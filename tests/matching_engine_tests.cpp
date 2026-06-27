#include "../cpp_engine/src/trading/MatchingEngine.hpp"

#include <cassert>
#include <cmath>
#include <vector>

namespace {

void assert_near(double actual, double expected) {
    assert(std::fabs(actual - expected) < 1e-9);
}

OrderRequest order(uint64_t id, Side side, OrderType type, double qty, double price = 0.0) {
    OrderRequest req;
    req.client_order_id = id;
    req.symbol = "BTCUSDT";
    req.side = side;
    req.type = type;
    req.quantity = qty;
    req.limit_price = price;
    return req;
}

void test_market_buy_hits_best_ask() {
    MatchingEngine engine;
    auto resting = engine.submit_order(order(1, Side::SELL, OrderType::LIMIT, 5.0, 101.0));
    assert(resting.rested);

    auto result = engine.submit_order(order(2, Side::BUY, OrderType::MARKET, 2.0));
    assert(result.execution.status == OrderStatus::FILLED);
    assert(result.fills.size() == 1);
    assert(result.fills[0].resting_client_order_id == 1);
    assert_near(result.fills[0].price, 101.0);
    assert_near(result.execution.filled_quantity, 2.0);
    assert_near(result.execution.avg_fill_price, 101.0);
    assert_near(engine.ask_quantity(101.0), 3.0);
}

void test_market_sell_hits_best_bid() {
    MatchingEngine engine;
    assert(engine.submit_order(order(10, Side::BUY, OrderType::LIMIT, 4.0, 99.0)).rested);

    auto result = engine.submit_order(order(11, Side::SELL, OrderType::MARKET, 1.5));
    assert(result.execution.status == OrderStatus::FILLED);
    assert(result.fills.size() == 1);
    assert(result.fills[0].resting_client_order_id == 10);
    assert_near(result.fills[0].price, 99.0);
    assert_near(engine.bid_quantity(99.0), 2.5);
}

void test_limit_buy_crosses_ask() {
    MatchingEngine engine;
    assert(engine.submit_order(order(20, Side::SELL, OrderType::LIMIT, 3.0, 100.0)).rested);

    auto result = engine.submit_order(order(21, Side::BUY, OrderType::LIMIT, 2.0, 100.5));
    assert(result.execution.status == OrderStatus::FILLED);
    assert(result.fills.size() == 1);
    assert_near(result.fills[0].price, 100.0);
    assert_near(engine.ask_quantity(100.0), 1.0);
}

void test_limit_sell_crosses_bid() {
    MatchingEngine engine;
    assert(engine.submit_order(order(30, Side::BUY, OrderType::LIMIT, 3.0, 100.0)).rested);

    auto result = engine.submit_order(order(31, Side::SELL, OrderType::LIMIT, 2.0, 99.5));
    assert(result.execution.status == OrderStatus::FILLED);
    assert(result.fills.size() == 1);
    assert_near(result.fills[0].price, 100.0);
    assert_near(engine.bid_quantity(100.0), 1.0);
}

void test_fifo_priority() {
    MatchingEngine engine;
    assert(engine.submit_order(order(40, Side::SELL, OrderType::LIMIT, 1.0, 101.0)).rested);
    assert(engine.submit_order(order(41, Side::SELL, OrderType::LIMIT, 1.0, 101.0)).rested);
    assert(engine.submit_order(order(42, Side::SELL, OrderType::LIMIT, 1.0, 101.0)).rested);
    assert((engine.ask_order_ids(101.0) == std::vector<uint64_t>{40, 41, 42}));

    auto result = engine.submit_order(order(43, Side::BUY, OrderType::MARKET, 2.0));
    assert(result.execution.status == OrderStatus::FILLED);
    assert(result.fills.size() == 2);
    assert(result.fills[0].resting_client_order_id == 40);
    assert(result.fills[1].resting_client_order_id == 41);
    assert((engine.ask_order_ids(101.0) == std::vector<uint64_t>{42}));
}

void test_partial_fill_rests_remainder() {
    MatchingEngine engine;
    assert(engine.submit_order(order(50, Side::SELL, OrderType::LIMIT, 2.0, 101.0)).rested);

    auto result = engine.submit_order(order(51, Side::BUY, OrderType::LIMIT, 5.0, 101.0));
    assert(result.execution.status == OrderStatus::PARTIALLY_FILLED);
    assert(result.rested);
    assert_near(result.execution.filled_quantity, 2.0);
    assert_near(result.execution.remaining_quantity, 3.0);
    assert(engine.ask_order_ids(101.0).empty());
    assert((engine.bid_order_ids(101.0) == std::vector<uint64_t>{51}));
    assert_near(engine.bid_quantity(101.0), 3.0);
}

void test_multi_level_fill() {
    MatchingEngine engine;
    assert(engine.submit_order(order(60, Side::SELL, OrderType::LIMIT, 1.0, 100.0)).rested);
    assert(engine.submit_order(order(61, Side::SELL, OrderType::LIMIT, 2.0, 101.0)).rested);
    assert(engine.submit_order(order(62, Side::SELL, OrderType::LIMIT, 3.0, 102.0)).rested);

    auto result = engine.submit_order(order(63, Side::BUY, OrderType::MARKET, 4.5));
    assert(result.execution.status == OrderStatus::FILLED);
    assert(result.fills.size() == 3);
    assert(result.fills[0].resting_client_order_id == 60);
    assert(result.fills[1].resting_client_order_id == 61);
    assert(result.fills[2].resting_client_order_id == 62);
    assert_near(result.fills[0].quantity, 1.0);
    assert_near(result.fills[1].quantity, 2.0);
    assert_near(result.fills[2].quantity, 1.5);
    assert_near(result.execution.avg_fill_price, ((1.0 * 100.0) + (2.0 * 101.0) + (1.5 * 102.0)) / 4.5);
    assert_near(engine.ask_quantity(102.0), 1.5);
}

} // namespace

int main() {
    test_market_buy_hits_best_ask();
    test_market_sell_hits_best_bid();
    test_limit_buy_crosses_ask();
    test_limit_sell_crosses_bid();
    test_fifo_priority();
    test_partial_fill_rests_remainder();
    test_multi_level_fill();
    return 0;
}
