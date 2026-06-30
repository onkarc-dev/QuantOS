# QuantOS Production Deployment Checklist

## Pre-deployment
- Generate a strong PRISMFLOW_SECRET_KEY (>=32 random bytes).
- Configure PostgreSQL and Redis.
- Configure SMTP and disable EMAIL_OTP_DEV_RETURN.
- Set production CORS origins.
- Build Docker images successfully.

## Deployment
- Run `docker compose up -d --build`.
- Verify API `/health` returns HTTP 200.
- Verify frontend loads.
- Verify worker connects to Redis.
- Verify PostgreSQL schema initializes.

## Persistence
- Confirm PostgreSQL volume persists restart.
- Confirm outputs volume persists reports/logs.

## Recovery
- Restart API container and verify health.
- Restart worker and verify queue resumes.
- Restart database and verify reconnect.

## Security
- HTTPS terminated by reverse proxy.
- Secrets supplied via environment or secret manager.
- No development OTP mode.
- Verify JWT secret is not default.

## Operations
- Verify Prometheus/Grafana (production profile).
- Check API and worker logs.
- Validate backup procedure.
- Record deployed commit SHA.

## Rollback
- Keep previous image tags.
- Restore previous compose deployment.
- Validate `/health` after rollback.
