#pragma once
#include "OrderTypes.hpp"

class IBroker {
public:
    virtual ~IBroker() = default;
    virtual OrderExecution submit_order(const OrderRequest& request, double market_price, uint64_t ts_ns) = 0;
    virtual OrderExecution cancel_order(uint64_t client_order_id, uint64_t ts_ns) {
        OrderExecution e; e.client_order_id = client_order_id; e.exchange_ts_ns = ts_ns; e.status = OrderStatus::CANCELLED; e.message = "cancel acknowledged by generic broker"; return e;
    }
    virtual const char* name() const = 0;
};
