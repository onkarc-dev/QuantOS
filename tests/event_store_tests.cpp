#include "storage/EventStore.hpp"
#include "trading/OrderTypes.hpp"

#include <cassert>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

namespace {

std::vector<std::string> read_lines(const std::string& path) {
    std::ifstream in(path);
    std::vector<std::string> lines;
    std::string line;
    while (std::getline(in, line)) {
        if (!line.empty()) lines.push_back(line);
    }
    return lines;
}

bool contains(const std::string& text, const std::string& needle) {
    return text.find(needle) != std::string::npos;
}

void assert_basic_jsonl_event_shape(const std::string& line) {
    assert(!line.empty());
    assert(line.front() == '{');
    assert(line.back() == '}');
    assert(contains(line, "\"ts_ns\":"));
    assert(contains(line, "\"type\":"));
    assert(contains(line, "\"payload\":{") );
}

void test_eventstore_writes_valid_jsonl_shapes_and_lifecycle_events() {
    const std::string dir = "event_store_test_output";
    const std::string path = dir + "/events.jsonl";
    std::filesystem::remove_all(dir);

    {
        EventStore store(path);

        OrderRequest req;
        req.client_order_id = 42;
        req.symbol = "BTCUSDT";
        req.side = Side::BUY;
        req.type = OrderType::MARKET;
        req.quantity = 1.25;
        req.limit_price = 0.0;
        req.strategy_tag = "jsonl smoke \"quote\" test";
        store.order(req);

        OrderExecution exec;
        exec.client_order_id = 42;
        exec.broker_order_id = "PAPER-42";
        exec.symbol = "BTCUSDT";
        exec.side = Side::BUY;
        exec.status = OrderStatus::FILLED;
        exec.requested_quantity = 1.25;
        exec.filled_quantity = 1.25;
        exec.remaining_quantity = 0.0;
        exec.fill_price = 100.5;
        exec.avg_fill_price = 100.5;
        exec.commission = 0.01;
        exec.exchange_ts_ns = 1000;
        exec.ack_ts_ns = 1100;
        exec.message = "filled with newline\nand tab\tchars";
        store.execution(exec);
    }

    const auto lines = read_lines(path);
    assert(lines.size() >= 20);

    bool saw_order_submit = false;
    bool saw_order_fill = false;
    bool saw_order_event = false;
    bool saw_trade_event = false;
    bool saw_execution_event = false;
    bool saw_portfolio_event = false;
    bool saw_risk_event = false;
    bool saw_analytics_event = false;
    bool saw_latency_event = false;
    bool saw_queue_event = false;
    bool saw_fill_quality_event = false;

    for (const auto& line : lines) {
        assert_basic_jsonl_event_shape(line);
        assert(!contains(line, "filled with newline\n"));
        assert(contains(line, "\\\"quote\\\"") || !contains(line, "jsonl smoke"));
        saw_order_submit = saw_order_submit || contains(line, "\"type\":\"ORDER_SUBMIT\"");
        saw_order_fill = saw_order_fill || contains(line, "\"type\":\"ORDER_FILL\"");
        saw_order_event = saw_order_event || contains(line, "\"type\":\"ORDER_EVENT\"");
        saw_trade_event = saw_trade_event || contains(line, "\"type\":\"TRADE_EVENT\"");
        saw_execution_event = saw_execution_event || contains(line, "\"type\":\"EXECUTION_EVENT\"");
        saw_portfolio_event = saw_portfolio_event || contains(line, "\"type\":\"PORTFOLIO_EVENT\"");
        saw_risk_event = saw_risk_event || contains(line, "\"type\":\"RISK_EVENT\"");
        saw_analytics_event = saw_analytics_event || contains(line, "\"type\":\"ANALYTICS_EVENT\"");
        saw_latency_event = saw_latency_event || contains(line, "\"type\":\"LATENCY_EVENT\"");
        saw_queue_event = saw_queue_event || contains(line, "\"type\":\"QUEUE_EVENT\"");
        saw_fill_quality_event = saw_fill_quality_event || contains(line, "\"type\":\"FILL_QUALITY_EVENT\"");
    }

    assert(saw_order_submit);
    assert(saw_order_fill);
    assert(saw_order_event);
    assert(saw_trade_event);
    assert(saw_execution_event);
    assert(saw_portfolio_event);
    assert(saw_risk_event);
    assert(saw_analytics_event);
    assert(saw_latency_event);
    assert(saw_queue_event);
    assert(saw_fill_quality_event);

    std::filesystem::remove_all(dir);
}

} // namespace

int main() {
    test_eventstore_writes_valid_jsonl_shapes_and_lifecycle_events();
    return 0;
}
