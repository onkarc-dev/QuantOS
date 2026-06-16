#include "../dashboard/DashboardWriter.hpp"
#include "../PrismConfigLoader.hpp"
#include "../engine_shared.hpp"
#include "../prism_live_engine.hpp"
#include "../storage/EventStore.hpp"
#include "../time_utils.hpp"
#include "../trading/BrokerAdapterStub.hpp"
#include "../trading/PaperBroker.hpp"
#include "../trading/Portfolio.hpp"
#include "../trading/PositionSizer.hpp"
#include "../trading/RiskManager.hpp"

#include <chrono>
#include <csignal>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

namespace {
bool g_running = true;
void stop_handler(int) { g_running = false; }

std::vector<std::string> split_symbols(const std::string& s) {
    std::vector<std::string> out;
    std::stringstream ss(s);
    std::string item;
    while (std::getline(ss, item, ',')) if (!item.empty()) out.push_back(item);
    return out.empty() ? std::vector<std::string>{"btcusdt"} : out;
}

struct Args {
    std::string mode = "paper";
    std::vector<std::string> symbols{"btcusdt", "ethusdt"};
    std::string data_path = "data/sample_market_data.csv";
    int bar_seconds = 10;
    int snapshot_every = 25;
    bool force_demo_signal = false;
    std::string config_path;
    std::string output_dir;
    PrismConfig config;
};

Args parse_args(int argc, char** argv) {
    Args a;
    for (int i = 1; i < argc; ++i) {
        std::string x = argv[i];
        auto take = [&](std::string& dst){ if (i + 1 < argc) dst = argv[++i]; };
        if (x == "--mode") take(a.mode);
        else if (x == "--symbols" && i + 1 < argc) a.symbols = split_symbols(argv[++i]);
        else if (x == "--data") take(a.data_path);
        else if (x == "--bar-seconds" && i + 1 < argc) a.bar_seconds = std::stoi(argv[++i]);
        else if (x == "--snapshot-every" && i + 1 < argc) a.snapshot_every = std::max(1, std::stoi(argv[++i]));
        else if (x == "--force-demo-signal") a.force_demo_signal = true;
        else if (x == "--config" && i + 1 < argc) a.config_path = argv[++i];
        else if (x == "--output-dir" && i + 1 < argc) a.output_dir = argv[++i];
    }
    if (!a.config_path.empty()) {
        a.config = prism_config_loader::load(a.config_path);
        a.mode = a.config.mode == "backtest" ? "paper" : a.config.mode;
        a.symbols = a.config.symbols;
        a.data_path = a.config.input_data;
        a.bar_seconds = a.config.bar_seconds;
        if (a.output_dir.empty()) a.output_dir = a.config.output_dir;
    }
    return a;
}

bool read_next_price(std::ifstream& in, double& price, double& vol) {
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty() || line.find("timestamp") != std::string::npos) continue;
        std::stringstream ss(line);
        std::string cell;
        std::vector<std::string> cols;
        while (std::getline(ss, cell, ',')) cols.push_back(cell);
        try {
            if (cols.size() >= 5) {
                price = std::stod(cols[4]);
                vol = cols.size() >= 6 ? std::stod(cols[5]) : 1.0;
                return true;
            }
            if (cols.size() >= 2) { price = std::stod(cols[1]); vol = 1.0; return true; }
        } catch (...) { continue; }
    }
    return false;
}

void maybe_submit_order(const std::string& symbol, const std::string& reason, double entry, double stop, double target1, double target2,
                        uint64_t ts_ns, uint64_t& next_order_id, uint64_t& signals,
                        RiskManager& risk, Portfolio& portfolio, IBroker& broker, EventStore& store) {
    ++signals;
    store.signal(symbol, reason, entry, stop, target1, target2);
    const double qty = PositionSizer::fixed_fractional(
        risk.equity(), risk.config().max_risk_per_trade_pct, entry, stop, risk.config().max_symbol_notional);

    OrderRequest order;
    order.client_order_id = next_order_id++;
    order.symbol = symbol;
    order.side = Side::BUY;
    order.quantity = qty;
    order.strategy_tag = reason;

    const auto decision = risk.validate(order, entry, portfolio.positions());
    store.risk_decision(symbol, decision.approved, decision.reason, decision.notional);
    if (!decision.approved) {
        std::cout << "RISK_REJECT symbol=" << symbol << " reason=" << decision.reason << "\n";
        return;
    }
    auto exec = broker.submit_order(order, entry, ts_ns);
    portfolio.apply_fill(exec);
    const auto it = portfolio.positions().find(symbol);
    if (it != portfolio.positions().end()) {
        const auto& p = it->second;
        store.position_snapshot(symbol, p.quantity, p.avg_price, p.realized_pnl, p.unrealized_pnl);
    }
    std::cout << "ORDER " << to_string(exec.status) << " symbol=" << symbol
              << " qty=" << exec.filled_quantity << " fill=" << exec.fill_price
              << " reason=" << reason << "\n";
}
}

int main(int argc, char** argv) {
    std::signal(SIGINT, stop_handler);
    std::signal(SIGTERM, stop_handler);

    const Args args = parse_args(argc, argv);
    const std::string out_dir = args.output_dir.empty() ? ("outputs/" + args.config.user_id + "/" + args.config.job_id) : args.output_dir;
    std::filesystem::create_directories(out_dir);

    EventStore store(out_dir + "/events.jsonl");
    RiskConfig rc;
    rc.max_risk_per_trade_pct = args.config.strategy.risk.risk_per_trade_pct > 0.2 ? args.config.strategy.risk.risk_per_trade_pct / 100.0 : args.config.strategy.risk.risk_per_trade_pct;
    rc.max_daily_loss = rc.starting_equity * (args.config.strategy.risk.max_daily_loss_pct / 100.0);
    rc.max_open_positions = args.config.strategy.risk.max_open_positions;
    rc.max_symbol_notional = args.config.strategy.risk.max_symbol_notional;
    RiskManager risk(rc);
    Portfolio portfolio(out_dir + "/ledger.csv");
    DashboardWriter dashboard(out_dir + "/dashboard");

    std::unique_ptr<IBroker> broker;
    if (args.mode == "live-stub") broker = std::make_unique<BrokerAdapterStub>();
    else broker = std::make_unique<PaperBroker>(&store, 1.0, 0.5);

    std::unordered_map<std::string, PrismLiveEngine> engines;
    for (const auto& s : args.symbols) engines.emplace(s, PrismLiveEngine(args.bar_seconds, args.config.strategy));

    std::ifstream data(args.data_path);
    if (!data.is_open()) {
        std::cerr << "Could not open data file: " << args.data_path << "\n";
        return 2;
    }

    std::cout << "PRISMFlow C++ Heavy Paper Trading App v2\n"
              << "Mode: " << args.mode << " Broker: " << broker->name() << "\n"
              << "Symbols: ";
    for (const auto& s : args.symbols) std::cout << s << " ";
    std::cout << "\nOutputs: " << out_dir << "/\n"
              << "Dashboard: " << out_dir << "/dashboard/index.html\n"
              << "Dashboard server: scripts\\run_dashboard_server_windows.bat\n";

    uint64_t processed = 0, signals = 0, next_order_id = 1;
    std::unordered_map<std::string, bool> last_signal_state;
    double base_price = 0.0, vol = 1.0;

    dashboard.write_snapshot(processed, signals, args.mode, portfolio, risk.equity(), risk.daily_realized_pnl(), risk.daily_loss_utilization());
    store.append("SYSTEM_START", "{\"app\":\"prism_cpp_heavy_paper_v2\"}");

    while (g_running && read_next_price(data, base_price, vol)) {
        for (size_t i = 0; i < args.symbols.size(); ++i) {
            const std::string& symbol = args.symbols[i];
            const double symbol_price = base_price * (1.0 + 0.0025 * static_cast<double>(i));
            TradePacket p{};
            p.price = symbol_price;
            p.volume = vol;
            std::snprintf(p.symbol, sizeof(p.symbol), "%s", symbol.c_str());
            p.exchange_ts_ns = now_ns();
            p.ingest_ts_ns = p.exchange_ts_ns;
            p.trade_id = processed + 1;

            auto& engine = engines.at(symbol);
            engine.on_trade(p);
            portfolio.mark(symbol, symbol_price);

            const bool demo_fire = args.force_demo_signal && processed == 20 && i == 0;
            const bool sig_now = engine.has_signal();
            const bool sig_prev = last_signal_state[symbol];
            if (demo_fire) {
                maybe_submit_order(symbol, "FORCED_DEMO_SIGNAL", symbol_price, symbol_price * 0.9975,
                                   symbol_price * 1.005, symbol_price * 1.01, p.exchange_ts_ns,
                                   next_order_id, signals, risk, portfolio, *broker, store);
            } else if (sig_now && !sig_prev) {
                const auto sig = engine.last_signal();
                maybe_submit_order(symbol, sig.reason, sig.entry_price, sig.stop_loss, sig.target1, sig.target2,
                                   p.exchange_ts_ns, next_order_id, signals, risk, portfolio, *broker, store);
            }
            last_signal_state[symbol] = sig_now;
            ++processed;
        }

        if (processed % static_cast<uint64_t>(args.snapshot_every) == 0) {
            dashboard.write_snapshot(processed, signals, args.mode, portfolio, risk.equity(), risk.daily_realized_pnl(),
                                     risk.daily_loss_utilization(), 1.3, 25.0);
            store.metric("processed", static_cast<double>(processed));
            std::this_thread::sleep_for(std::chrono::milliseconds(10)); // demo-friendly refresh pacing
        }
    }

    dashboard.write_snapshot(processed, signals, args.mode, portfolio, risk.equity(), risk.daily_realized_pnl(),
                             risk.daily_loss_utilization(), 1.3, 25.0);
    store.append("SYSTEM_STOP", "{\"reason\":\"end_of_data_or_user_stop\"}");
    std::ofstream summary(out_dir + "/backtest_summary.json");
    summary << "{\n  \"processed\": " << processed << ",\n  \"signals\": " << signals
            << ",\n  \"realized_pnl\": " << portfolio.total_realized_pnl()
            << ",\n  \"unrealized_pnl\": " << portfolio.total_unrealized_pnl()
            << ",\n  \"gross_notional\": " << portfolio.gross_notional()
            << "\n}\n";
    // Standard PRISMFlow root-level files for backend report readers.
    {
        std::ofstream o(out_dir + "/dashboard_snapshot.json");
        o << "{\n"
          << "  \"mode\": \"" << args.mode << "\",\n"
          << "  \"processed\": " << processed << ",\n"
          << "  \"signals\": " << signals << ",\n"
          << "  \"realized_pnl\": " << portfolio.total_realized_pnl() << ",\n"
          << "  \"unrealized_pnl\": " << portfolio.total_unrealized_pnl() << "\n"
          << "}\n";
    }
    {
        std::ofstream o(out_dir + "/trade_log.csv");
        o << "trade_id,entry_time,entry_price,stop_loss,target1,target2,exit_time,exit_price,exit_reason,r_multiple,setup_score_at_entry,regime_at_entry,holding_bars\n";
    }
    {
        std::ofstream o(out_dir + "/setup_score_log.csv");
        o << "timestamp,structure,positioning,regime,microstructure,interaction,setup_score,tier\n";
    }
    {
        std::ofstream o(out_dir + "/entry_intent_log.csv");
        o << "timestamp,entry_type,breakout_level,retest_zone,entry_price,stop_loss,target1,target2,setup_score,reason_codes\n";
    }
    {
        std::ofstream o(out_dir + "/setup_validation_report.json");
        o << "{\n  \"valid\": true,\n  \"setup_name\": \"PRISMFlow Paper Trading\",\n  \"notes\": [\"Paper mode preserves PRISMFlow output file contract.\"]\n}\n";
    }
    {
        std::ofstream o(out_dir + "/audit_log.json");
        o << "[\n  {\"event\":\"PAPER_RUN_COMPLETE\",\"processed\":" << processed << ",\"signals\":" << signals << "}\n]\n";
    }

    std::cout << "Done. processed=" << processed << " signals=" << signals << "\n";
    std::cout << "Generated: " << out_dir << "/events.jsonl, ledger.csv, backtest_summary.json, dashboard_snapshot.json and standard PRISM CSV/JSON files\n";
    return 0;
}
