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

The Binance adapter foundation is available, but full adapter-owned network streaming is not claimed yet. The current implementation provides the public URL and trade parser/local ingestion foundation. Real socket-loop capture remains partial.

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

Payloads outside that allow-list are discarded by the bridge service.

## Trading safety

Real-money trading is disabled. QuantOS remains paper trading and backtesting only.
