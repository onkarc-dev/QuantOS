#include "connectors/BinanceClient.h"
#include "engine_shared.hpp"
#include "json_trade_parser.hpp"
#include "order_book.hpp"
#include "prism_live_engine.hpp"
#include "time_utils.hpp"
#include "trade_manager.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <csignal>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

RawTradeQueue raw_trade_queue;
TradeQueue trade_queue;
std::atomic<bool> running{true};

namespace {

void signal_handler(int) {
    running.store(false, std::memory_order_relaxed);
}

void update_max(std::atomic<uint64_t>& target, uint64_t value) {
    uint64_t prev = target.load(std::memory_order_relaxed);
    while (value > prev &&
           !target.compare_exchange_weak(prev, value, std::memory_order_relaxed)) {
        // retry
    }
}


class LatencyStats {
public:
    void observe(uint64_t value_ns) noexcept {
        if (value_ns == 0) {
            return;
        }

        current_ns_.store(value_ns, std::memory_order_relaxed);
        total_ns_.fetch_add(value_ns, std::memory_order_relaxed);
        count_.fetch_add(1, std::memory_order_relaxed);
        update_max(max_ns_, value_ns);

        const uint64_t index = write_index_.fetch_add(1, std::memory_order_relaxed);
        samples_[index & (kWindowSize - 1)].store(value_ns, std::memory_order_relaxed);
    }

    uint64_t current_ns() const noexcept {
        return current_ns_.load(std::memory_order_relaxed);
    }

    uint64_t max_ns() const noexcept {
        return max_ns_.load(std::memory_order_relaxed);
    }

    uint64_t avg_ns() const noexcept {
        const uint64_t count = count_.load(std::memory_order_relaxed);
        if (count == 0) {
            return 0;
        }

        return total_ns_.load(std::memory_order_relaxed) / count;
    }

    uint64_t percentile_ns(double percentile) const {
        const uint64_t count = count_.load(std::memory_order_relaxed);
        const std::size_t n = static_cast<std::size_t>(std::min<uint64_t>(count, kWindowSize));

        if (n == 0) {
            return 0;
        }

        std::vector<uint64_t> values;
        values.reserve(n);

        for (std::size_t i = 0; i < n; ++i) {
            const uint64_t value = samples_[i].load(std::memory_order_relaxed);
            if (value > 0) {
                values.push_back(value);
            }
        }

        if (values.empty()) {
            return 0;
        }

        std::sort(values.begin(), values.end());

        const double clamped = std::max(0.0, std::min(100.0, percentile));
        const std::size_t index = static_cast<std::size_t>(
            (clamped / 100.0) * static_cast<double>(values.size() - 1)
        );

        return values[index];
    }

private:
    static constexpr std::size_t kWindowSize = 4096;

    std::array<std::atomic<uint64_t>, kWindowSize> samples_{};
    std::atomic<uint64_t> write_index_{0};
    std::atomic<uint64_t> count_{0};
    std::atomic<uint64_t> total_ns_{0};
    std::atomic<uint64_t> current_ns_{0};
    std::atomic<uint64_t> max_ns_{0};
};


void print_signal_banner(const PrismSignal& signal) {
    std::cout
        << "\n========== PRISM SIGNAL GENERATED ==========\n"
        << "Entry  : " << signal.entry_price << "\n"
        << "Stop   : " << signal.stop_loss << "\n"
        << "Target1: " << signal.target1 << "\n"
        << "Target2: " << signal.target2 << "\n"
        << "Score  : " << signal.setup_score << "\n"
        << "Reason : " << signal.reason << "\n"
        << "===========================================\n\n";
}

void write_system_score_json(
    const std::string& path,
    const BinanceClient& client,
    const TradeManager& trade_manager,
    uint64_t processed,
    uint64_t parsed,
    uint64_t parse_dropped,
    const LatencyStats& engine_latency_stats,
    const LatencyStats& ingest_latency_stats)
{
    std::ofstream out(path, std::ios::out);
    if (!out.is_open()) {
        return;
    }

    const uint64_t ws_received = client.received();
    const uint64_t ws_dropped = client.dropped();
    const uint64_t total_ws = ws_received + ws_dropped;
    const double drop_rate = total_ws == 0
        ? 0.0
        : static_cast<double>(ws_dropped) / static_cast<double>(total_ws);

    const double reliability_score = std::max(0.0, 100.0 - drop_rate * 1000.0);
    const double latency_ms = static_cast<double>(engine_latency_stats.percentile_ns(95.0)) / 1000000.0;
    const double latency_score = std::max(0.0, 100.0 - latency_ms / 5.0);
    const double avg_r = trade_manager.average_r();
    const double strategy_score = std::max(0.0, std::min(100.0, 50.0 + avg_r * 50.0));
    const double system_score = reliability_score * 0.40 + latency_score * 0.25 + strategy_score * 0.35;

    out
        << "{\n"
        << "  \"project_name\": \"PRISMFlow Low-Latency Engine\",\n"
        << "  \"ws_received\": " << ws_received << ",\n"
        << "  \"ws_dropped\": " << ws_dropped << ",\n"
        << "  \"ws_drop_rate\": " << drop_rate << ",\n"
        << "  \"ws_drop_queue_full\": " << client.dropped_queue_full() << ",\n"
        << "  \"ws_drop_too_large\": " << client.dropped_too_large() << ",\n"
        << "  \"parse_dropped\": " << parse_dropped << ",\n"
        << "  \"total_processed\": " << processed << ",\n"
        << "  \"total_parsed\": " << parsed << ",\n"
        << "  \"current_engine_latency_ns\": " << engine_latency_stats.current_ns() << ",\n"
        << "  \"avg_engine_latency_ns\": " << engine_latency_stats.avg_ns() << ",\n"
        << "  \"p50_engine_latency_ns\": " << engine_latency_stats.percentile_ns(50.0) << ",\n"
        << "  \"p95_engine_latency_ns\": " << engine_latency_stats.percentile_ns(95.0) << ",\n"
        << "  \"p99_engine_latency_ns\": " << engine_latency_stats.percentile_ns(99.0) << ",\n"
        << "  \"max_engine_latency_ns\": " << engine_latency_stats.max_ns() << ",\n"
        << "  \"current_ingest_to_engine_latency_ns\": " << ingest_latency_stats.current_ns() << ",\n"
        << "  \"avg_ingest_to_engine_latency_ns\": " << ingest_latency_stats.avg_ns() << ",\n"
        << "  \"p50_ingest_to_engine_latency_ns\": " << ingest_latency_stats.percentile_ns(50.0) << ",\n"
        << "  \"p95_ingest_to_engine_latency_ns\": " << ingest_latency_stats.percentile_ns(95.0) << ",\n"
        << "  \"p99_ingest_to_engine_latency_ns\": " << ingest_latency_stats.percentile_ns(99.0) << ",\n"
        << "  \"max_ingest_to_engine_latency_ns\": " << ingest_latency_stats.max_ns() << ",\n"
        << "  \"latency_score\": " << latency_score << ",\n"
        << "  \"reliability_score\": " << reliability_score << ",\n"
        << "  \"strategy_score\": " << strategy_score << ",\n"
        << "  \"system_score\": " << system_score << "\n"
        << "}\n";
}

} // namespace

int main(int argc, char** argv) {
    std::string symbol = "btcusdt";

    if (argc >= 2) {
        symbol = argv[1];
    }

    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

    [[maybe_unused]] FastOrderBook book;

    constexpr int prism_bar_seconds = 10;
    PrismLiveEngine prism(prism_bar_seconds);
    TradeManager trade_manager("trade_log.csv");

    std::atomic<uint64_t> processed{0};
    std::atomic<uint64_t> parsed{0};
    std::atomic<uint64_t> parse_dropped{0};
    LatencyStats engine_latency_stats;
    LatencyStats ingest_latency_stats;
    std::atomic<uint64_t> last_price_scaled{0};
    std::atomic<uint64_t> prism_signals{0};

    BinanceClient client(symbol);

    std::thread parser_thread([&]() {
        RawTradeMessage raw{};
        TradePacket parsed_packet{};

        while (running.load(std::memory_order_relaxed)) {
            if (raw_trade_queue.pop(raw)) {
                if (!json_trade_parser::parse_trade_packet(raw, parsed_packet)) {
                    parse_dropped.fetch_add(1, std::memory_order_relaxed);
                    continue;
                }

                while (!trade_queue.push(parsed_packet)) {
                    PAUSE();
                    if (!running.load(std::memory_order_relaxed)) {
                        break;
                    }
                }

                parsed.fetch_add(1, std::memory_order_relaxed);
            } else {
                PAUSE();
            }
        }
    });

    std::thread engine_thread([&]() {
        TradePacket p{};
        bool previous_signal_state = false;

        while (running.load(std::memory_order_relaxed)) {
            if (trade_queue.pop(p)) {
                const uint64_t start = now_ns();

                // OrderBook remains disabled during strategy/latency testing.
                // book.match(p);

                prism.on_trade(p);
                trade_manager.on_price(p.price);

                const bool current_signal_state = prism.has_signal();

                if (current_signal_state && !previous_signal_state) {
                    const PrismSignal signal = prism.last_signal();
                    prism_signals.fetch_add(1, std::memory_order_relaxed);
                    print_signal_banner(signal);
                    trade_manager.on_signal(signal);
                }

                previous_signal_state = current_signal_state;

                processed.fetch_add(1, std::memory_order_relaxed);
                last_price_scaled.store(
                    static_cast<uint64_t>(p.price * 100.0),
                    std::memory_order_relaxed
                );

                const uint64_t end_ns = now_ns();
                const uint64_t engine_latency = end_ns - start;
                const uint64_t ingest_to_engine_latency =
                    (p.ingest_ts_ns > 0 && end_ns > p.ingest_ts_ns)
                        ? (end_ns - p.ingest_ts_ns)
                        : 0;

                if (engine_latency < 1000000000ULL) {
                    engine_latency_stats.observe(engine_latency);
                }

                if (ingest_to_engine_latency > 0 && ingest_to_engine_latency < 5000000000ULL) {
                    ingest_latency_stats.observe(ingest_to_engine_latency);
                }
            } else {
                PAUSE();
            }
        }
    });

    std::thread feed_thread([&]() {
        client.run();
    });

    std::cout
        << "PRISMFlow Low-Latency Engine running. Symbol: "
        << symbol << "@trade\n"
        << "PRISM live engine enabled: " << prism_bar_seconds << "-second bars\n"
        << "Hot-path patch: WebSocket callback only timestamp-copy-enqueue; parsing and strategy run on worker threads\n"
        << "Generated on stop: trade_log.csv, performance_summary.json, system_score.json\n"
        << "Press Ctrl+C to stop.\n";

    uint64_t last_processed = 0;
    uint64_t last_signals = 0;

    while (running.load(std::memory_order_relaxed)) {
        std::this_thread::sleep_for(std::chrono::seconds(2));

        const uint64_t now_processed = processed.load(std::memory_order_relaxed);
        const uint64_t per_sec = (now_processed - last_processed) / 2;
        last_processed = now_processed;

        const uint64_t now_signals = prism_signals.load(std::memory_order_relaxed);
        const uint64_t signals_per_sec = (now_signals - last_signals) / 2;
        last_signals = now_signals;

        const double last_price =
            static_cast<double>(last_price_scaled.load(std::memory_order_relaxed)) / 100.0;

        std::cout
            << "live_rate_msg_s=" << per_sec
            << " total_processed=" << now_processed
            << " ws_received=" << client.received()
            << " ws_dropped=" << client.dropped()
            << " ws_drop_queue_full=" << client.dropped_queue_full()
            << " ws_drop_too_large=" << client.dropped_too_large()
            << " parse_dropped=" << parse_dropped.load(std::memory_order_relaxed)
            << " raw_queue=" << raw_trade_queue.size_approx()
            << " trade_queue=" << trade_queue.size_approx()
            << " last_price=" << last_price
            << " bars=" << prism.bars_count()
            << " prism_signals_total=" << now_signals
            << " prism_signals_s=" << signals_per_sec
            << " open_trade=" << (trade_manager.has_open_trade() ? 1 : 0)
            << " total_trades=" << trade_manager.total_trades()
            << " wins=" << trade_manager.wins()
            << " losses=" << trade_manager.losses()
            << " breakevens=" << trade_manager.breakevens()
            << " gross_R=" << trade_manager.gross_r()
            << " avg_R=" << trade_manager.average_r()
            << " current_engine_latency_ns=" << engine_latency_stats.current_ns()
            << " avg_engine_latency_ns=" << engine_latency_stats.avg_ns()
            << " p50_engine_latency_ns=" << engine_latency_stats.percentile_ns(50.0)
            << " p95_engine_latency_ns=" << engine_latency_stats.percentile_ns(95.0)
            << " p99_engine_latency_ns=" << engine_latency_stats.percentile_ns(99.0)
            << " max_engine_latency_ns=" << engine_latency_stats.max_ns()
            << " current_ingest_to_engine_latency_ns=" << ingest_latency_stats.current_ns()
            << " avg_ingest_to_engine_latency_ns=" << ingest_latency_stats.avg_ns()
            << " p50_ingest_to_engine_latency_ns=" << ingest_latency_stats.percentile_ns(50.0)
            << " p95_ingest_to_engine_latency_ns=" << ingest_latency_stats.percentile_ns(95.0)
            << " p99_ingest_to_engine_latency_ns=" << ingest_latency_stats.percentile_ns(99.0)
            << " max_ingest_to_engine_latency_ns=" << ingest_latency_stats.max_ns()
            << "\n";
    }

    client.stop();

    if (feed_thread.joinable()) {
        feed_thread.join();
    }

    if (parser_thread.joinable()) {
        parser_thread.join();
    }

    if (engine_thread.joinable()) {
        engine_thread.join();
    }

    trade_manager.write_summary_json("performance_summary.json");
    write_system_score_json(
        "system_score.json",
        client,
        trade_manager,
        processed.load(std::memory_order_relaxed),
        parsed.load(std::memory_order_relaxed),
        parse_dropped.load(std::memory_order_relaxed),
        engine_latency_stats,
        ingest_latency_stats
    );

    std::cout
        << "Stopped. total_processed=" << processed.load(std::memory_order_relaxed)
        << " prism_signals=" << prism_signals.load(std::memory_order_relaxed)
        << " total_trades=" << trade_manager.total_trades()
        << " wins=" << trade_manager.wins()
        << " losses=" << trade_manager.losses()
        << " breakevens=" << trade_manager.breakevens()
        << " gross_R=" << trade_manager.gross_r()
        << " avg_R=" << trade_manager.average_r()
        << " ws_received=" << client.received()
        << " ws_dropped=" << client.dropped()
        << " p95_engine_latency_ns=" << engine_latency_stats.percentile_ns(95.0)
        << " p99_engine_latency_ns=" << engine_latency_stats.percentile_ns(99.0)
        << " max_engine_latency_ns=" << engine_latency_stats.max_ns()
        << " p95_ingest_to_engine_latency_ns=" << ingest_latency_stats.percentile_ns(95.0)
        << " p99_ingest_to_engine_latency_ns=" << ingest_latency_stats.percentile_ns(99.0)
        << " max_ingest_to_engine_latency_ns=" << ingest_latency_stats.max_ns()
        << "\n";

    std::cout
        << "Generated files: trade_log.csv, performance_summary.json, system_score.json\n";

    return 0;
}
