@echo off
setlocal
cd /d "%~dp0\.."
if not exist build\Release\prism_live_paper_trading.exe (
  echo Build missing. Run: cmake -S . -B build ^&^& cmake --build build --config Release
  exit /b 1
)
build\Release\prism_live_paper_trading.exe btcusdt --bar-seconds 10 --snapshot-ms 1000 --force-demo-signal
