# Charting

QuantOS uses user-owned local-engine, CSV, and backtest candle/trade data only. It does not use paid TradingView widgets or paid/private TradingView market data.

## Active library

QuantOS now uses the official open-source TradingView Lightweight Charts package:

- package: `lightweight-charts`
- license: Apache-2.0
- component: `apps/web/components/TradingChart.tsx`

The reusable chart component renders candlesticks through `lightweight-charts`. The old canvas renderer is no longer the primary chart path.

## Supported overlays

- Candlesticks from local engine, CSV upload, or backtest data.
- Buy/sell markers.
- Stop-loss line.
- Target lines.
- Paper trade overlays through marker/line props.
- Backtest replay markers when timestamps are available.

## Pages using the chart

- `/charting`
- `/backtests`
- `/paper-trading`

## Safety

Charting remains paper/backtest-only. It must not imply financial advice, live broker execution, or real-money trading.
