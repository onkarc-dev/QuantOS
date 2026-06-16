# QuantOS Production Checklist

Implemented in this build:
- Dynamic live setup score from C++ live engine metrics, not user-defined minimum score.
- Clean Quant Coach empty-state when no closed trades exist.
- Raw report artifact file list hidden from UI.
- Multi-symbol historical data shown consistently for selected symbols.
- Email OTP hooks for SMTP production delivery with safe local fallback.
- JWT access tokens, refresh-token rotation, logout token revocation.
- Password reset OTP flow.
- Frontend route guards for protected routes.
- `/health`, `/system/readiness`, `/metrics`, request logging, optional HTTPS enforcement.
- Docker health checks, Prometheus config, and backup/verification scripts.

Before public launch:
1. Set `PRISMFLOW_SECRET_KEY` to a long random value.
2. Configure SMTP/Resend/SendGrid SMTP variables and set `EMAIL_OTP_DEV_RETURN=false`.
3. Put the app behind HTTPS reverse proxy and set `ENFORCE_HTTPS=true`.
4. Run `docker compose up --build` and `python scripts/verify_deployment.py http://127.0.0.1:8000`.
5. Schedule `python scripts/backup_quantos.py` daily or use managed Postgres backups.
