# QuantOS Docker Deployment

## Required production environment
Create `.env` in the project root before public deployment:

```env
ENV=production
POSTGRES_PASSWORD=replace-with-strong-password
PRISMFLOW_SECRET_KEY=replace-with-64-char-random-secret
NEXT_PUBLIC_API_BASE=https://api.yourdomain.com
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
EMAIL_OTP_DEV_RETURN=false
SMTP_HOST=smtp.yourprovider.com
SMTP_PORT=587
SMTP_USER=your-smtp-user
SMTP_PASSWORD=your-smtp-password
SMTP_FROM=no-reply@yourdomain.com
SMTP_TLS=true
ENFORCE_HTTPS=true
```

## Run locally with Docker

```bash
docker compose up --build
```

Open:
- Frontend: http://localhost:3000
- API health: http://localhost:8000/health
- API docs: http://localhost:8000/docs

## Run with monitoring

```bash
docker compose --profile production up --build
```

Open:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001

## Backup

Linux/macOS:
```bash
scripts/backup_postgres.sh
```

Windows CMD:
```bat
scripts\backup_postgres_windows.bat
```
