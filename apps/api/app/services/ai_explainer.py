from __future__ import annotations

import os
from typing import Any


def explain_backtest(payload: dict[str, Any] | None) -> dict[str, Any]:
    metrics = (payload or {}).get('metrics') or {}
    trades = int(metrics.get('total_trades') or metrics.get('trades') or 0)
    win_rate = float(metrics.get('win_rate') or 0)
    max_dd = float(metrics.get('max_drawdown') or metrics.get('max_drawdown_in_R') or 0)
    turnover = float(metrics.get('turnover') or 0)
    key_configured = bool(os.getenv('OPENAI_API_KEY', '').strip())
    return {
        'ai_configured': key_configured,
        'source': 'heuristic-fallback' if not key_configured else 'ai-service-ready',
        'why_won_or_lost': 'Positive expectancy depends on win rate, average win/loss, fees, and slippage. Add more trades before scaling.' if trades < 30 else 'Enough trades exist for a first-pass review; compare performance by market regime before trusting it.',
        'best_worst_regime': 'Segment results by trend/range and volatility buckets; current payload does not include full regime labels.',
        'drawdown_explanation': f'Max drawdown observed: {max_dd}. Review clustered losses and position sizing.',
        'turnover_cost_warning': 'Turnover/cost impact is high; reduce churn or model fees/slippage carefully.' if turnover > 1 else 'No high-turnover warning from supplied metrics.',
        'suggested_improvements': ['Increase sample size', 'Model fees and slippage', 'Validate out-of-sample', 'Keep paper-only until stable'],
        'risk_warning': 'Educational paper/backtest analytics only. No real-money trading is enabled.',
        'trade_count_sufficiency_warning': trades < 30,
        'overfitting_warning': trades < 100 or win_rate > 0.8,
    }
