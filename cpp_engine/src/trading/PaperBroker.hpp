#pragma once
#include "IBroker.hpp"
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
        OrderExecution e;
        e.client_order_id = request.client_order_id;
        e.broker_order_id = "PAPER-" + std::to_string(next_broker_id_.fetch_add(1));
        e.symbol = request.symbol;
        e.side = request.side;
        e.requested_quantity = request.quantity;
        e.exchange_ts_ns = ts_ns;
        if (market_price <= 0.0 || request.quantity <= 0.0) {
            e.status = OrderStatus::REJECTED;
            e.message = "invalid market price or quantity";
        } else {
            const double direction = request.side == Side::BUY ? 1.0 : -1.0;
            e.status = OrderStatus::FILLED;
            e.filled_quantity = request.quantity;
            e.fill_price = market_price * (1.0 + direction * slippage_bps_ / 10000.0);
            e.commission = std::abs(e.fill_price * e.filled_quantity) * commission_bps_ / 10000.0;
            e.message = "simulated immediate fill with commission and slippage";
        }
        if (store_) store_->execution(e);
        return e;
    }

    OrderExecution cancel_order(uint64_t client_order_id, uint64_t ts_ns) override {
        OrderExecution e;
        e.client_order_id = client_order_id;
        e.exchange_ts_ns = ts_ns;
        e.status = OrderStatus::CANCELLED;
        e.message = "paper cancel acknowledged";
        if (store_) store_->execution(e);
        return e;
    }

    const char* name() const override { return "PaperBroker"; }

private:
    EventStore* store_ = nullptr;
    double commission_bps_ = 1.0;
    double slippage_bps_ = 0.5;
    std::atomic<uint64_t> next_broker_id_{1};
};
