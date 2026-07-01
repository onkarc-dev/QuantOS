# QuantOS Data Adapters

QuantOS uses user-local adapters for market data whenever possible. Cloud APIs must not continuously stream exchange market data and must never receive exchange API keys, broker secrets, or premium-feed credentials.

## Adapter interface

C++ adapters live under `cpp_engine/src/adapters/MarketDataAdapter.hpp` and normalize sources into:

- candle
- tick
- trade
- orderbook update
- heartbeat
- error

## Implemented foundations

- `BinanceWebSocketAdapter`: exposes the Binance public trade WebSocket URL, normalizes the symbol, and parses Binance public `@trade` JSON payloads into normalized tick/trade events.
- `CsvFileAdapter`: local OHLCV replay/backtest source foundation.
- `CustomWebSocketAdapter`: user-owned premium, broker, or custom feed foundation. Credentials stay on the user's local machine.

## Binance scope

The Binance adapter foundation is available for public feed data. Live paper uses Binance public trade data only and remains paper-only. The cloud must not receive Binance API keys, broker credentials, or private account data.

The backend can launch the local C++ live paper binary from Windows paths such as `build\Release\prism_live_paper_trading.exe` or Linux/Docker paths such as `/app/build/Release/prism_live_paper_trading`. The process reports safe local telemetry through parseable stdout heartbeats.

## Cloud sync allow-list

The engine bridge accepts only safe telemetry/results:

- heartbeat
- candles
- orders
- trades
- positions
- P&L
- risk status
- logs
- live paper heartbeat fields: selected symbol, latest price, paper equity, cash, unrealized P&L, open position quantity, trade count, and latency

Payloads outside that allow-list are discarded by the bridge service.

## Trading safety

Real-money trading is disabled. QuantOS remains paper trading and backtesting only. No real broker orders are placed.
