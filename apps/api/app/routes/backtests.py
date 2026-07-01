from __future__ import annotations

import csv
import io
import json
import shutil
import subprocess
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.deps import current_user
from app.db import get_conn, now
from app.core.config import settings
from app.services.performance_metrics import build_performance_and_robustness

router = APIRouter()
REQUIRED = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
ALIASES = {
    'timestamp': {'timestamp', 'time', 'date', 'datetime'},
    'open': {'open', 'o'},
    'high': {'high', 'h'},
    'low': {'low', 'l'},
    'close': {'close', 'c'},
    'volume': {'volume', 'v', 'vol'},
}


def _placeholder() -> str:
    return '%s' if settings.is_postgres() else '?'


def _safe_upload_name(name: str) -> str:
    suffix = Path(name or 'upload.csv').suffix.lower()
    if suffix != '.csv':
        suffix = '.csv'
    return f'{uuid.uuid4().hex}{suffix}'


def _column_map(fieldnames: list[str] | None) -> dict[str, str]:
    actual = {str(f or '').strip().lower(): str(f or '').strip() for f in (fieldnames or [])}
    mapped: dict[str, str] = {}
    for canonical, aliases in ALIASES.items():
        for alias in aliases:
            if alias in actual:
                mapped[canonical] = actual[alias]
                break
    return mapped


def _write_normalized_csv(rows: list[dict], path: Path) -> None:
    with path.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=REQUIRED)
        writer.writeheader()
        writer.writerows(rows)


def _run_cpp_backtest(input_csv: Path, output_dir: Path) -> dict:
    binary = settings.engine_binary
    if not binary.exists():
        return {'ran': False, 'blocked_reason': f'prism_backtest binary not found at {binary}'}
    output_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run([str(binary), str(input_csv), str(output_dir)], cwd=str(settings.project_root), capture_output=True, text=True, timeout=30)
    return {'ran': proc.returncode == 0, 'returncode': proc.returncode, 'stdout': proc.stdout[-4000:], 'stderr': proc.stderr[-4000:], 'output_dir': str(output_dir)}


def _persist_backtest(user_id: str, upload_path: Path, output_dir: Path, result: dict) -> str:
    job_id = str(uuid.uuid4())
    report_id = str(uuid.uuid4())
    p = _placeholder()
    summary_path = output_dir / 'backtest_summary.json'
    trade_path = output_dir / 'trade_log.csv'
    summary_json = json.dumps(result)
    if summary_path.exists():
        summary_json = summary_path.read_text(encoding='utf-8', errors='replace')
    with get_conn() as conn:
        conn.execute(
            f"INSERT INTO jobs(id,user_id,strategy_id,mode,status,symbols_json,timeframe,output_dir,stdout,stderr,error_message,created_at,started_at,completed_at) VALUES({','.join([p]*14)})",
            (job_id, user_id, 'csv_upload', 'csv_upload_backtest', 'completed' if result.get('cpp_backtest', {}).get('ran') else 'completed_with_warnings', json.dumps(['CSV']), 'uploaded', str(output_dir), result.get('cpp_backtest', {}).get('stdout', ''), result.get('cpp_backtest', {}).get('stderr', ''), result.get('cpp_backtest', {}).get('blocked_reason', ''), now(), now(), now()),
        )
        conn.execute(
            f"INSERT INTO reports(id,job_id,user_id,summary_json,validation_json,dashboard_snapshot_json,created_at) VALUES({','.join([p]*7)})",
            (report_id, job_id, user_id, summary_json, json.dumps({'upload_path': str(upload_path), 'required_columns': REQUIRED}), json.dumps(result.get('chart_data', [])), now()),
        )
        if trade_path.exists():
            with trade_path.open('r', encoding='utf-8', newline='') as fh:
                for row in csv.DictReader(fh):
                    trade_id = str(row.get('trade_id') or uuid.uuid4())
                    conn.execute(
                        f"INSERT INTO trades(id,job_id,user_id,strategy_id,symbol,trade_json,r_multiple,created_at) VALUES({','.join([p]*8)})",
                        (trade_id, job_id, user_id, 'csv_upload', row.get('symbol', 'CSV'), json.dumps(row), float(row.get('r_multiple') or 0), now()),
                    )
        conn.commit()
    return job_id


@router.post('/upload-csv')
async def upload_csv(file: UploadFile = File(...), user=Depends(current_user)):
    raw = await file.read()
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail='CSV upload limit is 10 MB for closed beta')
    text = raw.decode('utf-8-sig', errors='replace')
    reader = csv.DictReader(io.StringIO(text))
    mapped = _column_map(reader.fieldnames)
    missing = [c for c in REQUIRED if c not in mapped]
    if missing:
        raise HTTPException(status_code=400, detail={'missing_columns': missing, 'required_columns': REQUIRED, 'accepted_aliases': {k: sorted(v) for k, v in ALIASES.items()}})
    rows = []
    for i, row in enumerate(reader, start=2):
        try:
            normalized = {'timestamp': str(row[mapped['timestamp']]).strip()}
            for c in ['open', 'high', 'low', 'close', 'volume']:
                normalized[c] = float(row[mapped[c]])
            rows.append(normalized)
        except Exception:
            raise HTTPException(status_code=400, detail=f'Invalid OHLCV value on CSV line {i}')
        if len(rows) >= 100000:
            break
    if not rows:
        raise HTTPException(status_code=400, detail='CSV contains no data rows')
    upload_root = settings.outputs_dir / 'csv_uploads' / str(user['id'])
    upload_root.mkdir(parents=True, exist_ok=True)
    original_path = upload_root / _safe_upload_name(file.filename or 'upload.csv')
    original_path.write_bytes(raw)
    normalized_path = upload_root / f'normalized_{uuid.uuid4().hex}.csv'
    _write_normalized_csv(rows, normalized_path)
    closes = [float(r['close']) for r in rows]
    returns = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    proxy_trades = [
        {
            'trade_id': i,
            'entry_time': rows[i - 1]['timestamp'],
            'exit_time': rows[i]['timestamp'],
            'r_multiple': change,
            'holding_bars': 1,
            'entry_price': closes[i - 1],
            'exit_price': closes[i],
        }
        for i, change in enumerate(returns, start=1)
    ]
    wins = [r for r in returns if r > 0]
    losses = [abs(r) for r in returns if r < 0]
    gross_win = sum(wins)
    gross_loss = sum(losses)
    output_dir = settings.outputs_dir / 'csv_backtests' / str(user['id']) / uuid.uuid4().hex
    cpp = _run_cpp_backtest(normalized_path, output_dir)
    result = {
        'mode': 'csv-upload-backtest',
        'rows': len(rows),
        'first_timestamp': rows[0]['timestamp'],
        'last_timestamp': rows[-1]['timestamp'],
        'start_close': closes[0],
        'end_close': closes[-1],
        'gross_pnl_points': closes[-1] - closes[0],
        'win_rate': (len(wins) / len(returns)) if returns else 0,
        'profit_factor': (gross_win / gross_loss) if gross_loss else 0,
        'turnover_points': sum(abs(x) for x in returns),
        'estimated_fees': 0.0,
        'estimated_slippage': 0.0,
        'uploaded_file': str(original_path),
        'normalized_file': str(normalized_path),
        'cpp_backtest': cpp,
        'chart_data': rows[-1000:],
        'fees_slippage_note': 'Apply explicit fee/slippage settings before relying on results.',
    }
    result['performance_and_robustness'] = build_performance_and_robustness(
        proxy_trades,
        start_time=rows[0]['timestamp'],
        end_time=rows[-1]['timestamp'],
        bars_processed=len(rows),
        profit_factor=(gross_win / gross_loss) if gross_loss else None,
        risk_per_trade_pct=None,
        source_note='CSV upload uses close-to-close point changes as an R proxy because no explicit entry, stop, risk, or capital data is available.',
    )
    result_path = output_dir / 'quantos_csv_upload_result.json'
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    try:
        result['job_id'] = _persist_backtest(str(user['id']), normalized_path, output_dir, result)
    except Exception as exc:
        result['storage_warning'] = f'Backtest ran but DB storage failed: {exc}'
    return {**result, 'result_export_path': str(result_path)}
