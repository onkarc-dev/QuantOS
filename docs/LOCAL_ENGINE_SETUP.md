# Local Engine Setup

QuantOS keeps market data adapters, paper execution simulation, premium/broker credentials, and heavy low-latency work on the user's machine.

## Build

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j2
ctest --test-dir build -C Release --output-on-failure
```

Current local result: C++ configure/build passed and `ctest` passed 6/6.

## Useful targets

- `quantos-engine`: local bridge/heartbeat CLI.
- `prism_backtest`: C++ CSV/backtest path.
- `benchmark_engine`: internal engine latency benchmark.
- `prism_cpp_heavy_paper`: local paper engine target.
- `prism_live_paper_trading`: optional live-paper target when WebSocket dependencies are available.

## Live paper binary paths

The backend detects the live paper binary in these locations:

- Windows release: `build\Release\prism_live_paper_trading.exe`
- Windows fallback: `build\prism_live_paper_trading.exe`
- Linux/Docker release: `/app/build/Release/prism_live_paper_trading`
- Linux local release: `build/Release/prism_live_paper_trading`
- Linux local fallback: `build/prism_live_paper_trading`

If the binary is missing, the API returns the resolved repo root, every checked path, and the build command:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release --target prism_live_paper_trading
```

## Connect

1. Sign in to the web app.
2. Open **Engine Connection**.
3. Click the local engine connect action.
4. Run the displayed command:

```bash
build\Release\quantos-engine.exe --token <TOKEN> --mode paper --exchange binance --symbol BTCUSDT
```

Linux/macOS/Docker:

```bash
./build/quantos-engine --token <TOKEN> --mode paper --exchange binance --symbol BTCUSDT
```

The UI shows connected/disconnected state, exchange/source, mode, last heartbeat, engine version, latest price, and p50/p95/p99 internal latency.

The Paper Trading page starts `prism_live_paper_trading` through the backend in managed paper mode. The C++ process may emit safe lines like `QUANTOS_HEARTBEAT {...}` with symbol, latest price, equity, cash, unrealized P&L, position quantity, trade count, latency, and feed status. Secrets are never included.

## Safe sync contract

The local engine may sync only safe events/results: heartbeat, candles, orders, trades, positions, P&L, risk status, and logs. API keys, broker secrets, and premium data-feed credentials must never be sent to QuantOS cloud.

## Binance adapter foundation

`BinanceWebSocketAdapter` includes the Binance public trade WebSocket URL and parser/local ingestion foundation for public `@trade` messages. Full adapter-owned network socket streaming remains partial and should not be described as complete.

## Real-money trading

Real-money trading is disabled. QuantOS local engine workflows are paper/backtest only.
