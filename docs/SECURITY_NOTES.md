# QuantOS Security Notes

QuantOS is paper/backtest only. Do not add real-money execution without a separate security/design review.

## Secrets and market data

- Exchange API keys, broker secrets, and premium-feed credentials must remain on the user's local machine.
- The local engine bridge stores token hashes, not raw engine tokens.
- The heartbeat bridge allow-lists only safe telemetry/results: heartbeat, candles, orders, trades, positions, P&L, risk status, and logs.
- Frontend env variables must remain `NEXT_PUBLIC_*` only for public API base URLs; never expose broker/exchange secrets in the frontend.

## Ownership checks

- Strategies, jobs, reports, journal entries, live sessions, and engine status routes should be scoped to the authenticated user.
- `coach/{job_id}/strengths-weaknesses` now filters reports by `job_id` and `user_id`.
- Journal entry creation now verifies referenced `job_id` and `trade_id` belong to the current user before insertion.
- CSV uploads are written under `outputs/csv_uploads/<user_id>` and normalized filenames are generated server-side to avoid path traversal.

## CSV validation

- Upload limit is 10 MB for closed beta.
- Required columns are `timestamp, open, high, low, close, volume` with safe aliases.
- Numeric OHLCV values are parsed and invalid rows are rejected with clear errors.

## Production hardening

- `PRISMFLOW_SECRET_KEY` is required and length-checked when `ENV=production`.
- Wildcard CORS is rejected in production by settings validation.
- HTTPS enforcement is available through `ENFORCE_HTTPS=true` behind a proxy.
- Basic security headers are set in the request middleware.

## Remaining security work

- In-app per-IP rate limiting is available through `RATE_LIMIT_PER_MINUTE`; production should still prefer Redis/proxy-backed distributed limits.
- Run full FastAPI integration tests once package installation is available.
- Add migration tooling for Postgres schema changes before a broader beta.
