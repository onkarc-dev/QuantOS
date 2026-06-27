#pragma once

#include "IBroker.hpp"
#include "MatchingEngine.hpp"
#include "../storage/EventStore.hpp"

#include <atomic>
#include <cmath>
#include <string>

class PaperBroker final : public IBroker {
public:
    explicit PaperBroker(EventStore* store = nullptr, double commission_bps = 1.0, double slippage_bps = 0.5)
        : store_(store), commission_bps_(commission_bps), slippage_bps_(slippage_bps) {}

    OrderExecution submit_order(const OrderRequest& request, double market_price, uint64_t ts_ns) override {
        if (store_) store_->order(request);

        if (market_price <= 0.0 || request.quantity <= 0.0) {
            OrderExecution rejected = make_rejection(request, ts_ns, "invalid market price or quantity");
            publish_execution(rejected);
            return rejected;
        }

        seed_market_liquidity_if_needed(request, market_price, ts_ns);

        auto result = engine_.submit_order(request, ts_ns);
        OrderExecution execution = result.execution;
        execution.broker_order_id = broker_order_id(request.client_order_id);
        apply_broker_costs(execution);

        if (execution.message.empty()) execution.message = "paper order routed through matching engine";
        publish_reports(result, execution.broker_order_id);
        publish_execution(execution);
        return execution;
    }

    OrderExecution cancel_order(uint64_t client_order_id, uint64_t ts_ns) override {
        auto result = engine_.cancel_order_report(client_order_id, ts_ns);
        OrderExecution execution = result.execution;
        execution.broker_order_id = broker_order_id(client_order_id);
        if (execution.message.empty()) execution.message = "paper cancel routed through matching engine";
        publish_reports(result, execution.broker_order_id);
        publish_execution(execution);
        return execution;
    }

    void seed_liquidity(const std::string& symbol, Side side, double quantity, double price, uint64_t ts_ns = 0) {
        if (quantity <= 0.0 || price <= 0.0) return;
        OrderRequest req;
        req.client_order_id = next_liquidity_order_id_.fetch_add(1);
        req.symbol = symbol;
        req.side = side;
        req.type = OrderType::LIMIT;
        req.time_in_force = TimeInForce::GTC;
        req.quantity = quantity;
        req.limit_price = price;
        req.strategy_tag = "PAPER_LIQUIDITY";
        engine_.submit_order(req, ts_ns);
    }

    const char* name() const override { return "PaperBroker"; }

private:
    static bool is_marketable_strategy_order(const OrderRequest& request) {
        return request.type == OrderType::MARKET;
    }

    void seed_market_liquidity_if_needed(const OrderRequest& request, double market_price, uint64_t ts_ns) {
        if (!is_marketable_strategy_order(request)) return;
        const Side contra_side = request.side == Side::BUY ? Side::SELL : Side::BUY;
        const double direction = request.side == Side::BUY ? 1.0 : -1.0;
        const double simulated_price = market_price * (1.0 + direction * slippage_bps_ / 10000.0);
        seed_liquidity(request.symbol, contra_side, request.quantity, simulated_price, ts_ns);
    }

    static std::string broker_order_id(uint64_t client_order_id) {
        return "PAPER-" + std::to_string(client_order_id);
    }

    OrderExecution make_rejection(const OrderRequest& request, uint64_t ts_ns, const std::string& message) const {
        OrderExecution e;
        e.client_order_id = request.client_order_id;
        e.broker_order_id = broker_order_id(request.client_order_id);
        e.symbol = request.symbol;
        e.side = request.side;
        e.status = OrderStatus::REJECTED;
        e.requested_quantity = request.quantity;
        e.remaining_quantity = request.quantity;
        e.exchange_ts_ns = ts_ns;
        e.ack_ts_ns = ts_ns;
        e.message = message;
        return e;
    }

    void apply_broker_costs(OrderExecution& execution) const {
        if (execution.filled_quantity <= 0.0 || execution.avg_fill_price <= 0.0) return;
        execution.fill_price = execution.avg_fill_price;
        execution.commission = std::abs(execution.fill_price * execution.filled_quantity) * commission_bps_ / 10000.0;
    }

    void publish_reports(const MatchingEngine::MatchResult& result, const std::string& broker_order_id) {
        if (!store_) return;
        for (const auto& report : result.execution_reports) {
            OrderExecution e = report.execution;
            e.broker_order_id = broker_order_id;
            apply_broker_costs(e);
            store_->execution(e);
        }
    }

    void publish_execution(const OrderExecution& execution) {
        if (store_) store_->execution(execution);
    }

    EventStore* store_ = nullptr;
    double commission_bps_ = 1.0;
    double slippage_bps_ = 0.5;
    MatchingEngine engine_;
    std::atomic<uint64_t> next_liquidity_order_id_{900000000000ULL};
};
