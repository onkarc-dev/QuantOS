@echo off
if not exist backups mkdir backups
for /f "tokens=1-4 delims=/ " %%a in ('date /t') do set DATESTAMP=%%d%%b%%c
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set TIMESTAMP=%%a%%b
set OUT=backups\quantos_%DATESTAMP%_%TIMESTAMP%.sql
docker compose exec -T postgres pg_dump -U quantos quantos > %OUT%
echo Backup written: %OUT%
