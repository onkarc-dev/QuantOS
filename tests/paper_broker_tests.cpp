#include "trading/PaperBroker.hpp"

#include <cassert>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>

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

std::string read_file(const std::string& path) {
    std::ifstream in(path);
    std::ostringstream ss;
    ss << in.rdbuf();
    return ss.str();
}

void test_submit_market_routes_through_matching_engine() {
    PaperBroker broker(nullptr, 1.0, 0.5);
    auto req = order(1, Side::BUY, OrderType::MARKET, 2.0);

    auto exec = broker.submit_order(req, 100.0, 123);

    assert(exec.client_order_id == 1);
    assert(exec.broker_order_id == "PAPER-1");
    assert(exec.status == OrderStatus::FILLED);
    assert_near(exec.filled_quantity, 2.0);
    assert_near(exec.remaining_quantity, 0.0);
    assert(exec.fill_price > 100.0);
    assert(exec.commission > 0.0);
}

void test_cancel_resting_limit_order() {
    PaperBroker broker;
    auto req = order(2, Side::BUY, OrderType::LIMIT, 3.0, 99.0);

    auto accepted = broker.submit_order(req, 100.0, 124);
    assert(accepted.status == OrderStatus::ACCEPTED);
    assert_near(accepted.filled_quantity, 0.0);
    assert_near(accepted.remaining_quantity, 3.0);

    auto cancelled = broker.cancel_order(2, 125);
    assert(cancelled.client_order_id == 2);
    assert(cancelled.broker_order_id == "PAPER-2");
    assert(cancelled.status == OrderStatus::CANCELLED);
    assert_near(cancelled.remaining_quantity, 3.0);
}

void test_partial_fill_from_seeded_liquidity() {
    PaperBroker broker(nullptr, 0.0, 0.0);
    broker.seed_liquidity("BTCUSDT", Side::SELL, 2.0, 101.0, 126);

    auto req = order(3, Side::BUY, OrderType::LIMIT, 5.0, 101.0);
    auto exec = broker.submit_order(req, 100.0, 127);

    assert(exec.client_order_id == 3);
    assert(exec.status == OrderStatus::PARTIALLY_FILLED);
    assert_near(exec.filled_quantity, 2.0);
    assert_near(exec.remaining_quantity, 3.0);
    assert_near(exec.fill_price, 101.0);
    assert_near(exec.avg_fill_price, 101.0);
}

void test_eventstore_execution_events_are_emitted() {
    const std::string dir = "paper_broker_test_output";
    const std::string path = dir + "/events.jsonl";
    std::filesystem::remove_all(dir);

    {
        EventStore store(path);
        PaperBroker broker(&store, 0.0, 0.0);
        auto req = order(4, Side::BUY, OrderType::MARKET, 1.0);
        auto exec = broker.submit_order(req, 100.0, 128);
        assert(exec.status == OrderStatus::FILLED);
    }

    const auto events = read_file(path);
    assert(events.find("ORDER_SUBMIT") != std::string::npos);
    assert(events.find("ORDER_EXECUTION") != std::string::npos);
    assert(events.find("ORDER_FILL") != std::string::npos);
    assert(events.find("PAPER-4") != std::string::npos);

    std::filesystem::remove_all(dir);
}

} // namespace

int main() {
    test_submit_market_routes_through_matching_engine();
    test_cancel_resting_limit_order();
    test_partial_fill_from_seeded_liquidity();
    test_eventstore_execution_events_are_emitted();
    return 0;
}
