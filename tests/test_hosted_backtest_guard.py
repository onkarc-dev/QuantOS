import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
os.environ.setdefault("PRISMFLOW_SECRET_KEY", "unit-test-secret-key-with-enough-length")

from app.routes.jobs import BacktestPayload, HOSTED_HEAVY_BACKTEST_MESSAGE, heavy_backtest_reason


def test_production_heavy_backtest_guard_blocks_multi_symbol_low_timeframe_shape():
    payload = BacktestPayload(
        strategy_id="s",
        symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"],
        timeframe="5s",
        start_date="2026-06-01",
        end_date="2026-06-02",
        config={},
    )

    assert heavy_backtest_reason(payload) == HOSTED_HEAVY_BACKTEST_MESSAGE


def test_production_heavy_backtest_guard_allows_light_shape():
    payload = BacktestPayload(
        strategy_id="s",
        symbols=["BTCUSDT", "ETHUSDT"],
        timeframe="1m",
        start_date="2026-06-01",
        end_date="2026-06-02",
        config={},
    )

    assert heavy_backtest_reason(payload) is None
