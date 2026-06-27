# QuantOS Exchange Simulator Architecture

## Goal

Add a professional paper-execution simulator to QuantOS without redesigning the platform.

## Placement

```text
Strategy Signal
  -> RiskManager
  -> PaperBroker
  -> ExchangeSimulator
      -> latency model
      -> session and halt checks
      -> spread, slippage and liquidity model
      -> queue delay model
      -> matching-engine hook point
      -> execution quality metrics
  -> EventStore
  -> Portfolio
  -> Dashboard / Analytics
```

## New module

```text
cpp_engine/src/execution/ExchangeSimulator.hpp
```

The module is header-only to match the current C++ style.

## Responsibilities

The simulator handles network latency, gateway latency, exchange latency, acknowledgement delay, random latency, configurable latency, spread, slippage, queue delay, order rejection, liquidity exhaustion, market impact, partial fills, trading halts, session open/close, auction hooks, latency metrics, queue metrics, execution metrics and fill-quality metrics.

## Compatibility

The existing broker API remains valid:

```cpp
submit_order(const OrderRequest& request, double market_price, uint64_t ts_ns)
```

Existing strategy and paper-trading code can continue passing a reference market price. The simulator derives a paper top-of-book around that price unless a richer book snapshot is supplied later.

## Event model

For simulated orders and fills, the broker emits JSONL events:

- ORDER_SUBMIT
- ORDER_ACK
- EXECUTION_EVENT
- ORDER_FILL
- TRADE_EVENT
- PORTFOLIO_EVENT
- RISK_EVENT
- ANALYTICS_EVENT
- LATENCY_EVENT
- QUEUE_EVENT
- FILL_QUALITY_EVENT

The original EventStore execution path remains in place for dashboard compatibility.

## Latency model

Total simulated latency is:

```text
network + gateway + exchange + acknowledgement + queue + random
```

The random component is seedable for reproducible tests.

## Execution model

The simulator estimates spread-adjusted price, configured slippage, queue delay, size-based market impact, partial fill ratio, rejection probability, halt/session rejection, IOC expiry and FOK expiry.

## Metrics

The simulator tracks p50/p95/p99/max latency, accepted/rejected/expired counts, fill rate, partial-fill count, average slippage bps, market-impact bps, queue delay and fill ratio.

## Tests

Tests live in:

```text
cpp_engine/tests/test_exchange_simulator.cpp
```
