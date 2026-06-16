# PRISMFlow — Clean Final Build

PRISMFlow is a paper-trading and backtesting research platform for Binance USDT markets.
It is designed for education, strategy research, and simulated execution only.

## What is included

- Next.js frontend
- FastAPI backend
- C++ low-latency engine
- Real Binance WebSocket live paper trading
- Multi-symbol paper trading support
- Real Binance historical data cache for backtesting
- Strategy Builder with user-defined parameters
- Trade Journal with symbol, entry/exit, slippage, R-multiple, result, and exit reason
- Quant Coach rule-based report view
- Analytics and backtest reports

## Safety scope

PRISMFlow is paper/backtest only.

- No real-money trading
- No broker order execution
- No exchange API keys required
- No real order placement

## Supported paper markets

- BTCUSDT
- ETHUSDT
- BNBUSDT
- SOLUSDT
- XRPUSDT
- ADAUSDT
- DOGEUSDT
- AVAXUSDT
- LINKUSDT
- TRXUSDT

## Run locally on Windows

### 1. Backend

Use Python 3.12, not Python 3.13.

```bat
cd C:\Users\Admin\PRISMFlow_phase3_clean_final\apps\api
py -3.12 -m venv venv
venv\Scripts\activate
python --version
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Expected Python version:

```text
Python 3.12.x
```

### 2. Frontend

Open a second CMD:

```bat
cd C:\Users\Admin\PRISMFlow_phase3_clean_final\apps\web
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

### 3. C++ engine

Open Developer Command Prompt for Visual Studio:

```bat
cd C:\Users\Admin\PRISMFlow_phase3_clean_final
cmake -S . -B build
cmake --build build --config Release
dir build\Release\prism_live_paper_trading.exe
```

The live paper engine uses:

```text
build\Release\prism_live_paper_trading.exe
```

## Normal workflow

1. Start backend.
2. Start frontend.
3. Build the C++ engine.
4. Login/register.
5. Open Strategy Builder.
6. Select one, multiple, or all supported symbols.
7. Save strategy.
8. Run backtest or start live paper trading.
9. Use Journal/Analytics/Quant Coach for review.

## Notes

- Live paper trading uses real Binance WebSocket ticks.
- Backtesting uses real Binance historical candles when the data fetch succeeds.
- Historical data may take time on first download and is cached for later use.
- Closed-trade metrics are read from an atomic session snapshot to avoid flickering.
- Price and unrealized PnL are expected to move tick-by-tick.

## Update: Higher-Timeframe EMA Trend Filter

Strategy Builder now includes an optional higher-timeframe EMA trend filter. The default setting is `5m EMA20 > EMA50`, which allows long 15-second breakout/retest entries only when the 5-minute fast EMA is above the slow EMA. Backtest summaries now report whether the filter was enabled and how many setups were rejected by `HTF_EMA_TREND_NOT_BULLISH`.
