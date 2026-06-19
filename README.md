# QuantOS — Personal Quant Operating System

QuantOS is a paper-trading, backtesting, analytics, journaling, and trader-coaching platform for Binance USDT markets.

It is designed to help traders become systematic decision makers: define rules, test strategies on historical market data, practice with real-time paper trading, review mistakes, and improve discipline.

QuantOS is research and simulation software only. It does not place real orders and it is not financial advice.

## Product positioning

QuantOS is not trying to be another charting app or another buy/sell signal tool.

It is closer to:

- A personal quant lab for retail traders
- A discipline and performance operating system
- A paper-trading arena with analytics, review, and coaching
- A future platform for weekly trading challenges and trader improvement

## What is included today

- Next.js frontend
- FastAPI backend
- C++ low-latency backtest/live paper engine
- Multi-symbol Binance USDT paper markets
- Real-time Binance WebSocket live paper trading
- Historical market-data cache for user-defined backtests
- Strategy Builder with user-defined parameters
- Trade Journal with symbol, entry/exit, slippage, R-multiple, result, and exit reason
- Quant Coach rule-based report view
- Analytics and backtest reports
- Docker support with API, web, PostgreSQL, Redis worker, Prometheus, and Grafana profiles

## Data model clarity

QuantOS uses different data paths for different modes:

1. Backtesting
   - Uses historical market candles/data.
   - The data can be cached/stored as CSV or structured files after being fetched from market sources.
   - This is for replaying past market behavior against a strategy.

2. Live paper trading
   - Uses real-time Binance WebSocket market ticks.
   - This is paper only: virtual balance, simulated fills, no broker, no real orders.

3. Future analytics data
   - News sentiment, social sentiment, funding rates, open interest, fear/greed, and macro data can be added as optional context layers.
   - These should support risk and regime understanding, not pretend to guarantee market prediction.

## Safety scope

QuantOS is paper/backtest only.

- No real-money trading
- No broker order execution
- No exchange API keys required
- No real order placement
- No leverage recommendation engine
- No guaranteed profit claims

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

## Planned product extensions

### AI Quant Coach

The AI layer should focus on explanation and discipline, not blind buy/sell predictions.

Planned coaching examples:

- Explain why a strategy lost money
- Detect overtrading and revenge trading patterns
- Summarize drawdown behavior
- Suggest what to test next
- Compare strategy performance across market regimes
- Explain whether risk should be reduced after a bad streak

### Better data visualization

Priority visualizations:

- Equity curve
- Drawdown curve
- R-multiple distribution
- Win/loss by symbol
- Setup score over time
- Trade heatmap by session/time
- Expectancy by regime
- Risk-adjusted leaderboard metrics

### Alternative data context

Early-stage free or low-cost data layers:

- Funding rates
- Open interest
- Long/short ratios
- Fear & Greed Index
- Crypto news headlines
- Reddit/social sentiment
- Macro indicators from public datasets

These should be used for context and risk awareness, not guaranteed signals.

### Weekly QuantOS Challenges

A future community feature where traders compete with the same virtual balance, same time window, and fair rules.

The leaderboard should not rank only by return. It should reward risk-adjusted trading:

- Return
- Max drawdown control
- Risk management
- Discipline score
- Rule consistency
- Trade quality

This prevents the platform from encouraging pure gambling.

## Run locally on Windows

### 1. Backend

Use Python 3.12, not Python 3.13.

```bat
cd C:\Users\Admin\QuantOS\apps\api
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
cd C:\Users\Admin\QuantOS\apps\web
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
cd C:\Users\Admin\QuantOS
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
8. Run a backtest on historical market data or start live paper trading with WebSocket data.
9. Use Journal, Analytics, and Quant Coach for review.

## Production-readiness notes

Before public launch, verify:

- CORS allows only the production frontend domain.
- SMTP is configured and `EMAIL_OTP_DEV_RETURN=false`.
- `PRISMFLOW_SECRET_KEY` is replaced with a strong secret.
- PostgreSQL is used instead of local SQLite.
- Redis worker is running for jobs.
- HTTPS is enforced behind the deployment proxy.
- Internal file paths, stdout tails, and raw report paths are not shown to end users.
- Live paper binary works on the actual production host, not only Windows local.

## Higher-Timeframe EMA Trend Filter

Strategy Builder includes an optional higher-timeframe EMA trend filter. The default setting is `5m EMA20 > EMA50`, which allows long 15-second breakout/retest entries only when the 5-minute fast EMA is above the slow EMA. Backtest summaries report whether the filter was enabled and how many setups were rejected by `HTF_EMA_TREND_NOT_BULLISH`.
