#include "trade_manager.hpp"

#include <fstream>
#include <iostream>

namespace {
constexpr bool ENABLE_TRADE_EVENT_LOGS = false;
}

TradeManager::TradeManager()
    : TradeManager("trade_log.csv")
{
}

TradeManager::TradeManager(const std::string& csv_path)
    : state_(PositionState::FLAT),
      next_trade_id_(1),
      total_trades_(0),
      wins_(0),
      losses_(0),
      breakevens_(0),
      gross_r_(0.0)
{
    open_csv(csv_path);
}

void TradeManager::open_csv(const std::string& csv_path)
{
    csv_.open(csv_path, std::ios::out);

    if (csv_.is_open()) {
        csv_
            << "trade_id,"
            << "entry,"
            << "exit,"
            << "initial_stop,"
            << "final_stop,"
            << "target1,"
            << "target2,"
            << "setup_score,"
            << "R_multiple,"
            << "result,"
            << "entry_reason,"
            << "exit_reason\n";

        csv_.flush();
    }
}

void TradeManager::on_signal(const PrismSignal& signal)
{
    if (!signal.active) {
        return;
    }

    if (state_ != PositionState::FLAT) {
        return;
    }

    const double risk = signal.entry_price - signal.stop_loss;

    if (risk <= 0.0) {
        return;
    }

    trade_ = ManagedTrade{};
    trade_.trade_id = next_trade_id_++;
    trade_.entry_price = signal.entry_price;
    trade_.stop_loss = signal.stop_loss;
    trade_.initial_stop_loss = signal.stop_loss;
    trade_.initial_risk = risk;
    trade_.target1 = signal.target1;
    trade_.target2 = signal.target2;
    trade_.setup_score = signal.setup_score;
    trade_.entry_reason = signal.reason;

    state_ = PositionState::LONG_OPEN;

    if (ENABLE_TRADE_EVENT_LOGS) {
        std::cout
            << "[TRADE_OPEN]"
            << " id=" << trade_.trade_id
            << " entry=" << trade_.entry_price
            << " stop=" << trade_.stop_loss
            << " t1=" << trade_.target1
            << " t2=" << trade_.target2
            << " score=" << trade_.setup_score
            << "\n";
    }
}

void TradeManager::on_price(double price)
{
    if (state_ != PositionState::LONG_OPEN) {
        return;
    }

    if (!trade_.target1_hit && price >= trade_.target1) {
        trade_.target1_hit = true;
        trade_.stop_loss = trade_.entry_price;

        if (ENABLE_TRADE_EVENT_LOGS) {
            std::cout
                << "[TARGET1_HIT]"
                << " id=" << trade_.trade_id
                << " price=" << price
                << " stop_moved_to_breakeven"
                << "\n";
        }
    }

    if (price >= trade_.target2) {
        close_trade(price, "TARGET2_HIT");
        return;
    }

    if (price <= trade_.stop_loss) {
        close_trade(
            price,
            trade_.target1_hit ? "BREAKEVEN_STOP" : "STOP_LOSS"
        );
        return;
    }
}

void TradeManager::close_trade(double price, const std::string& reason)
{
    trade_.closed = true;
    trade_.exit_price = price;
    trade_.exit_reason = reason;

    if (trade_.initial_risk > 0.0) {
        trade_.r_multiple =
            (trade_.exit_price - trade_.entry_price) / trade_.initial_risk;
    }

    if (reason == "BREAKEVEN_STOP") {
        trade_.r_multiple = 0.0;
    }

    ++total_trades_;
    gross_r_ += trade_.r_multiple;

    if (trade_.r_multiple > 0.0) {
        ++wins_;
    } else if (trade_.r_multiple < 0.0) {
        ++losses_;
    } else {
        ++breakevens_;
    }

    write_trade_close_csv();

    if (ENABLE_TRADE_EVENT_LOGS) {
        std::cout
            << "[TRADE_CLOSE]"
            << " id=" << trade_.trade_id
            << " exit=" << trade_.exit_price
            << " reason=" << trade_.exit_reason
            << " R=" << trade_.r_multiple
            << "\n";
    }

    state_ = PositionState::FLAT;
}

void TradeManager::write_trade_close_csv()
{
    if (!csv_.is_open()) {
        return;
    }

    std::string result = "BREAKEVEN";

    if (trade_.r_multiple > 0.0) {
        result = "WIN";
    } else if (trade_.r_multiple < 0.0) {
        result = "LOSS";
    }

    csv_
        << trade_.trade_id << ","
        << trade_.entry_price << ","
        << trade_.exit_price << ","
        << trade_.initial_stop_loss << ","
        << trade_.stop_loss << ","
        << trade_.target1 << ","
        << trade_.target2 << ","
        << trade_.setup_score << ","
        << trade_.r_multiple << ","
        << result << ","
        << trade_.entry_reason << ","
        << trade_.exit_reason
        << "\n";

    // Do not flush on every trade close in the live hot path.
    // The file stream is flushed/closed by its destructor on normal shutdown.
}

bool TradeManager::has_open_trade() const
{
    return state_ == PositionState::LONG_OPEN;
}

TradeManager::ManagedTrade TradeManager::current_trade() const
{
    return trade_;
}

uint64_t TradeManager::total_trades() const { return total_trades_; }
uint64_t TradeManager::wins() const { return wins_; }
uint64_t TradeManager::losses() const { return losses_; }
uint64_t TradeManager::breakevens() const { return breakevens_; }
double TradeManager::gross_r() const { return gross_r_; }

double TradeManager::average_r() const
{
    if (total_trades_ == 0) {
        return 0.0;
    }

    return gross_r_ / static_cast<double>(total_trades_);
}

double TradeManager::win_rate() const
{
    if (total_trades_ == 0) {
        return 0.0;
    }

    return static_cast<double>(wins_) / static_cast<double>(total_trades_);
}

void TradeManager::write_summary_json(const std::string& path) const
{
    std::ofstream out(path, std::ios::out);

    if (!out.is_open()) {
        return;
    }

    out
        << "{\n"
        << "  \"total_trades\": " << total_trades_ << ",\n"
        << "  \"wins\": " << wins_ << ",\n"
        << "  \"losses\": " << losses_ << ",\n"
        << "  \"breakevens\": " << breakevens_ << ",\n"
        << "  \"win_rate\": " << win_rate() << ",\n"
        << "  \"gross_R\": " << gross_r_ << ",\n"
        << "  \"average_R\": " << average_r() << ",\n"
        << "  \"expectancy_R_per_trade\": " << average_r() << ",\n"
        << "  \"open_trade\": " << (has_open_trade() ? "true" : "false") << "\n"
        << "}\n";
}
