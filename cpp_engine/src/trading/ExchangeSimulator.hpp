#pragma once

#include "MatchingEngine.hpp"

#include <algorithm>
#include <cstdint>
#include <functional>
#include <random>
#include <string>
#include <utility>
#include <vector>

class ExchangeSimulator {
public:
    enum class SessionState { OPEN, CLOSED, HALTED, AUCTION };

    struct Config {
        uint64_t seed = 42;
        uint64_t network_latency_min_ns = 50'000;
        uint64_t network_latency_max_ns = 150'000;
        uint64_t gateway_latency_min_ns = 10'000;
        uint64_t gateway_latency_max_ns = 50'000;
        uint64_t exchange_latency_min_ns = 5'000;
        uint64_t exchange_latency_max_ns = 25'000;
        uint64_t acknowledgement_delay_min_ns = 20'000;
        uint64_t acknowledgement_delay_max_ns = 75'000;
        uint64_t queue_delay_per_order_ns = 1'000;
        double slippage_bps = 0.0;
        double bid_ask_spread_bps = 1.0;
        double top_of_book_liquidity = 100.0;
        double second_level_liquidity = 0.0;
        double second_level_distance_bps = 2.0;
        double market_impact_bps_per_x_liquidity = 1.0;
        bool auction_accepts_orders = true;
    };

    explicit ExchangeSimulator(Config cfg = {}) : cfg_(cfg), rng_(cfg.seed) {}

    MatchingEngine::MatchResult submit_order(const OrderRequest& request, double reference_mid_price, uint64_t receive_ts_ns = 0) {
        MatchingEngine::MatchResult result;
        initialise_rejection(result.execution, request, receive_ts_ns);

        if (reference_mid_price <= 0.0) {
            result.execution.message = "invalid reference price";
            stamp_latency(result.execution, 0);
            return result;
        }
        if (state_ == SessionState::HALTED) {
            result.execution.message = "trading halt active";
            stamp_latency(result.execution, 0);
            return result;
        }
        if (state_ == SessionState::CLOSED) {
            result.execution.message = "session closed";
            stamp_latency(result.execution, 0);
            return result;
        }
        if (state_ == SessionState::AUCTION) {
            if (auction_hook_) return auction_hook_(request, reference_mid_price, receive_ts_ns);
            if (!cfg_.auction_accepts_orders) {
                result.execution.message = "auction order handling unavailable";
                stamp_latency(result.execution, 0);
                return result;
            }
        }

        const uint64_t queue_depth = seed_synthetic_book(request, reference_mid_price, receive_ts_ns);
        auto routed = request;
        if (request.type == OrderType::MARKET) {
            routed.type = OrderType::LIMIT;
            routed.time_in_force = TimeInForce::IOC;
            routed.limit_price = impacted_limit_price(request, reference_mid_price);
        }

        result = engine_.submit_order(routed, receive_ts_ns);
        apply_execution_costs(result.execution, request, reference_mid_price, queue_depth);
        for (auto& report : result.execution_reports) {
            apply_execution_costs(report.execution, request, reference_mid_price, queue_depth);
        }
        return result;
    }

    void set_session_state(SessionState state) { state_ = state; }
    SessionState session_state() const { return state_; }
    void open_session() { state_ = SessionState::OPEN; }
    void close_session() { state_ = SessionState::CLOSED; }
    void halt() { state_ = SessionState::HALTED; }
    void resume() { state_ = SessionState::OPEN; }
    void enter_auction() { state_ = SessionState::AUCTION; }

    using AuctionHook = std::function<MatchingEngine::MatchResult(const OrderRequest&, double, uint64_t)>;
    void set_auction_hook(AuctionHook hook) { auction_hook_ = std::move(hook); }

    const Config& config() const { return cfg_; }

private:
    static constexpr double kEpsilon = 1e-12;

    static double bps(double value) { return value / 10000.0; }

    void initialise_rejection(OrderExecution& e, const OrderRequest& r, uint64_t ts_ns) const {
        e = OrderExecution{};
        e.client_order_id = r.client_order_id;
        e.symbol = r.symbol;
        e.side = r.side;
        e.status = OrderStatus::REJECTED;
        e.requested_quantity = r.quantity;
        e.remaining_quantity = r.quantity;
        e.exchange_ts_ns = ts_ns;
        e.ack_ts_ns = ts_ns;
    }

    uint64_t uniform_latency(uint64_t min_ns, uint64_t max_ns) {
        if (max_ns <= min_ns) return min_ns;
        std::uniform_int_distribution<uint64_t> dist(min_ns, max_ns);
        return dist(rng_);
    }

    uint64_t synthetic_latency(uint64_t queue_depth) {
        const uint64_t network = uniform_latency(cfg_.network_latency_min_ns, cfg_.network_latency_max_ns);
        const uint64_t gateway = uniform_latency(cfg_.gateway_latency_min_ns, cfg_.gateway_latency_max_ns);
        const uint64_t exchange = uniform_latency(cfg_.exchange_latency_min_ns, cfg_.exchange_latency_max_ns);
        const uint64_t acknowledgement = uniform_latency(cfg_.acknowledgement_delay_min_ns, cfg_.acknowledgement_delay_max_ns);
        const uint64_t queue_delay = queue_depth * cfg_.queue_delay_per_order_ns;
        last_queue_delay_ns_ = queue_delay;
        return network + gateway + exchange + acknowledgement + queue_delay;
    }

    void stamp_latency(OrderExecution& e, uint64_t queue_depth) {
        const uint64_t total = synthetic_latency(queue_depth);
        e.queue_delay_ns = last_queue_delay_ns_;
        e.total_latency_ns = total;
        e.ack_ts_ns = e.exchange_ts_ns + total;
    }

    double side_adjusted_price(Side side, double mid, double spread_bps, double extra_bps) const {
        const double direction = side == Side::BUY ? 1.0 : -1.0;
        return mid * (1.0 + direction * bps(spread_bps * 0.5 + extra_bps));
    }

    double market_impact_bps(const OrderRequest& request) const {
        if (cfg_.top_of_book_liquidity <= kEpsilon) return 0.0;
        return (request.quantity / cfg_.top_of_book_liquidity) * cfg_.market_impact_bps_per_x_liquidity;
    }

    double impacted_limit_price(const OrderRequest& request, double mid) const {
        const double extra_bps = cfg_.slippage_bps + market_impact_bps(request) + cfg_.second_level_distance_bps + cfg_.bid_ask_spread_bps;
        return side_adjusted_price(request.side, mid, cfg_.bid_ask_spread_bps, extra_bps);
    }

    uint64_t seed_synthetic_book(const OrderRequest& request, double mid, uint64_t ts_ns) {
        const Side contra_side = request.side == Side::BUY ? Side::SELL : Side::BUY;
        const double first_extra = cfg_.slippage_bps + market_impact_bps(request);
        const double first_price = side_adjusted_price(request.side, mid, cfg_.bid_ask_spread_bps, first_extra);
        uint64_t levels = 0;

        if (cfg_.top_of_book_liquidity > kEpsilon) {
            seed_liquidity(request.symbol, contra_side, cfg_.top_of_book_liquidity, first_price, ts_ns);
            ++levels;
        }
        if (cfg_.second_level_liquidity > kEpsilon) {
            const double second_price = side_adjusted_price(request.side, mid, cfg_.bid_ask_spread_bps,
                                                            first_extra + cfg_.second_level_distance_bps);
            seed_liquidity(request.symbol, contra_side, cfg_.second_level_liquidity, second_price, ts_ns);
            ++levels;
        }
        return levels;
    }

    void seed_liquidity(const std::string& symbol, Side side, double quantity, double price, uint64_t ts_ns) {
        OrderRequest liquidity;
        liquidity.client_order_id = next_liquidity_order_id_++;
        liquidity.symbol = symbol;
        liquidity.side = side;
        liquidity.type = OrderType::LIMIT;
        liquidity.time_in_force = TimeInForce::GTC;
        liquidity.quantity = quantity;
        liquidity.limit_price = price;
        liquidity.strategy_tag = "EXCHANGE_SIMULATOR_LIQUIDITY";
        engine_.submit_order(liquidity, ts_ns);
    }

    void apply_execution_costs(OrderExecution& e, const OrderRequest& original, double reference_mid_price, uint64_t queue_depth) {
        e.symbol = original.symbol;
        e.side = original.side;
        e.requested_quantity = original.quantity;
        if (e.filled_quantity > 0.0 && e.remaining_quantity > kEpsilon && e.status == OrderStatus::EXPIRED) {
            e.status = OrderStatus::PARTIALLY_FILLED;
            e.message = "liquidity exhausted; partial simulator fill";
        }
        e.reference_price = reference_mid_price;
        e.slippage_bps = cfg_.slippage_bps;
        e.market_impact_bps = market_impact_bps(original);
        stamp_latency(e, queue_depth);
    }

    Config cfg_;
    SessionState state_ = SessionState::OPEN;
    MatchingEngine engine_;
    std::mt19937_64 rng_;
    uint64_t next_liquidity_order_id_ = 800000000000ULL;
    uint64_t last_queue_delay_ns_ = 0;
    AuctionHook auction_hook_;
};