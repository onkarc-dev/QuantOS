@echo off
cd /d "%~dp0\..\outputs\prismflow_cpp_heavy\dashboard"
echo Opening PRISMFlow dashboard on http://localhost:8088/
start "" http://localhost:8088/
py -3 -m http.server 8088
if errorlevel 1 python -m http.server 8088
