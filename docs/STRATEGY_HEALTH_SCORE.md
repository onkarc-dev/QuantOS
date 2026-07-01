# Strategy Health Score

QuantOS Strategy Health Score is a 0-100 paper/backtest quality score. It is not a promise of profits and must not be used as real-money trading advice.

## Output

- Overall Strategy Health Score: 0-100.
- Sub-scores: Performance, Risk, Execution, Robustness, Discipline.
- Labels: Excellent, Good, Needs more data, Fragile, Do not scale yet.

## Metrics

Performance includes net return, gross return where available, annualized/daily/monthly approximations. Risk includes max drawdown, average drawdown, drawdown duration, volatility, and downside volatility. Risk-adjusted metrics include Sharpe, Sortino, Calmar, profit factor, and recovery factor. Trading quality includes win/loss rate, average winner/loser, expectancy, payoff ratio, and average trade duration when timestamps are available. Execution quality includes turnover, estimated fees, estimated slippage, cost-vs-gross-profit, and fill-delay placeholder. Robustness includes trade-count sufficiency, overfitting warnings, Monte Carlo/walk-forward hooks when enough trades exist, and parameter-sensitivity placeholder. Regime behavior exposes bull/bear/sideways and high/low-volatility placeholders when data allows.

## API

- `GET /coach/{job_id}/strategy-health`
- `GET /analytics/{job_id}/strategy-health`

Both routes are user-scoped through the authenticated job/report ownership checks.
