# QuantOS Architecture

- Next.js frontend: strategy builder, backtests, paper trading, journal, analytics, profile/auth.
- FastAPI backend: auth, strategy storage, backtest jobs, live paper orchestration, health/readiness, metrics.
- C++ engine: backtesting and Binance WebSocket paper-trading engine. Live engine is started only by backend when the user clicks Start Live Paper Trading.
- PostgreSQL: production persistence.
- Redis/RQ: background job queue.
- Prometheus/Grafana: monitoring profile.
