# QuantOS Matching Engine Architecture

## Scope

This document defines the in-place QuantOS matching engine upgrade. It does not redesign QuantOS and it does not implement market impact.

The matching engine is a C++ execution simulator that sits between the existing strategy/risk/paper-trading layer and the L2/L3 market-data layer. It keeps existing APIs working while adding exchange-style order lifecycle handling.

## Existing source of truth

QuantOS currently has:

- `PrismLiveEngine` for strategy/candle decisions.
- `RiskManager` for order approval.
- `Portfolio` for fills and ledger updates.
- `PaperBroker` implementing the `IBroker` interface.
- `EventStore` for JSONL order/execution/position/metric events.
- L2/L3 market-data primitives in `cpp_engine/src/order_book.hpp`.

The matching engine integrates into this existing path instead of replacing it.

## New module

```text
cpp_engine/src/matching/MatchingEngine.hpp
```

The module is header-only to match the current QuantOS C++ style and keep CMake integration simple.

## Responsibilities

The matching engine handles:

- FIFO price-time priority.
- Market orders.
- Limit orders.
- Stop orders.
- Stop-limit orders.
- Time-in-force: GTC, IOC, FOK.
- Post-only validation.
- Reduce-only validation hooks.
- Partial fills.
- Multiple fills.
- Cancel.
- Modify.
- Replace.
- Queue-priority behavior.
- Self-trade prevention hook.
- Execution reports.
- Order states: NEW, ACCEPTED, PARTIALLY_FILLED, FILLED, CANCELLED, REJECTED, EXPIRED.

## Non-goals

The matching engine does not implement:

- Market impact.
- Real-money exchange routing.
- Broker API keys.
- Exchange-specific fee tiers.
- Cross-venue smart order routing.

## Data flow

```text
Strategy Signal
    │
    ▼
RiskManager.validate(...)
    │
    ▼
PaperBroker.submit_order(...)
    │
    ▼
MatchingEngine.submit(...)
    │
    ├── Validate order flags
    ├── Trigger stop / stop-limit rules
    ├── Match against opposite book using FIFO price-time priority
    ├── Emit zero or more fills
    ├── Update order state
    └── Return execution reports
    │
    ▼
EventStore
    ├── ORDER_SUBMIT
    ├── RISK_EVENT
    ├── EXECUTION_EVENT
    ├── TRADE_EVENT
    ├── PORTFOLIO_EVENT
    └── ANALYTICS_EVENT
    │
    ▼
Portfolio.apply_fill(...)
```

## Class diagram

```text
IBroker
  ▲
  │
PaperBroker
  ├── EventStore*
  └── MatchingEngine
        ├── MatchingOrder
        ├── MatchingFill
        ├── ExecutionReport
        ├── bid_levels_: map<price, deque<order_id>>
        ├── ask_levels_: map<price, deque<order_id>>
        ├── orders_: unordered_map<order_id, MatchingOrder>
        └── stop_orders_: vector<order_id>
```

## FIFO price-time priority

For each price level, the engine stores order IDs in insertion order. Matching always consumes the front order first. A modify that changes price or increases quantity loses priority and is requeued at the back. A quantity decrease keeps queue position.

## Order compatibility

`OrderTypes.hpp` remains the shared API. Existing fields stay valid:

- `client_order_id`
- `symbol`
- `side`
- `type`
- `quantity`
- `limit_price`
- `strategy_tag`

New optional fields are added for advanced order handling:

- stop price
- time-in-force
- post-only
- reduce-only
- account ID / owner ID for self-trade prevention
- remaining quantity and average fill price in execution responses

Existing code that submits market orders still compiles.

## Event compatibility

Every fill produces the five required event types through `EventStore` helpers:

- `TRADE_EVENT`
- `EXECUTION_EVENT`
- `PORTFOLIO_EVENT`
- `RISK_EVENT`
- `ANALYTICS_EVENT`

The existing `ORDER_FILL` / `ORDER_EXECUTION` events are preserved for current dashboard compatibility.

## Database changes

No database migration is required for this phase because QuantOS already writes JSONL execution events and dashboard snapshots. If/when persisted order books are required, the future DB tables should be:

- `orders`
- `executions`
- `fills`
- `risk_events`
- `portfolio_events`
- `analytics_events`

## Unit tests

Unit tests live in:

```text
cpp_engine/tests/test_matching_engine.cpp
```

They cover:

- FIFO matching.
- Partial fills.
- IOC expiry.
- FOK rejection/expiry behavior.
- Post-only rejection.
- Cancel.
- Modify priority behavior.
- Replace behavior.
- Stop-limit trigger.
- Self-trade prevention hook.

## Performance notes

- Per-price FIFO uses `std::deque<uint64_t>` to avoid moving orders during partial fills.
- Order lookup uses `std::unordered_map<uint64_t, MatchingOrder>`.
- Price levels use sorted maps for best-bid/best-ask access.
- No market impact model is applied.
- No allocation is done during simple fill report construction except vectors used to return reports.
- For production-grade HFT scale, this can later move to fixed-capacity arenas and intrusive lists without changing the public `IBroker` interface.
