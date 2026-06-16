# PRISMFlow Final Cleanup Report

## Cleanup completed

This clean build removes old phase reports, duplicate documentation, temporary files, cache files, generated database files, and old project artifacts.

## Removed from root

- Phase 1/2/3 progress reports
- Old upgrade reports
- Old scorecards
- Duplicate run guides
- Backup CMake files
- Python cache files
- TypeScript build cache
- Local SQLite database files
- Old generated outputs
- Old standalone producer/consumer Python demo folders
- Large docs/archive materials not needed for running the app

## Kept because required

- `apps/api` — FastAPI backend
- `apps/web` — Next.js frontend
- `cpp_engine` — C++ backtest/live paper engine
- `config` and `configs` — strategy/config samples
- `data` — sample/local data area
- `proto` — optional Kafka/protobuf build support
- `scripts` — useful local run/diagnostic scripts
- `tests` — test suite
- `CMakeLists.txt` — C++ build definition
- `Dockerfile.api`, `Dockerfile.web`, `docker-compose.yml` — single Docker stack
- `.env.example` — environment template
- `README.md` — final run guide
- `REPORT.md` — this cleanup report

## Current product capabilities

- Multi-symbol Strategy Builder
- Select one, multiple, or all 10 Binance USDT markets
- Real WebSocket live paper trading
- One C++ paper engine per active symbol
- Professional Trade Journal with symbol, slippage, result, R, stop, and targets
- Multi-position panel instead of raw JSON
- Session reports after Stop & Exit
- Clean Quant Coach, Analytics, and Backtest views
- Green/red/white result coloring
- Atomic closed-trade metrics snapshot

## Important runtime note

The ZIP is clean and does not include build outputs, virtual environments, node_modules, local databases, or generated session outputs.
These are intentionally regenerated locally when you run the project.

## Update: Higher-Timeframe EMA Trend Filter

Strategy Builder now includes an optional higher-timeframe EMA trend filter. The default setting is `5m EMA20 > EMA50`, which allows long 15-second breakout/retest entries only when the 5-minute fast EMA is above the slow EMA. Backtest summaries now report whether the filter was enabled and how many setups were rejected by `HTF_EMA_TREND_NOT_BULLISH`.

## Final Paper-Trading Accounting UI Fix

Updated the Paper Trading page to avoid balance confusion:

- Renamed **Virtual balance** to **Account equity**.
- Added separate **Cash balance** card.
- Accounting model is now explicit:
  - `Cash balance = Starting balance + Realized PnL`
  - `Account equity = Cash balance + Unrealized PnL`
- Kept backend `current_balance` for compatibility, but it now also returns explicit `account_equity` and `cash_balance` fields.
- Updated live execution explanation text so users understand why equity moves every tick while closed-trade metrics update only after C++ ledger close events.
