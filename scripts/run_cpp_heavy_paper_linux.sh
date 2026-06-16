#!/usr/bin/env bash
set -euo pipefail
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
./build/prism_cpp_heavy_paper --mode paper --symbols btcusdt,ethusdt --data data/sample_market_data.csv --bar-seconds 10
