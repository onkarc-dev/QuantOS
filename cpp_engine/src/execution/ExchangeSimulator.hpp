#pragma once

#include "../trading/OrderTypes.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <random>
#include <string>
#include <vector>

namespace quantos::execution {

struct SimulatorConfig {
    uint64_t network_latency_ns = 250000;
    uint64_t gateway_latency_ns = 100000;
    uint64_t exchange_latency_ns = 150000;
    uint64_t acknowledgement_delay_ns = 100000;
    uint64_t random_latency_min_ns = 0;
    uint64_t random_latency_max_ns = 250000;
    uint64_t base_queue_delay_ns = 250000;
    uint64_t session_open_ns = 0;
    uint64_t session_close_ns = UINT64_MAX;
    double spread_bps = 2.0;
    double slippage_bps = 0.5;
    double market_impact_bps_per_notional_ratio = 8.0;
    double visible_liquidity_qty = 10.0;
    double reject_probability = 0.0;
    bool trading_halted = false;
    bool auction_mode = false;
    uint64_t random_seed = 42;
};

struct SimulatorMetrics {
    uint64_t orders = 0;
    uint64_t accepted = 0;
    uint64_t rejected = 0;
    uint64_t expired = 0;
    uint64_t filled = 0;
    uint64_t partial_filled = 0;
    uint64_t liquidity_exhausted = 0;
    uint64_t halted_rejections = 0;
    uint64_t session_rejections = 0;
    uint64_t post_only_rejections = 0;
    double total_slippage_bps = 0.0;
    double total_impact_bps = 0.0;
    double total_fill_ratio = 0.0;
    uint64_t total_latency_ns = 0;
    uint64_t max_latency_ns = 0;
    uint64_t total_queue_delay_ns = 0;
    std::vector<uint64_t> latency_samples;

    double avg_latency_ns() const { return accepted ? static_cast<double>(total_latency_ns) / accepted : 0.0; }
    double avg_slippage_bps() const { return accepted ? total_slippage_bps / accepted : 0.0; }
    double avg_impact_bps() const { return accepted ? total_impact_bps / accepted : 0.0; }
    double avg_fill_ratio() const { return accepted ? total_fill_ratio / accepted : 0.0; }

    uint64_t percentile_latency(double pct) const {
        if (latency_samples.empty()) return 0;
        std::vector<uint64_t> v = latency_samples;
        std::sort(v.begin(), v.end());
        pct = std::max(0.0, std::min(100.0, pct));
        return v[static_cast<std::size_t>((pct / 100.0) * static_cast<double>(v.size() - 1))];
    }
};

struct SimulatorResult {
    OrderExecution execution;
    bool trade_event = false;
    bool portfolio_event = false;
    bool risk_event = false;
    bool analytics_event = false;
    bool latency_event = false;
    bool queue_event = false;
    bool fill_quality_event = false;
};

class ExchangeSimulator {
public:
    explicit ExchangeSimulator(SimulatorConfig cfg = {})
        : cfg_(cfg), rng_(cfg.random_seed) {}

    void configure(const SimulatorConfig& cfg) {
        cfg_ = cfg;
        rng_.seed(cfg.random_seed);
    }

    const SimulatorConfig& config() const { return cfg_; }
    const SimulatorMetrics& metrics() const { return metrics_; }

    void set_trading_halt(bool halted) { cfg_.trading_halted = halted; }
    void set_session(uint64_t open_ns, uint64_t close_ns) { cfg_.session_open_ns = open_ns; cfg_.session_close_ns = close_ns; }
    void set_visible_liquidity(double qty) { cfg_.visible_liquidity_qty = std::max(0.0, qty); }

    SimulatorResult execute(const OrderRequest& request, double reference_price, uint64_t ts_ns) {
        ++metrics_.orders;
        SimulatorResult result;
        OrderExecution& e = result.execution;
        e.client_order_id = request.client_order_id;
        e.symbol = request.symbol;
        e.side = request.side;
        e.requested_quantity = request.quantity;
        e.remaining_quantity = request.quantity;
        e.reference_price = reference_price;
        e.exchange_ts_ns = ts_ns;

        if (request.quantity <= 0.0 || reference_price <= 0.0) {
            return reject(e, "invalid price or quantity");
        }
        if (cfg_.trading_halted) {
            ++metrics_.halted_rejections;
            return reject(e, "trading halted");
        }
        if (ts_ns < cfg_.session_open_ns || ts_ns > cfg_.session_close_ns) {
            ++metrics_.session_rejections;
            return reject(e, "outside trading session");
        }
        if (cfg_.auction_mode && request.type == OrderType::MARKET) {
            return expire(e, "auction mode does not accept market execution");
        }
        if (random_reject()) {
            return reject(e, "random exchange rejection");
        }

        const double half_spread = reference_price * cfg_.spread_bps / 20000.0;
        const double best_ask = reference_price + half_spread;
        const double best_bid = reference_price - half_spread;
        const double touch = request.side == Side::BUY ? best_ask : best_bid;

        if ((request.post_only || request.time_in_force == TimeInForce::POST_ONLY) && crosses_book(request, best_bid, best_ask)) {
            ++metrics_.post_only_rejections;
            return reject(e, "post-only would cross book");
        }

        if (!stop_condition_met(request, reference_price)) {
            e.status = OrderStatus::ACCEPTED;
            e.message = "stop order accepted and waiting for trigger";
            accept_no_fill(e, ts_ns);
            result.risk_event = result.analytics_event = result.latency_event = true;
            return result;
        }

        if (!limit_price_allows_fill(request, touch)) {
            if (request.time_in_force == TimeInForce::IOC || request.time_in_force == TimeInForce::FOK) {
                return expire(e, "time-in-force expired without executable price");
            }
            e.status = OrderStatus::ACCEPTED;
            e.message = "accepted resting order";
            accept_no_fill(e, ts_ns);
            result.risk_event = result.analytics_event = result.latency_event = result.queue_event = true;
            return result;
        }

        const double available = std::max(0.0, cfg_.visible_liquidity_qty);
        if (request.time_in_force == TimeInForce::FOK && available + 1e-12 < request.quantity) {
            ++metrics_.liquidity_exhausted;
            return expire(e, "FOK expired: insufficient visible liquidity");
        }

        const double fill_qty = std::min(request.quantity, available);
        if (fill_qty <= 0.0) {
            ++metrics_.liquidity_exhausted;
            return expire(e, "liquidity exhausted");
        }

        const bool partial = fill_qty + 1e-12 < request.quantity;
        const double liquidity_ratio = available > 0.0 ? request.quantity / available : 1.0;
        const double impact_bps = std::max(0.0, liquidity_ratio - 1.0) * cfg_.market_impact_bps_per_notional_ratio;
        const double direction = request.side == Side::BUY ? 1.0 : -1.0;
        const double exec_bps = cfg_.slippage_bps + impact_bps;
        const double price = touch * (1.0 + direction * exec_bps / 10000.0);
        const uint64_t queue_delay = queue_delay_ns(request, fill_qty, available);
        const uint64_t latency = total_latency_ns(queue_delay);

        e.status = partial ? OrderStatus::PARTIALLY_FILLED : OrderStatus::FILLED;
        e.filled_quantity = fill_qty;
        e.remaining_quantity = request.quantity - fill_qty;
        e.fill_price = price;
        e.avg_fill_price = price;
        e.slippage_bps = direction * ((price - reference_price) / reference_price) * 10000.0;
        e.market_impact_bps = impact_bps;
        e.fill_ratio = request.quantity > 0.0 ? fill_qty / request.quantity : 0.0;
        e.queue_delay_ns = queue_delay;
        e.total_latency_ns = latency;
        e.ack_ts_ns = ts_ns + latency;
        e.message = partial ? "partial fill after liquidity exhaustion" : "filled by exchange simulator";

        update_metrics(e, partial);
        result.trade_event = result.portfolio_event = result.risk_event = true;
        result.analytics_event = result.latency_event = result.queue_event = result.fill_quality_event = true;
        return result;
    }

private:
    SimulatorResult reject(OrderExecution& e, const std::string& reason) {
        ++metrics_.rejected;
        e.status = OrderStatus::REJECTED;
        e.message = reason;
        SimulatorResult r;
        r.execution = e;
        r.risk_event = r.analytics_event = true;
        return r;
    }

    SimulatorResult expire(OrderExecution& e, const std::string& reason) {
        ++metrics_.expired;
        e.status = OrderStatus::EXPIRED;
        e.message = reason;
        SimulatorResult r;
        r.execution = e;
        r.risk_event = r.analytics_event = true;
        return r;
    }

    void accept_no_fill(OrderExecution& e, uint64_t ts_ns) {
        ++metrics_.accepted;
        const uint64_t latency = total_latency_ns(0);
        e.ack_ts_ns = ts_ns + latency;
        e.total_latency_ns = latency;
        metrics_.total_latency_ns += latency;
        metrics_.max_latency_ns = std::max(metrics_.max_latency_ns, latency);
        metrics_.latency_samples.push_back(latency);
    }

    bool random_reject() {
        if (cfg_.reject_probability <= 0.0) return false;
        std::uniform_real_distribution<double> dist(0.0, 1.0);
        return dist(rng_) < cfg_.reject_probability;
    }

    uint64_t random_latency_ns() {
        if (cfg_.random_latency_max_ns <= cfg_.random_latency_min_ns) return cfg_.random_latency_min_ns;
        std::uniform_int_distribution<uint64_t> dist(cfg_.random_latency_min_ns, cfg_.random_latency_max_ns);
        return dist(rng_);
    }

    uint64_t queue_delay_ns(const OrderRequest& request, double fill_qty, double available) const {
        if (available <= 0.0) return cfg_.base_queue_delay_ns;
        const double pressure = std::max(0.0, request.quantity - fill_qty) / available;
        return cfg_.base_queue_delay_ns + static_cast<uint64_t>(pressure * static_cast<double>(cfg_.base_queue_delay_ns));
    }

    uint64_t total_latency_ns(uint64_t queue_delay) {
        return cfg_.network_latency_ns + cfg_.gateway_latency_ns + cfg_.exchange_latency_ns +
               cfg_.acknowledgement_delay_ns + queue_delay + random_latency_ns();
    }

    static bool crosses_book(const OrderRequest& request, double best_bid, double best_ask) {
        if (request.type == OrderType::MARKET || request.type == OrderType::STOP) return true;
        if (request.side == Side::BUY) return request.limit_price >= best_ask;
        return request.limit_price <= best_bid;
    }

    static bool stop_condition_met(const OrderRequest& request, double reference_price) {
        if (request.type != OrderType::STOP && request.type != OrderType::STOP_LIMIT) return true;
        if (request.stop_price <= 0.0) return false;
        return request.side == Side::BUY ? reference_price >= request.stop_price : reference_price <= request.stop_price;
    }

    static bool limit_price_allows_fill(const OrderRequest& request, double touch) {
        if (request.type == OrderType::MARKET || request.type == OrderType::STOP) return true;
        if (request.limit_price <= 0.0) return false;
        return request.side == Side::BUY ? request.limit_price >= touch : request.limit_price <= touch;
    }

    void update_metrics(const OrderExecution& e, bool partial) {
        ++metrics_.accepted;
        if (partial) ++metrics_.partial_filled; else ++metrics_.filled;
        if (partial) ++metrics_.liquidity_exhausted;
        metrics_.total_slippage_bps += std::abs(e.slippage_bps);
        metrics_.total_impact_bps += e.market_impact_bps;
        metrics_.total_fill_ratio += e.fill_ratio;
        metrics_.total_latency_ns += e.total_latency_ns;
        metrics_.total_queue_delay_ns += e.queue_delay_ns;
        metrics_.max_latency_ns = std::max(metrics_.max_latency_ns, e.total_latency_ns);
        metrics_.latency_samples.push_back(e.total_latency_ns);
    }

    SimulatorConfig cfg_;
    SimulatorMetrics metrics_;
    std::mt19937_64 rng_;
};

} // namespace quantos::execution
