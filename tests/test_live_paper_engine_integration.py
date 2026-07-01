import os
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
os.environ.setdefault("PRISMFLOW_SECRET_KEY", "unit-test-secret-key-with-enough-length")

from app.db import init_db
from app.services import live_paper
from app.services.live_paper import (
    LivePaperManager,
    LivePaperSession,
    classify_trade_result,
    parse_quantos_heartbeat,
    resolve_live_paper_binary,
    validate_live_start_request,
)


def setup_module(module):
    init_db()


def test_live_binary_resolution_windows_style_path(tmp_path):
    binary = tmp_path / "build" / "Release" / "prism_live_paper_trading.exe"
    binary.parent.mkdir(parents=True)
    binary.write_text("stub", encoding="utf-8")

    out = resolve_live_paper_binary(tmp_path, override="")

    assert out["binary_found"] is True
    assert out["selected_binary_path"] == str(binary)
    assert str(binary) in out["checked_paths"]
    assert out["detected_platform"]


def test_live_binary_resolution_uses_quantos_override(tmp_path, monkeypatch):
    binary = tmp_path / "custom" / "prism_live_paper_trading.exe"
    binary.parent.mkdir(parents=True)
    binary.write_text("stub", encoding="utf-8")
    monkeypatch.setenv("QUANTOS_LIVE_PAPER_BINARY", str(binary))

    out = resolve_live_paper_binary(tmp_path)

    assert out["binary_found"] is True
    assert out["selected_binary_path"] == str(binary)
    assert out["checked_paths"] == [str(binary)]


def test_live_binary_resolution_hides_docker_path_on_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(live_paper.os, "name", "nt")

    out = resolve_live_paper_binary(tmp_path, override="")

    assert not any(path.startswith("/app/build") for path in out["checked_paths"])
    assert any(path.endswith("build\\Release\\prism_live_paper_trading.exe") or path.endswith("build/Release/prism_live_paper_trading.exe") for path in out["checked_paths"])


def test_live_binary_resolution_linux_style_path(tmp_path):
    binary = tmp_path / "build" / "Release" / "prism_live_paper_trading"
    binary.parent.mkdir(parents=True)
    binary.write_text("stub", encoding="utf-8")

    out = resolve_live_paper_binary(tmp_path, override="")

    assert out["binary_found"] is True
    assert out["selected_binary_path"] == str(binary)


def test_missing_binary_error_lists_paths_and_build_command(tmp_path, monkeypatch):
    monkeypatch.setattr(live_paper.settings, "project_root", tmp_path)
    manager = LivePaperManager()

    out = manager.start("missing-binary-user", symbols=["BTCUSDT"])

    assert out["status"] == "disabled"
    assert "Checked paths" in out["error"]
    assert "cmake -S . -B build" in out["error"]
    assert out["binary_diagnostics"]["binary_found"] is False


def test_parse_quantos_heartbeat_safe_json_line():
    out = parse_quantos_heartbeat(
        'QUANTOS_HEARTBEAT {"symbol":"BTCUSDT","latest_price":123.45,"equity":100000,'
        '"cash":99999,"unrealized_pnl":1.5,"position_qty":0,"trades":2,'
        '"p50_latency_us":1,"p95_latency_us":3,"p99_latency_us":5,"mode":"paper"}'
    )

    assert out["symbol"] == "BTCUSDT"
    assert out["latest_price"] == 123.45
    assert out["mode"] == "paper"
    assert "api_key" not in out


def test_live_symbol_guard_blocks_unsafe_1s_multi_symbol(monkeypatch):
    row = {
        "id": "s1",
        "name": "Fast",
        "timeframe": "1s",
        "symbols_json": json.dumps(["BTCUSDT", "ETHUSDT"]),
        "config_json": json.dumps({"bar_seconds": 1, "symbols": ["BTCUSDT", "ETHUSDT"]}),
    }
    monkeypatch.setattr(live_paper, "_strategy_for_user", lambda user_id, strategy_id="": row)

    rejected = validate_live_start_request("guard-user", symbols=["BTCUSDT", "ETHUSDT"])
    accepted = validate_live_start_request("guard-user", symbols=["BTCUSDT"])

    assert rejected["ok"] is False
    assert rejected["status_code"] == 422
    assert "Windows memory/pagefile" in rejected["message"]
    assert accepted["ok"] is True


def test_trade_classification_uses_small_breakeven_epsilon():
    assert classify_trade_result(-1.314) == "LOSS"
    assert classify_trade_result(-0.355) == "LOSS"
    assert classify_trade_result(0.005) == "BREAKEVEN"
    assert classify_trade_result(0.02) == "WIN"


class _LinesProcess:
    def __init__(self, lines):
        self.stdout = iter(lines)

    def poll(self):
        return None


def test_heartbeat_updates_connected_status_open_position_and_candles(monkeypatch):
    manager = LivePaperManager()
    session = LivePaperSession(user_id="parser-user", session_id="1", status="running")
    session.live_config = {"symbols": ["BTCUSDT"], "bar_seconds": 1}
    proc = _LinesProcess([
        'QUANTOS_HEARTBEAT {"symbol":"BTCUSDT","latest_price":101.5,"processed":3,'
        '"bars":2,"signals":1,"trades":0,"equity":100001,"cash":100000,'
        '"realized_pnl":0,"unrealized_pnl":1.25,"position_qty":0.5,'
        '"open_qty":0.5,"open_entry":100,"open_stop":99,"target1":102,'
        '"target2":104,"current_R":0.75,"p95_latency_us":7,"feed_status":"starting"}'
    ])
    session.processes["BTCUSDT"] = proc
    manager._sessions["parser-user"] = session
    monkeypatch.setattr(live_paper, "_update_wallet", lambda *args, **kwargs: {})

    manager._reader(session, "BTCUSDT", proc)
    status = manager.status("parser-user")

    assert status["feed_status"] == "connected"
    assert status["ticks_processed"] == 3
    assert status["markets"][0]["messages"] == 3
    assert status["open_positions_detail"][0]["entry_price"] == 100
    assert status["open_positions_detail"][0]["qty"] == 0.5
    assert status["recent_candles"][-1]["close"] == 101.5


def test_live_candle_and_trade_history_are_bounded(monkeypatch):
    manager = LivePaperManager()
    session = LivePaperSession(user_id="bounded-user", session_id="1", status="running")
    session.live_config = {"symbols": ["BTCUSDT"], "bar_seconds": 1}
    lines = [
        f'QUANTOS_HEARTBEAT {{"symbol":"BTCUSDT","latest_price":{100 + i},'
        f'"processed":{i + 1},"closed_trades":[{{"symbol":"BTCUSDT","r":-1.314}}]}}'
        for i in range(1005)
    ]
    proc = _LinesProcess(lines)
    session.processes["BTCUSDT"] = proc
    manager._sessions["bounded-user"] = session
    monkeypatch.setattr(live_paper, "_update_wallet", lambda *args, **kwargs: {})
    monkeypatch.setattr(live_paper.time, "time", lambda: test_live_candle_and_trade_history_are_bounded.tick)

    for i, line in enumerate(lines):
        test_live_candle_and_trade_history_are_bounded.tick = 1_700_000_000 + i
        proc.stdout = iter([line])
        manager._reader(session, "BTCUSDT", proc)

    assert len(session.candles_by_symbol["BTCUSDT"]) == 1000
    assert len(session.events) == 100
    assert session.events[-1]["result"] == "LOSS"


class _BlockingStdout:
    def __init__(self, proc):
        self.proc = proc

    def __iter__(self):
        return self

    def __next__(self):
        while not self.proc.stopped:
            time.sleep(0.01)
        raise StopIteration


class _FakeProcess:
    def __init__(self):
        self.stopped = False
        self.stdout = _BlockingStdout(self)

    def poll(self):
        return 0 if self.stopped else None

    def send_signal(self, signal):
        self.stopped = True

    def terminate(self):
        self.stopped = True

    def kill(self):
        self.stopped = True


def test_duplicate_start_prevention_and_stop_process(tmp_path, monkeypatch):
    binary = tmp_path / "build" / "Release" / "prism_live_paper_trading.exe"
    binary.parent.mkdir(parents=True)
    binary.write_text("stub", encoding="utf-8")
    monkeypatch.setattr(live_paper.settings, "project_root", tmp_path)

    created = []

    def fake_popen(*args, **kwargs):
        proc = _FakeProcess()
        created.append(proc)
        return proc

    monkeypatch.setattr(live_paper.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(live_paper.subprocess, "CREATE_NEW_PROCESS_GROUP", 0, raising=False)

    manager = LivePaperManager()
    first = manager.start("duplicate-user", symbols=["BTCUSDT"])
    second = manager.start("duplicate-user", symbols=["BTCUSDT"])

    assert first["status"] == "running"
    assert second["status"] == "running"
    assert len(created) == 1

    stopped = manager.stop("duplicate-user")

    assert stopped["status"] == "stopped"
    assert stopped["process_running"] is False
    assert created[0].poll() == 0
