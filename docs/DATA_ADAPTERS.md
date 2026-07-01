# QuantOS Data Adapters

QuantOS uses user-local adapters for market data whenever possible. Cloud APIs should not continuously stream exchange market data and must never receive exchange API keys, broker secrets, or premium-feed credentials.

## Adapter interface

C++ adapters live under `cpp_engine/src/adapters/MarketDataAdapter.hpp` and normalize all sources into:

- `candle`
- `tick`
- `trade`
- `orderbook update` when available
- `heartbeat`
- `error`

## Implemented adapter foundations

- `BinanceWebSocketAdapter`: default local Binance/BTCUSDT source. Real WebSocket networking is enabled only in environments with optional WebSocket dependencies installed.
- `CsvFileAdapter`: local OHLCV replay/backtest source.
- `CustomWebSocketAdapter`: user-owned premium, broker, or custom feed source. Credentials stay in the user's local environment.

## Cloud sync allow-list

The engine bridge accepts only safe telemetry/results: heartbeat, candles, orders, trades, positions, P&L, risk status, and logs. Payloads outside that allow-list are discarded by the bridge service.
