#pragma once
#include "IBroker.hpp"
#include <cstdlib>
#include <string>

// Safe real-broker integration seam. This keeps production API design in place without risking live money.
// Replace this with REST/FIX/private-WebSocket logic only after credentials, compliance and kill-switches are approved.
class BrokerAdapterStub final : public IBroker {
public:
    OrderExecution submit_order(const OrderRequest& request, double, uint64_t ts_ns) override {
        OrderExecution e;
        e.client_order_id = request.client_order_id;
        e.symbol = request.symbol;
        e.side = request.side;
        e.requested_quantity = request.quantity;
        e.exchange_ts_ns = ts_ns;
        e.status = OrderStatus::REJECTED;
        e.message = "LIVE_BROKER_DISABLED: set up a concrete adapter such as BinanceFuturesBroker/IBKRBroker/ZerodhaBroker after approval";
        return e;
    }
    const char* name() const override { return "BrokerAdapterStub"; }
};
