#pragma once

#include "PrismConfig.hpp"

#include <cstdint>
#include <deque>
#include <string>

struct Bar {
    uint64_t ts = 0;
    double open = 0.0;
    double high = 0.0;
    double low = 0.0;
    double close = 0.0;
    double volume = 0.0;
    double atr_14 = 0.0;
};

class PrismStrategy {
public:
    enum class State { IDLE, BREAKOUT, RETEST };

    struct Signal {
        bool valid = false;
        double entry_price = 0.0;
        double stop_loss = 0.0;
        double target1 = 0.0;
        double target2 = 0.0;
        double setup_score = 0.0;
        std::string reason;
    };

    PrismStrategy();
    explicit PrismStrategy(const StrategyRulesConfig& config);

    void on_new_bar(const Bar& bar);
    bool has_signal() const;
    Signal current_signal() const;
    uint64_t bars_processed() const;
    const StrategyRulesConfig& config() const;

private:
    void detect_breakout(const Bar& bar);
    void detect_retest(const Bar& bar);
    double calculate_score(const Bar& bar);
    double average_volume(size_t lookback) const;
    void update_trend_filter(const Bar& bar);
    bool trend_filter_allows_long() const;

private:
    StrategyRulesConfig config_;
    std::deque<Bar> history_;
    State state_ = State::IDLE;
    Signal signal_;
    uint64_t bars_processed_ = 0;
    uint64_t breakout_bar_index_ = 0;
    uint64_t last_signal_bar_ = 0;
    double breakout_level_ = 0.0;
    uint64_t bars_since_htf_close_ = 0;
    bool ema_seeded_ = false;
    double htf_fast_ema_ = 0.0;
    double htf_slow_ema_ = 0.0;
};
