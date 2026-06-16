#pragma once
#include "OrderTypes.hpp"
#include <algorithm>
#include <cmath>
#include <string>
#include <unordered_map>

struct RiskConfig {
    double starting_equity = 100000.0;
    double max_risk_per_trade_pct = 0.005;      // 0.5% equity per trade
    double max_symbol_notional = 25000.0;
    double max_gross_notional = 75000.0;
    double max_daily_loss = 2000.0;
    int max_open_positions = 6;
    int max_orders_per_minute = 120;
};

struct RiskDecision {
    bool approved = false;
    std::string reason;
    double notional = 0.0;
};

class RiskManager {
public:
    explicit RiskManager(RiskConfig cfg = {}) : cfg_(cfg), equity_(cfg.starting_equity) {}

    RiskDecision validate(const OrderRequest& order, double reference_price,
                          const std::unordered_map<std::string, Position>& positions) {
        if (order.quantity <= 0.0) return {false, "quantity must be positive", 0.0};
        if (reference_price <= 0.0) return {false, "reference price invalid", 0.0};
        if (daily_realized_pnl_ <= -std::abs(cfg_.max_daily_loss)) return {false, "daily loss limit reached", 0.0};
        if (orders_this_minute_ >= cfg_.max_orders_per_minute) return {false, "orders per minute limit reached", 0.0};

        const double order_notional = std::abs(order.quantity * reference_price);
        if (order_notional > cfg_.max_symbol_notional) return {false, "symbol notional limit exceeded", order_notional};

        double gross = order_notional;
        int open_positions = 0;
        for (const auto& kv : positions) {
            const auto& p = kv.second;
            if (std::abs(p.quantity) > 1e-12) {
                ++open_positions;
                gross += std::abs(p.quantity * reference_price);
            }
        }
        if (gross > cfg_.max_gross_notional) return {false, "gross notional limit exceeded", order_notional};
        if (open_positions >= cfg_.max_open_positions && positions.find(order.symbol) == positions.end()) {
            return {false, "max open positions reached", order_notional};
        }
        ++orders_this_minute_;
        return {true, "approved", order_notional};
    }

    void reset_rate_window() { orders_this_minute_ = 0; }
    double max_risk_amount() const { return equity_ * cfg_.max_risk_per_trade_pct; }
    void on_realized_pnl(double pnl) { daily_realized_pnl_ += pnl; equity_ += pnl; }
    double equity() const { return equity_; }
    double daily_realized_pnl() const { return daily_realized_pnl_; }
    double daily_loss_utilization() const { return std::abs(daily_realized_pnl_) / std::max(1.0, std::abs(cfg_.max_daily_loss)); }
    const RiskConfig& config() const { return cfg_; }

private:
    RiskConfig cfg_;
    double equity_ = 0.0;
    double daily_realized_pnl_ = 0.0;
    int orders_this_minute_ = 0;
};
