@echo off
setlocal
cd /d "%~dp0\.."
if not exist build mkdir build
cmake -S . -B build
if errorlevel 1 exit /b 1
cmake --build build --config Release
if errorlevel 1 exit /b 1
build\Release\prism_cpp_heavy_paper.exe --mode paper --symbols btcusdt,ethusdt,solusdt --snapshot-every 10 --force-demo-signal
endlocal
