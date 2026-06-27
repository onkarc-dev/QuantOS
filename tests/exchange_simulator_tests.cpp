#include "trading/ExchangeSimulator.hpp"

#include <cassert>
#include <cmath>
#include <cstdint>
#include <string>

namespace {

void assert_near(double actual, double expected, double eps = 1e-9) {
    assert(std::fabs(actual - expected) < eps);
}

OrderRequest market_order(uint64_t id, Side side, double qty) {
    OrderRequest req;
    req.client_order_id = id;
    req.symbol = "BTCUSDT";
    req.side = side;
    req.type = OrderType::MARKET;
    req.quantity = qty;
    return req;
}

ExchangeSimulator::Config base_config() {
    ExchangeSimulator::Config cfg;
    cfg.network_latency_min_ns = 100;
    cfg.network_latency_max_ns = 200;
    cfg.gateway_latency_min_ns = 10;
    cfg.gateway_latency_max_ns = 20;
    cfg.exchange_latency_min_ns = 5;
    cfg.exchange_latency_max_ns = 15;
    cfg.acknowledgement_delay_min_ns = 50;
    cfg.acknowledgement_delay_max_ns = 70;
    cfg.queue_delay_per_order_ns = 3;
    cfg.bid_ask_spread_bps = 2.0;
    cfg.slippage_bps = 0.0;
    cfg.top_of_book_liquidity = 10.0;
    cfg.second_level_liquidity = 10.0;
    cfg.second_level_distance_bps = 3.0;
    cfg.market_impact_bps_per_x_liquidity = 1.0;
    return cfg;
}

void test_deterministic_latency_with_same_seed() {
    auto cfg = base_config();
    cfg.seed = 12345;
    ExchangeSimulator a(cfg);
    ExchangeSimulator b(cfg);

    auto ra = a.submit_order(market_order(1, Side::BUY, 1.0), 100.0, 1'000);
    auto rb = b.submit_order(market_order(1, Side::BUY, 1.0), 100.0, 1'000);

    assert(ra.execution.network_latency_ns == rb.execution.network_latency_ns);
    assert(ra.execution.gateway_latency_ns == rb.execution.gateway_latency_ns);
    assert(ra.execution.exchange_latency_ns == rb.execution.exchange_latency_ns);
    assert(ra.execution.acknowledgement_delay_ns == rb.execution.acknowledgement_delay_ns);
    assert(ra.execution.total_latency_ns == rb.execution.total_latency_ns);
    assert(ra.execution.queue_delay_ns == rb.execution.queue_delay_ns);
    assert(ra.execution.ack_ts_ns == rb.execution.ack_ts_ns);
}

void test_random_latency_within_bounds() {
    auto cfg = base_config();
    cfg.seed = 7;
    ExchangeSimulator sim(cfg);

    auto r = sim.submit_order(market_order(2, Side::BUY, 1.0), 100.0, 2'000);
    const uint64_t min_total = cfg.network_latency_min_ns + cfg.gateway_latency_min_ns +
                               cfg.exchange_latency_min_ns + cfg.acknowledgement_delay_min_ns +
                               (2 * cfg.queue_delay_per_order_ns);
    const uint64_t max_total = cfg.network_latency_max_ns + cfg.gateway_latency_max_ns +
                               cfg.exchange_latency_max_ns + cfg.acknowledgement_delay_max_ns +
                               (2 * cfg.queue_delay_per_order_ns);

    assert(r.execution.network_latency_ns >= cfg.network_latency_min_ns);
    assert(r.execution.network_latency_ns <= cfg.network_latency_max_ns);
    assert(r.execution.gateway_latency_ns >= cfg.gateway_latency_min_ns);
    assert(r.execution.gateway_latency_ns <= cfg.gateway_latency_max_ns);
    assert(r.execution.exchange_latency_ns >= cfg.exchange_latency_min_ns);
    assert(r.execution.exchange_latency_ns <= cfg.exchange_latency_max_ns);
    assert(r.execution.acknowledgement_delay_ns >= cfg.acknowledgement_delay_min_ns);
    assert(r.execution.acknowledgement_delay_ns <= cfg.acknowledgement_delay_max_ns);
    assert(r.execution.total_latency_ns >= min_total);
    assert(r.execution.total_latency_ns <= max_total);
    assert(r.execution.ack_ts_ns == r.execution.exchange_ts_ns + r.execution.total_latency_ns);
}

void test_halt_rejects_order() {
    ExchangeSimulator sim(base_config());
    sim.halt();
    auto r = sim.submit_order(market_order(3, Side::BUY, 1.0), 100.0, 3'000);
    assert(r.execution.status == OrderStatus::REJECTED);
    assert(r.execution.message.find("halt") != std::string::npos);
}

void test_session_closed_rejects_order() {
    ExchangeSimulator sim(base_config());
    sim.close_session();
    auto r = sim.submit_order(market_order(4, Side::BUY, 1.0), 100.0, 4'000);
    assert(r.execution.status == OrderStatus::REJECTED);
    assert(r.execution.message.find("session closed") != std::string::npos);
}

void test_liquidity_shortage_causes_partial_fill() {
    auto cfg = base_config();
    cfg.top_of_book_liquidity = 2.0;
    cfg.second_level_liquidity = 1.0;
    ExchangeSimulator sim(cfg);

    auto r = sim.submit_order(market_order(5, Side::BUY, 5.0), 100.0, 5'000);
    assert(r.execution.status == OrderStatus::PARTIALLY_FILLED);
    assert_near(r.execution.filled_quantity, 3.0);
    assert_near(r.execution.remaining_quantity, 2.0);
}

void test_synthetic_liquidity_does_not_accumulate_between_orders() {
    auto cfg = base_config();
    cfg.top_of_book_liquidity = 2.0;
    cfg.second_level_liquidity = 1.0;
    ExchangeSimulator sim(cfg);

    auto first = sim.submit_order(market_order(50, Side::BUY, 5.0), 100.0, 5'000);
    auto second = sim.submit_order(market_order(51, Side::BUY, 5.0), 100.0, 5'100);

    assert(first.execution.status == OrderStatus::PARTIALLY_FILLED);
    assert(second.execution.status == OrderStatus::PARTIALLY_FILLED);
    assert_near(first.execution.filled_quantity, 3.0);
    assert_near(second.execution.filled_quantity, 3.0);
}

void test_market_impact_increases_with_order_size() {
    auto cfg = base_config();
    cfg.top_of_book_liquidity = 10.0;
    cfg.market_impact_bps_per_x_liquidity = 2.0;
    ExchangeSimulator small(cfg);
    ExchangeSimulator large(cfg);

    auto small_r = small.submit_order(market_order(6, Side::BUY, 1.0), 100.0, 6'000);
    auto large_r = large.submit_order(market_order(7, Side::BUY, 8.0), 100.0, 7'000);

    assert(large_r.execution.market_impact_bps > small_r.execution.market_impact_bps);
    assert(large_r.execution.avg_fill_price > small_r.execution.avg_fill_price);
}

void test_slippage_is_configurable() {
    auto low_cfg = base_config();
    auto high_cfg = base_config();
    low_cfg.slippage_bps = 0.0;
    high_cfg.slippage_bps = 10.0;

    ExchangeSimulator low(low_cfg);
    ExchangeSimulator high(high_cfg);

    auto low_r = low.submit_order(market_order(8, Side::BUY, 1.0), 100.0, 8'000);
    auto high_r = high.submit_order(market_order(9, Side::BUY, 1.0), 100.0, 9'000);

    assert_near(low_r.execution.slippage_bps, 0.0);
    assert_near(high_r.execution.slippage_bps, 10.0);
    assert(high_r.execution.avg_fill_price > low_r.execution.avg_fill_price);
}

void test_auction_hook_is_used() {
    ExchangeSimulator sim(base_config());
    sim.enter_auction();
    sim.set_auction_hook([](const OrderRequest& request, double mid, uint64_t ts_ns) {
        MatchingEngine::MatchResult result;
        result.execution.client_order_id = request.client_order_id;
        result.execution.symbol = request.symbol;
        result.execution.side = request.side;
        result.execution.status = OrderStatus::ACCEPTED;
        result.execution.requested_quantity = request.quantity;
        result.execution.remaining_quantity = request.quantity;
        result.execution.reference_price = mid;
        result.execution.exchange_ts_ns = ts_ns;
        result.execution.message = "auction accepted";
        return result;
    });

    auto r = sim.submit_order(market_order(10, Side::BUY, 1.0), 100.0, 10'000);
    assert(r.execution.status == OrderStatus::ACCEPTED);
    assert(r.execution.message == "auction accepted");
    assert(r.execution.total_latency_ns > 0);
}

} // namespace

int main() {
    test_deterministic_latency_with_same_seed();
    test_random_latency_within_bounds();
    test_halt_rejects_order();
    test_session_closed_rejects_order();
    test_liquidity_shortage_causes_partial_fill();
    test_synthetic_liquidity_does_not_accumulate_between_orders();
    test_market_impact_increases_with_order_size();
    test_slippage_is_configurable();
    test_auction_hook_is_used();
    return 0;
}
