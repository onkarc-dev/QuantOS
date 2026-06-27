#include "execution/ExchangeSimulator.hpp"

#include <cmath>
#include <iostream>
#include <string>

using quantos::execution::ExchangeSimulator;
using quantos::execution::SimulatorConfig;

namespace {

int failures = 0;

void check(bool condition, const std::string& name) {
    if (condition) {
        std::cout << "[PASS] " << name << "\n";
    } else {
        std::cout << "[FAIL] " << name << "\n";
        ++failures;
    }
}

OrderRequest base_order() {
    OrderRequest o;
    o.client_order_id = 1;
    o.symbol = "BTCUSDT";
    o.quantity = 1.0;
    o.side = Side::BUY;
    o.type = OrderType::MARKET;
    o.time_in_force = TimeInForce::GTC;
    return o;
}

} // namespace

int main() {
    SimulatorConfig cfg;
    cfg.random_latency_min_ns = 0;
    cfg.random_latency_max_ns = 0;
    cfg.visible_liquidity_qty = 10.0;
    cfg.spread_bps = 2.0;
    cfg.slippage_bps = 0.5;
    cfg.random_seed = 7;

    ExchangeSimulator sim(cfg);

    {
        auto o = base_order();
        auto r = sim.execute(o, 100.0, 1000);
        check(r.execution.status == OrderStatus::FILLED, "market order fills");
        check(r.execution.filled_quantity == 1.0, "market fill quantity");
        check(r.execution.fill_price > 100.0, "buy market pays ask plus slippage");
        check(r.trade_event && r.portfolio_event && r.fill_quality_event, "market fill emits events");
    }

    {
        auto o = base_order();
        o.type = OrderType::LIMIT;
        o.limit_price = 100.02;
        auto r = sim.execute(o, 100.0, 2000);
        check(r.execution.status == OrderStatus::FILLED, "marketable limit fills");
    }

    {
        auto o = base_order();
        o.type = OrderType::LIMIT;
        o.limit_price = 99.0;
        o.time_in_force = TimeInForce::GTC;
        auto r = sim.execute(o, 100.0, 3000);
        check(r.execution.status == OrderStatus::ACCEPTED, "non-marketable limit rests");
        check(r.execution.filled_quantity == 0.0, "resting limit has no fill");
    }

    {
        auto o = base_order();
        o.type = OrderType::LIMIT;
        o.limit_price = 100.02;
        o.post_only = true;
        auto r = sim.execute(o, 100.0, 4000);
        check(r.execution.status == OrderStatus::REJECTED, "post-only crossing rejected");
    }

    {
        auto o = base_order();
        o.quantity = 20.0;
        o.time_in_force = TimeInForce::FOK;
        auto r = sim.execute(o, 100.0, 5000);
        check(r.execution.status == OrderStatus::EXPIRED, "FOK expires on insufficient liquidity");
    }

    {
        auto o = base_order();
        o.quantity = 20.0;
        o.time_in_force = TimeInForce::IOC;
        auto r = sim.execute(o, 100.0, 6000);
        check(r.execution.status == OrderStatus::PARTIALLY_FILLED, "IOC partially fills available liquidity");
        check(std::abs(r.execution.filled_quantity - cfg.visible_liquidity_qty) < 1e-12, "partial fill equals visible liquidity");
    }

    {
        auto o = base_order();
        o.type = OrderType::STOP;
        o.stop_price = 101.0;
        auto r = sim.execute(o, 100.0, 7000);
        check(r.execution.status == OrderStatus::ACCEPTED, "untriggered stop accepted");
    }

    {
        SimulatorConfig halted_cfg = cfg;
        halted_cfg.trading_halted = true;
        ExchangeSimulator halted(halted_cfg);
        auto o = base_order();
        auto r = halted.execute(o, 100.0, 8000);
        check(r.execution.status == OrderStatus::REJECTED, "halted market rejects orders");
    }

    std::cout << "exchange_simulator_tests failures=" << failures << "\n";
    return failures == 0 ? 0 : 1;
}
