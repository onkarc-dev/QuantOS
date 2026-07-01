# Strategy Health Score

QuantOS Strategy Health Score is a 0-100 paper/backtest quality score. It is not a promise of profits and must not be used as real-money trading advice.

## Output

- Overall Strategy Health Score: 0-100.
- Sub-scores: Performance, Risk, Execution, Robustness, Discipline.
- Labels: Excellent, Good, Needs more data, Fragile, Do not scale yet.

## Metrics

Performance includes net return, gross return where available, annualized/daily/monthly approximations. Risk includes max drawdown, average drawdown, drawdown duration, volatility, and downside volatility. Risk-adjusted metrics include Sharpe, Sortino, Calmar, profit factor, and recovery factor. Trading quality includes win/loss rate, average winner/loser, expectancy, payoff ratio, and average trade duration when timestamps are available. Execution quality includes turnover, estimated fees, estimated slippage, cost-vs-gross-profit, and fill-delay placeholder. Robustness includes trade-count sufficiency, overfitting warnings, Monte Carlo/walk-forward hooks when enough trades exist, and parameter-sensitivity placeholder. Regime behavior exposes bull/bear/sideways and high/low-volatility placeholders when data allows.

Backtest reports and Strategy Health also expose `performance_and_robustness`:

- Risk-adjusted: Sharpe, Sortino, Calmar, Omega, Recovery Factor.
- Expectancy: expectancy R/trade, average winner/loser R, payoff ratio, largest winner/loser R.
- Risk: max/average drawdown R, drawdown duration, consecutive win/loss streaks, Ulcer Index.
- Trading behavior: trades/day, turnover raw estimate, turnover percentage estimate, formatted turnover display, exposure estimate/percentage, average/median holding bars.
- Robustness: trade-count warning, overfitting risk label and 0-100 score, parameter-sensitivity placeholder, walk-forward placeholder, and out-of-sample placeholder.

Sharpe, Sortino, and Calmar are available when enough R-multiple and drawdown dispersion exists; otherwise they return `null` rather than `0`. Turnover is estimated from notional data when present, and from trade count/holding bars when full notional data is unavailable. The API exposes `turnover_raw`, `turnover_percentage`, and `turnover_display`; frontend pages show `turnover_display` instead of raw numbers. Overfitting risk is heuristic and not a guarantee. LOW risk is not assigned unless sufficient trades and validation evidence exist. Walk-forward, out-of-sample validation, and parameter sensitivity remain placeholders until implemented. Real-money trading remains disabled.

## API

- `GET /coach/{job_id}/strategy-health`
- `GET /analytics/{job_id}/strategy-health`

Both routes are user-scoped through the authenticated job/report ownership checks.
