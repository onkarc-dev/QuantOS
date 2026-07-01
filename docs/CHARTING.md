# Charting

QuantOS uses user-owned/local-engine/CSV/backtest candle and trade data only. It must not use paid TradingView widgets or paid/private TradingView market data.

## Library direction and license

Target dependency: official open-source TradingView Lightweight Charts (`lightweight-charts`) from GitHub/npm. Lightweight Charts is Apache-2.0 licensed, which is compatible with QuantOS closed-beta SaaS usage when notices/license terms are respected.

In this validation environment, `npm install lightweight-charts` is blocked by registry/proxy HTTP 403. Until the dependency can be installed, QuantOS provides `apps/web/components/TradingChart.tsx`, a reusable canvas fallback with the same product data contract: candles, real-time updates via prop changes, buy/sell markers, stop line, target lines, paper overlays, and replay markers.

## Required overlays

- Candlesticks from local engine, CSV upload, or backtest data.
- Buy/sell markers.
- Stop-loss line.
- Target 1 and Target 2 lines.
- Paper trade overlays.
- Backtest replay markers when timestamps are available.
