#include "prism_live_engine.hpp"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <sstream>

namespace {

static constexpr bool ENABLE_BAR_LOGS = false;
static constexpr bool ENABLE_SIGNAL_LOGS = true;

std::string ns_to_simple_time(uint64_t ns) {
    const uint64_t sec = ns / 1000000000ULL;

    std::ostringstream oss;
    oss << sec;

    return oss.str();
}

uint64_t normalize_timestamp_ns(uint64_t ts) {
    // Binance usually gives milliseconds.
    if (ts > 0 && ts < 100000000000000ULL) {
        return ts * 1000000ULL;
    }

    // Microseconds.
    if (ts >= 100000000000000ULL && ts < 100000000000000000ULL) {
        return ts * 1000ULL;
    }

    // Already nanoseconds.
    return ts;
}

Bar to_strategy_bar(const PrismBar& b) {
    Bar out{};

    out.ts = static_cast<uint64_t>(
        std::strtoull(b.timestamp.c_str(), nullptr, 10)
    );

    out.open = b.open;
    out.high = b.high;
    out.low = b.low;
    out.close = b.close;
    out.volume = b.volume;
    out.atr_14 = b.atr_14;

    return out;
}


} // namespace

PrismLiveEngine::PrismLiveEngine(int bar_seconds)
    : bar_seconds_(bar_seconds), strategy_(StrategyRulesConfig{})
{
}

PrismLiveEngine::PrismLiveEngine(int bar_seconds, const StrategyRulesConfig& strategy_config)
    : bar_seconds_(bar_seconds), strategy_(strategy_config)
{
}

void PrismLiveEngine::on_trade(const TradePacket& trade) {
    if (trade.price <= 0.0 || trade.volume <= 0.0) {
        return;
    }

    const uint64_t exchange_ts_ns =
        normalize_timestamp_ns(trade.exchange_ts_ns);

    if (exchange_ts_ns == 0) {
        return;
    }

    const uint64_t bar_ns =
        static_cast<uint64_t>(bar_seconds_) * 1000000000ULL;

    const uint64_t trade_bar_start =
        (exchange_ts_ns / bar_ns) * bar_ns;

    if (!has_current_bar_) {
        current_bar_start_ns_ = trade_bar_start;
        start_new_bar(trade);
        return;
    }

    if (trade_bar_start != current_bar_start_ns_) {
        close_current_bar();
        current_bar_start_ns_ = trade_bar_start;
        start_new_bar(trade);
        return;
    }

    update_current_bar(trade);
}

void PrismLiveEngine::start_new_bar(const TradePacket& trade) {
    const uint64_t exchange_ts_ns =
        normalize_timestamp_ns(trade.exchange_ts_ns);

    has_current_bar_ = true;

    current_bar_ = PrismBar{};
    current_bar_.timestamp = ns_to_simple_time(exchange_ts_ns);
    current_bar_.open = trade.price;
    current_bar_.high = trade.price;
    current_bar_.low = trade.price;
    current_bar_.close = trade.price;
    current_bar_.volume = trade.volume;
    current_bar_.vwap = trade.price;
    current_bar_.atr_14 = 0.0;
}

void PrismLiveEngine::update_current_bar(const TradePacket& trade) {
    current_bar_.high =
        std::max(current_bar_.high, trade.price);

    current_bar_.low =
        std::min(current_bar_.low, trade.price);

    current_bar_.close = trade.price;

    const double old_value =
        current_bar_.vwap * current_bar_.volume;

    const double new_value =
        trade.price * trade.volume;

    current_bar_.volume += trade.volume;

    if (current_bar_.volume > 0.0) {
        current_bar_.vwap =
            (old_value + new_value) / current_bar_.volume;
    }
}

void PrismLiveEngine::close_current_bar() {
    bars_.push_back(current_bar_);

    if (bars_.size() > 200) {
        bars_.pop_front();
    }

    compute_atr();

    if (ENABLE_BAR_LOGS) {
        std::cout
            << "[LIVE_BAR_CLOSED]"
            << " bars=" << bars_.size()
            << " O=" << bars_.back().open
            << " H=" << bars_.back().high
            << " L=" << bars_.back().low
            << " C=" << bars_.back().close
            << " V=" << bars_.back().volume
            << " VWAP=" << bars_.back().vwap
            << " ATR14=" << bars_.back().atr_14
            << "\n";
    }

    const Bar strategy_bar =
        to_strategy_bar(bars_.back());

    strategy_.on_new_bar(strategy_bar);

    if (strategy_.has_signal()) {
        const auto sig =
            strategy_.current_signal();

        last_signal_ = PrismSignal{};
        last_signal_.active = true;
        last_signal_.reason = sig.reason;
        last_signal_.entry_price = sig.entry_price;
        last_signal_.stop_loss = sig.stop_loss;
        last_signal_.target1 = sig.target1;
        last_signal_.target2 = sig.target2;
        last_signal_.setup_score = sig.setup_score;

        if (ENABLE_SIGNAL_LOGS) {
            std::cout
            << "[LIVE_PRISM_SIGNAL]"
            << " reason=" << last_signal_.reason
            << " entry=" << last_signal_.entry_price
            << " stop=" << last_signal_.stop_loss
            << " t1=" << last_signal_.target1
            << " t2=" << last_signal_.target2
            << " score=" << last_signal_.setup_score
            << "\n";
        }
    } else {
        last_signal_ = PrismSignal{};
    }
}

void PrismLiveEngine::compute_atr() {
    if (bars_.empty()) {
        return;
    }

    if (bars_.size() < 2) {
        bars_.back().atr_14 =
            bars_.back().high - bars_.back().low;
        return;
    }

    const size_t count =
        std::min<size_t>(14, bars_.size() - 1);

    double atr_sum = 0.0;

    const size_t start =
        bars_.size() - count;

    for (size_t i = start; i < bars_.size(); ++i) {
        const auto& bar = bars_[i];
        const auto& prev = bars_[i - 1];

        const double tr1 = bar.high - bar.low;
        const double tr2 = std::abs(bar.high - prev.close);
        const double tr3 = std::abs(bar.low - prev.close);

        atr_sum += std::max({tr1, tr2, tr3});
    }

    if (count > 0) {
        bars_.back().atr_14 =
            atr_sum / static_cast<double>(count);
    }
}

double PrismLiveEngine::previous_20_bar_high() const {
    if (bars_.size() < 21) {
        return 0.0;
    }

    double high =
        bars_[bars_.size() - 21].high;

    for (size_t i = bars_.size() - 20; i < bars_.size() - 1; ++i) {
        high = std::max(high, bars_[i].high);
    }

    return high;
}

double PrismLiveEngine::compute_setup_score(const PrismBar& bar) const {
    double structure = 8.0;
    double positioning = 8.0;
    double regime = 7.0;
    double microstructure = 7.0;
    double interaction = 8.0;

    if (bar.close > bar.vwap) {
        positioning += 1.0;
    }

    if (bar.volume > 0.0) {
        microstructure += 0.5;
    }

    const double score =
        structure * 0.25 +
        positioning * 0.25 +
        regime * 0.15 +
        microstructure * 0.15 +
        interaction * 0.20;

    return std::min(score, 10.0);
}

void PrismLiveEngine::evaluate_prism() {
    // Disabled. Signal generation is handled by PrismStrategy.
}

bool PrismLiveEngine::has_signal() const {
    return last_signal_.active;
}

PrismSignal PrismLiveEngine::last_signal() const {
    return last_signal_;
}

size_t PrismLiveEngine::bars_count() const {
    return bars_.size();
}

double PrismLiveEngine::last_close() const {
    if (has_current_bar_) {
        return current_bar_.close;
    }

    if (!bars_.empty()) {
        return bars_.back().close;
    }

    return 0.0;
}