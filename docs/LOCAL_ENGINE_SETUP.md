# Local Engine Setup

QuantOS cloud is intentionally lightweight. Market data WebSockets, paper execution simulation, premium/broker credentials, and heavy low-latency work stay on the user's machine.

## Build

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j2
```

Useful targets:

- `quantos-engine`: local bridge/heartbeat CLI.
- `prism_backtest`: C++ CSV/backtest smoke path.
- `benchmark_engine`: internal engine latency benchmark.
- `prism_cpp_heavy_paper`: local paper engine target available without WebSocket deps.
- `prism_live_paper_trading`: optional, enabled only when `libwebsockets` is installed.

## Connect

1. Sign in to the web app.
2. Open **Engine Connection**.
3. Click **Connect Local Engine** or **Connect BTC Live Feed**.
4. Run the displayed local command:

```bash
quantos-engine --token <TOKEN> --mode paper --exchange binance --symbol BTCUSDT
```

The UI shows connected/disconnected state, exchange/source, mode, last heartbeat, engine version, latest price, and p50/p95/p99 internal latency.

## Safe sync contract

The local engine may sync only safe events/results: heartbeat, candles, orders, trades, positions, P&L, risk status, and logs. API keys, broker secrets, and premium data-feed credentials must never be sent to QuantOS cloud.

## Local WebSocket capture/backtest

When `libwebsockets` is available, the local engine can capture candles/ticks from Binance or custom feeds. Users save/download captured data locally, then run it through `prism_backtest` or CSV upload. The backend must not continuously stream exchange market data.

## Data adapters

- `BinanceWebSocketAdapter`: local Binance BTCUSDT/crypto WebSocket source.
- `CsvFileAdapter`: local OHLCV replay/backtest source.
- `CustomWebSocketAdapter`: user-owned premium/broker/custom feed source.

All adapters normalize to candle, tick, orderbook update, trade, heartbeat, or error events.
