#pragma once

#include "prism_live_engine.hpp"

#include <cstdint>
#include <fstream>
#include <string>

class TradeManager {
public:
    enum class PositionState {
        FLAT,
        LONG_OPEN
    };

    struct ManagedTrade {
        uint64_t trade_id = 0;

        double entry_price = 0.0;
        double stop_loss = 0.0;
        double initial_stop_loss = 0.0;
        double initial_risk = 0.0;

        double target1 = 0.0;
        double target2 = 0.0;

        double exit_price = 0.0;
        double r_multiple = 0.0;

        bool target1_hit = false;
        bool closed = false;

        double setup_score = 0.0;

        std::string entry_reason;
        std::string exit_reason;
    };

    TradeManager();
    explicit TradeManager(const std::string& csv_path);

    void on_signal(const PrismSignal& signal);
    void on_price(double price);

    bool has_open_trade() const;
    ManagedTrade current_trade() const;

    uint64_t total_trades() const;
    uint64_t wins() const;
    uint64_t losses() const;
    uint64_t breakevens() const;

    double gross_r() const;
    double average_r() const;
    double win_rate() const;

    void write_summary_json(const std::string& path) const;

private:
    void close_trade(double price, const std::string& reason);
    void open_csv(const std::string& csv_path);
    void write_trade_close_csv();

private:
    PositionState state_;
    ManagedTrade trade_;

    uint64_t next_trade_id_;
    uint64_t total_trades_;
    uint64_t wins_;
    uint64_t losses_;
    uint64_t breakevens_;

    double gross_r_;

    std::ofstream csv_;
};