# Backtesting Data Sources

## Active path

QuantOS uses a hybrid path: cloud/API validates inputs, orchestrates jobs, and stores reports; `prism_backtest` is the C++ release backtest binary when available. Lightweight Python service code supports validation, upload smoke metrics, and report shaping.

## CSV upload mode

CSV files must include: `timestamp, open, high, low, close, volume`. The upload endpoint rejects missing columns, malformed numeric OHLCV values, empty files, and files larger than 10 MB for closed beta. Results include rows, first/last timestamps, win rate, profit factor, gross P&L points, `performance_and_robustness`, and an export JSON path.

CSV upload mode does not know the user's intended entries, stops, capital, or notional unless those are supplied by a richer engine report. For CSV smoke metrics, close-to-close point changes are used as an R proxy and the response includes a calculation note. Ratio metrics return `null` when exact calculation is not supported by available data.

Multi-symbol backtests use the selected real-data symbols and can take longer than a BTC-only run. The current UI reports job-level progress and avoids duplicate submissions; it does not fake per-symbol completions unless the backend exposes them.

## Local WebSocket capture/download mode

The local engine captures candle/tick data from user-owned sources. Captured data can be saved/downloaded locally and then replayed/backtested. The cloud backend must not continuously stream market data.

## Costs and health metrics

Strategy health scoring includes net return, annualized/monthly/daily return approximations, max/average drawdown, drawdown duration, volatility, downside volatility, VaR/CVaR, Sharpe, Sortino, Calmar, Omega, win/loss rate, average winner/loser, profit factor, recovery factor, expectancy, payoff ratio, average trade duration when available, turnover, estimated fees, estimated slippage, cost-vs-gross-profit, trade-count sufficiency warnings, overfitting warnings, and placeholders for parameter sensitivity and walk-forward/out-of-sample.

Turnover is estimated when full notional data is unavailable and is displayed in the UI as a percentage estimate through `turnover_display`. Overfit risk is heuristic and not a guarantee; HIGH can be triggered by too few trades, too short a test range, extreme profit factor, high drawdown, high turnover, or one-day/high-frequency results. MEDIUM is expected when enough trades exist but no walk-forward or out-of-sample validation exists. LOW is reserved for sufficient trades with validation evidence. Walk-forward, out-of-sample validation, and parameter sensitivity remain placeholders until implemented. Real-money trading remains disabled.
