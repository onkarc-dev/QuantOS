#pragma once
#include <cstdint>
#include <string>

enum class Side { BUY, SELL };
enum class OrderType { MARKET, LIMIT };
enum class OrderStatus { NEW, ACCEPTED, REJECTED, FILLED, CANCELLED };

inline const char* to_string(Side side) { return side == Side::BUY ? "BUY" : "SELL"; }
inline const char* to_string(OrderStatus s) {
    switch (s) {
        case OrderStatus::NEW: return "NEW";
        case OrderStatus::ACCEPTED: return "ACCEPTED";
        case OrderStatus::REJECTED: return "REJECTED";
        case OrderStatus::FILLED: return "FILLED";
        case OrderStatus::CANCELLED: return "CANCELLED";
    }
    return "UNKNOWN";
}

struct OrderRequest {
    uint64_t client_order_id = 0;
    std::string symbol;
    Side side = Side::BUY;
    OrderType type = OrderType::MARKET;
    double quantity = 0.0;
    double limit_price = 0.0;
    std::string strategy_tag;
};

struct OrderExecution {
    uint64_t client_order_id = 0;
    std::string broker_order_id;
    std::string symbol;
    Side side = Side::BUY;
    OrderStatus status = OrderStatus::NEW;
    double requested_quantity = 0.0;
    double filled_quantity = 0.0;
    double fill_price = 0.0;
    double commission = 0.0;
    uint64_t exchange_ts_ns = 0;
    std::string message;
};

struct Position {
    std::string symbol;
    double quantity = 0.0;
    double avg_price = 0.0;
    double realized_pnl = 0.0;
    double unrealized_pnl = 0.0;
};
