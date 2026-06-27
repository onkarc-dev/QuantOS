#pragma once
#include <cstdint>
#include <string>

enum class Side { BUY, SELL };
enum class OrderType { MARKET, LIMIT, STOP, STOP_LIMIT };
enum class TimeInForce { GTC, IOC, FOK, POST_ONLY };
enum class OrderStatus { NEW, ACCEPTED, PARTIALLY_FILLED, FILLED, CANCELLED, REJECTED, EXPIRED };

inline const char* to_string(Side side) { return side == Side::BUY ? "BUY" : "SELL"; }
inline const char* to_string(OrderType t) {
    switch (t) {
        case OrderType::MARKET: return "MARKET";
        case OrderType::LIMIT: return "LIMIT";
        case OrderType::STOP: return "STOP";
        case OrderType::STOP_LIMIT: return "STOP_LIMIT";
    }
    return "UNKNOWN";
}
inline const char* to_string(TimeInForce t) {
    switch (t) {
        case TimeInForce::GTC: return "GTC";
        case TimeInForce::IOC: return "IOC";
        case TimeInForce::FOK: return "FOK";
        case TimeInForce::POST_ONLY: return "POST_ONLY";
    }
    return "UNKNOWN";
}
inline const char* to_string(OrderStatus s) {
    switch (s) {
        case OrderStatus::NEW: return "NEW";
        case OrderStatus::ACCEPTED: return "ACCEPTED";
        case OrderStatus::PARTIALLY_FILLED: return "PARTIALLY_FILLED";
        case OrderStatus::REJECTED: return "REJECTED";
        case OrderStatus::FILLED: return "FILLED";
        case OrderStatus::CANCELLED: return "CANCELLED";
        case OrderStatus::EXPIRED: return "EXPIRED";
    }
    return "UNKNOWN";
}

struct OrderRequest {
    uint64_t client_order_id = 0;
    std::string symbol;
    Side side = Side::BUY;
    OrderType type = OrderType::MARKET;
    TimeInForce time_in_force = TimeInForce::GTC;
    double quantity = 0.0;
    double limit_price = 0.0;
    double stop_price = 0.0;
    bool post_only = false;
    bool reduce_only = false;
    std::string owner_id;
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
    double remaining_quantity = 0.0;
    double fill_price = 0.0;
    double avg_fill_price = 0.0;
    double reference_price = 0.0;
    double commission = 0.0;
    double slippage_bps = 0.0;
    double market_impact_bps = 0.0;
    double fill_ratio = 0.0;
    uint64_t exchange_ts_ns = 0;
    uint64_t ack_ts_ns = 0;
    uint64_t network_latency_ns = 0;
    uint64_t gateway_latency_ns = 0;
    uint64_t exchange_latency_ns = 0;
    uint64_t acknowledgement_delay_ns = 0;
    uint64_t total_latency_ns = 0;
    uint64_t queue_delay_ns = 0;
    std::string message;
};

struct Position {
    std::string symbol;
    double quantity = 0.0;
    double avg_price = 0.0;
    double realized_pnl = 0.0;
    double unrealized_pnl = 0.0;
};
