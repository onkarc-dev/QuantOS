from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any


def _f(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _score(value: float, lo: float, hi: float, invert: bool = False) -> float:
    if hi == lo:
        return 0.0
    x = max(0.0, min(1.0, (value - lo) / (hi - lo)))
    if invert:
        x = 1.0 - x
    return round(x * 100, 2)


def build_strategy_health_score(trades: list[dict[str, Any]], journal_entries: list[dict[str, Any]] | None = None, benchmark_returns: list[float] | None = None) -> dict[str, Any]:
    r = [_f(t.get('r_multiple', t.get('r', t.get('pnl', 0)))) for t in trades]
    n = len(r)
    wins = [x for x in r if x > 0]
    losses = [x for x in r if x < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    equity = []
    cur = 0.0
    peak = 0.0
    drawdowns = []
    dd_durations = []
    active_dd = 0
    for x in r:
        cur += x
        equity.append(cur)
        if cur >= peak:
            if active_dd:
                dd_durations.append(active_dd)
            active_dd = 0
            peak = cur
        else:
            active_dd += 1
        drawdowns.append(cur - peak)
    if active_dd:
        dd_durations.append(active_dd)
    avg = mean(r) if r else 0.0
    vol = pstdev(r) if len(r) > 1 else 0.0
    downside = pstdev([min(0.0, x) for x in r]) if len(r) > 1 else 0.0
    max_dd = min(drawdowns) if drawdowns else 0.0
    avg_dd = mean([abs(x) for x in drawdowns if x < 0]) if any(x < 0 for x in drawdowns) else 0.0
    sorted_r = sorted(r)
    var_95 = sorted_r[max(0, int(0.05 * len(sorted_r)) - 1)] if sorted_r else 0.0
    cvar_95 = mean([x for x in sorted_r if x <= var_95]) if sorted_r else 0.0
    fees = sum(_f(t.get('fee', 0)) for t in trades)
    slippage = sum(abs(_f(t.get('slippage', 0))) for t in trades)
    turnover = sum(abs(_f(t.get('notional', t.get('qty', 0)) or 0) * _f(t.get('price', 1))) for t in trades)
    trade_durations = [_f(t.get('duration_seconds', t.get('duration', 0))) for t in trades if t.get('duration_seconds') or t.get('duration')]
    journal_entries = journal_entries or []
    mistakes = [j for j in journal_entries if j.get('rule_broken') or j.get('mistake_tag')]
    repeated = {}
    for j in mistakes:
        key = str(j.get('rule_broken') or j.get('mistake_tag'))
        repeated[key] = repeated.get(key, 0) + 1
    sharpe = (avg / vol * math.sqrt(max(n, 1))) if vol else 0.0
    sortino = (avg / downside * math.sqrt(max(n, 1))) if downside else 0.0
    calmar = (sum(r) / abs(max_dd)) if max_dd else (sum(r) if sum(r) > 0 else 0.0)
    omega = (gross_profit / gross_loss) if gross_loss else (gross_profit if gross_profit else 0.0)
    benchmark_avg = mean(benchmark_returns) if benchmark_returns else None
    information_ratio = ((avg - benchmark_avg) / vol * math.sqrt(max(n, 1))) if benchmark_avg is not None and vol else None
    profit_factor = (gross_profit / gross_loss) if gross_loss else (gross_profit if gross_profit else 0.0)
    recovery_factor = (sum(r) / abs(max_dd)) if max_dd else 0.0
    expectancy = avg
    payoff = (mean(wins) / abs(mean(losses))) if wins and losses else 0.0
    performance_score = _score(sum(r), -5, 20)
    risk_score = round((_score(abs(max_dd), 10, 0, invert=False) + _score(vol, 5, 0, invert=False)) / 2, 2)
    execution_score = _score((fees + slippage) / gross_profit if gross_profit else 1, 0.5, 0, invert=False)
    robustness_score = round((_score(n, 10, 100) + (30 if n < 30 else 80 if n < 100 else 100)) / 2, 2)
    discipline_score = max(0.0, 100.0 - len(mistakes) * 10)
    overall = round(0.30 * performance_score + 0.25 * risk_score + 0.15 * execution_score + 0.20 * robustness_score + 0.10 * discipline_score, 2)
    return {
        'overall_strategy_health_score': overall,
        'sub_scores': {'performance': performance_score, 'risk': risk_score, 'execution': execution_score, 'robustness': robustness_score, 'discipline': discipline_score},
        'performance': {'net_return_R': sum(r), 'annualized_return_R': avg * 252 if n else 0, 'daily_return_R': avg, 'monthly_return_R': avg * 21},
        'risk': {'max_drawdown_R': max_dd, 'average_drawdown_R': avg_dd, 'drawdown_duration_trades': max(dd_durations) if dd_durations else 0, 'volatility_R': vol, 'downside_volatility_R': downside, 'var_95_R': var_95, 'cvar_95_R': cvar_95},
        'risk_adjusted': {'sharpe': sharpe, 'sortino': sortino, 'calmar': calmar, 'omega': omega, 'information_ratio': information_ratio},
        'trading_quality': {'win_rate': len(wins) / n if n else 0, 'loss_rate': len(losses) / n if n else 0, 'average_winner_R': mean(wins) if wins else 0, 'average_loser_R': mean(losses) if losses else 0, 'profit_factor': profit_factor, 'recovery_factor': recovery_factor, 'expectancy_R': expectancy, 'payoff_ratio': payoff, 'average_trade_duration_seconds': mean(trade_durations) if trade_durations else 0},
        'execution_quality': {'turnover': turnover, 'estimated_fees': fees, 'estimated_slippage': slippage, 'cost_vs_gross_profit': ((fees + slippage) / gross_profit) if gross_profit else 0, 'fill_delay': None},
        'robustness': {'trade_count_sufficiency_warning': n < 30, 'overfitting_warning': n < 100 or (len(wins) / n if n else 0) > 0.8, 'parameter_sensitivity': 'placeholder_not_implemented', 'out_of_sample_walk_forward': 'placeholder_not_implemented'},
        'regime_behavior': {'bull_score': None, 'sideways_score': None, 'bear_score': None, 'high_volatility_score': None, 'low_volatility_score': None},
        'discipline': {'journal_entries': len(journal_entries), 'mistake_count': len(mistakes), 'repeated_mistakes': repeated},
    }
