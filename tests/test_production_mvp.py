import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps' / 'api'))

from app.services.production_readiness import readiness_check
from app.services.job_queue import InMemoryJobQueue
from app.services.live_paper import replay_csv_paper_session
from app.services.portfolio import aggregate_strategy_reports
from app.services.data_manager import validate_market_csv


def test_readiness_check_is_honest_and_structured():
    out = readiness_check(ROOT)
    assert out['product'] == 'PRISMFlow Production Readiness'
    assert 0 <= out['score_out_of_10'] <= 10
    assert 'blocking_items' in out
    assert any(c['area'] == 'database' for c in out['checks'])


def test_in_memory_queue_executes_job():
    q = InMemoryJobQueue()
    job = q.enqueue('unit', {'x': 2})
    done = q.run(job.id, lambda payload: {'y': payload['x'] + 3})
    assert done.status == 'completed'
    assert done.result == {'y': 5}


def test_live_paper_replay_works_on_sample_data():
    out = replay_csv_paper_session(ROOT / 'data' / 'sample_market_data.csv', max_rows=80)
    assert out['status'] == 'completed'
    assert out['mode'] == 'paper_replay_no_real_money'
    assert out['rows_processed'] > 0
    assert 'risk_statement' in out


def test_portfolio_aggregation():
    out = aggregate_strategy_reports([
        {'strategy_id': 'a', 'metrics': {'trades': 2, 'gross_R': 1.5, 'avg_R': 0.75, 'max_drawdown_R': 0.5}},
        {'strategy_id': 'b', 'metrics': {'trades': 3, 'gross_R': -0.5, 'avg_R': -0.166, 'max_drawdown_R': 1.2}},
    ])
    assert out['portfolio']['strategy_count'] == 2
    assert out['portfolio']['gross_R'] == 1.0


def test_market_data_validation():
    out = validate_market_csv(ROOT / 'data' / 'sample_market_data.csv')
    assert out['valid'] is True
    assert out['rows'] > 0
