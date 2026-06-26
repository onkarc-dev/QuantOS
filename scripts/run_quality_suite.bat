@echo off
setlocal enabledelayedexpansion
cd /d %~dp0\..

echo.
echo QuantOS 9.5 Quality Suite
echo ==========================

echo.
echo [1/5] Checking Git branch
git branch --show-current

echo.
echo [2/5] Building C++ engines
cmake -S . -B build
if errorlevel 1 goto fail
cmake --build build --config Release
if errorlevel 1 goto fail

echo.
echo [3/5] Checking frontend dependencies
cd apps\web
if not exist node_modules (
  npm install
  if errorlevel 1 goto fail
)
npm run build
if errorlevel 1 goto fail
cd ..\..

echo.
echo [4/5] Running quality gate
py -3.12 scripts\quality_gate.py
if errorlevel 1 goto fail

echo.
echo [5/5] Quality suite PASSED
echo QuantOS local quality is 9.5+ if all runtime pages also visually verify.
exit /b 0

:fail
echo.
echo Quality suite FAILED. Fix the error above and rerun scripts\run_quality_suite.bat
exit /b 1
