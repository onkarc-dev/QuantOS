import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
os.environ.setdefault("PRISMFLOW_SECRET_KEY", "unit-test-secret-key-with-enough-length")

from app.db import init_db
from app.services import live_paper
from app.services.live_paper import LivePaperManager, parse_quantos_heartbeat, resolve_live_paper_binary


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
