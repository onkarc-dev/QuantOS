# QuantOS Test Results

Date: 2026-07-01.

## Passing local checks

| Area | Command | Result |
|---|---|---|
| Frontend clean install | `cd apps/web && npm ci` | PASS |
| Frontend typecheck | `cd apps/web && npm test` | PASS |
| Frontend production build | `cd apps/web && npm run build` | PASS |
| Backend venv | `cd apps/api && py -3.12 -m venv .venv` | PASS |
| Backend tooling | `python -m pip install --upgrade pip setuptools wheel` | PASS |
| Backend dependencies | `pip install -r requirements.txt` | PASS |
| Backend tests | `python -m pytest ..\..\tests tests` | PASS, 97 tests |
| C++ configure | `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release` | PASS |
| C++ build | `cmake --build build --config Release -j2` | PASS |
| C++ tests | `ctest --test-dir build -C Release --output-on-failure` | PASS, 6/6 |
| Full backend smoke | `python scripts\smoke_quantos.py` | PASS |

## Smoke coverage

`scripts/smoke_quantos.py` validates:

- `/health`
- `/version`
- registration OTP generation
- registration verification
- login
- strategy creation
- `/backtests/upload-csv` using `data/sample_market_data.csv`
- strategy health score through Quant Coach
- `performance_and_robustness` existence after CSV upload/backtest
- overfitting risk, Sharpe/Sortino/Calmar keys, and warnings list
- AI explainer fallback
- `/engine/token`
- `/engine/heartbeat`
- `/engine/status`
- live paper binary path resolution for Windows and Linux-style paths
- missing live paper binary diagnostics with checked paths and build command
- C++ `QUANTOS_HEARTBEAT` parser
- duplicate live paper process prevention and stop behavior

The script prints clear `PASS`/`FAIL` lines for each step.

## Notes

- `lightweight-charts` is installed and active.
- Canvas fallback is no longer the primary chart implementation.
- Binance adapter foundation includes public trade parsing and the Binance public trade WebSocket URL.
- Full adapter-owned live socket loop is still partial.
- Real-money trading remains disabled.
- Live paper local-engine integration supports Windows and Linux/Docker binary paths and remains paper-only with no real broker orders.
- Backtest metrics now cover Sharpe, Sortino, Calmar, Recovery Factor, expectancy, estimated turnover, and overfitting risk. Ratio values are `null` when the available R-multiple data is insufficient.
- Walk-forward and out-of-sample validation are placeholders until implemented.
