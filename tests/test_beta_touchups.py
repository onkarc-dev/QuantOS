import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps' / 'api'))
os.environ.setdefault('PRISMFLOW_SECRET_KEY', 'unit-test-secret-key-with-enough-length')

from app.db import init_db
from app.services.engine_bridge import create_engine_token, record_heartbeat, status_for_user
from app.services.ai_explainer import explain_backtest
from app.services.live_paper import replay_csv_paper_session


def setup_module(module):
    init_db()


def test_engine_bridge_records_safe_heartbeat(tmp_path, monkeypatch):
    from app.core import config
    from app.services import engine_bridge
    config.settings.api_root = tmp_path
    engine_bridge.settings.api_root = tmp_path
    tok = create_engine_token('user-1', mode='paper', exchange='binance', source='BTCUSDT')
    assert tok['token'].startswith('qeng_')
    out = record_heartbeat(tok['token'], {
        'mode': 'paper', 'exchange': 'binance', 'source': 'BTCUSDT',
        'engine_version': 'test', 'latest_price': 100.0,
        'p50_latency_us': 1, 'p95_latency_us': 2, 'p99_latency_us': 3,
        'api_secret': 'must-not-be-stored', 'trades': []
    })
    assert out['connected'] is True
    assert out['latency']['p99_us'] == 3.0
    assert 'api_secret' not in str(out.get('payload', ''))
    assert status_for_user('user-1')['source'] == 'BTCUSDT'


def test_ai_explainer_fallback_no_key(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    out = explain_backtest({'metrics': {'trades': 5, 'turnover': 2}})
    assert out['source'] == 'heuristic-fallback'
    assert out['trade_count_sufficiency_warning'] is True
    assert 'No real-money trading' in out['risk_warning']


def test_csv_replay_smoke_uses_local_data_only():
    out = replay_csv_paper_session(ROOT / 'data' / 'sample_market_data.csv', max_rows=25)
    assert out['status'] == 'completed'
    assert out['source'] == 'local_csv'
    assert out['rows_processed'] == 25
    assert out['mode'] == 'paper_replay_no_real_money'

from app.services.strategy_health import build_strategy_health_score


def test_strategy_health_score_complete_shape():
    trades = [{'r_multiple': x, 'fee': 0.01, 'slippage': 0.02, 'qty': 1, 'price': 100} for x in [1, -0.5, 1.2, -0.2, 0.8] * 8]
    out = build_strategy_health_score(trades, [{'rule_broken': 'overtrade'}, {'rule_broken': 'overtrade'}])
    assert 0 <= out['overall_strategy_health_score'] <= 100
    for key in ['performance', 'risk', 'execution', 'robustness', 'discipline']:
        assert key in out['sub_scores']
    assert 'sharpe' in out['risk_adjusted']
    assert out['discipline']['repeated_mistakes']['overtrade'] == 2
