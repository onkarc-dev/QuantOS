'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { api, formatApiError } from '../../lib/api';

export default function AICoachV2Page() {
  const [data, setData] = useState<any>(null);
  const [tradeReview, setTradeReview] = useState<any>(null);
  const [strategyAdvice, setStrategyAdvice] = useState<any>(null);
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api('/trader-profile/me/ai-coach-v2')
      .then(setData)
      .catch(e => setMsg(formatApiError(e)))
      .finally(() => setLoading(false));
  }, []);

  async function runTradeReview() {
    try {
      const res = await api('/trader-profile/ai-coach-v2/trade-review', {
        method: 'POST',
        body: JSON.stringify({ symbol: 'BTCUSDT', side: 'LONG', entry: 65000, exit: 65800, stop: 64500, r_multiple: 1.6, pnl: 800, setup_score: 8, rule_followed: true, note: 'Demo review' }),
      });
      setTradeReview(res);
    } catch (e) { setMsg(formatApiError(e)); }
  }

  async function runStrategyAdvice() {
    try {
      const res = await api('/trader-profile/ai-coach-v2/strategy-advice', {
        method: 'POST',
        body: JSON.stringify({ strategy_name: 'Demo Breakout Strategy', trades: 42, win_rate_pct: 41, avg_r: 0.18, gross_r: 7.6, max_drawdown_r: 5.2, profit_factor: 1.34, regime: 'BULL_TREND' }),
      });
      setStrategyAdvice(res);
    } catch (e) { setMsg(formatApiError(e)); }
  }

  const coach = data?.ai_coach_v2 || {};
  const s = {
    page: { background: '#0d0d1a', minHeight: '100vh', padding: 24, color: '#e2e8f0', fontFamily: 'system-ui,sans-serif' },
    wrap: { maxWidth: 1100, margin: '0 auto' },
    h1: { fontSize: 34, fontWeight: 850, margin: '8px 0', background: 'linear-gradient(135deg,#6366f1,#a78bfa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' },
    card: { background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 14, padding: 18, marginTop: 16 },
    grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(300px,1fr))', gap: 16 },
    btn: { background: '#6366f1', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 16px', cursor: 'pointer', fontWeight: 800, marginRight: 10 },
    link: { color: '#a78bfa', textDecoration: 'none', marginRight: 14, fontSize: 13 },
    muted: { color: '#94a3b8', lineHeight: 1.6 },
    danger: { background: '#2a1a1a', border: '1px solid #ef444444', borderRadius: 10, padding: 12, color: '#fca5a5', marginTop: 14 },
  };

  if (loading) return <div style={s.page}><div style={s.wrap}><h1 style={s.h1}>Loading AI Coach v2…</h1></div></div>;

  return <div style={s.page}><div style={s.wrap}>
    <Link href="/dashboard" style={s.link}>← Dashboard</Link><Link href="/trader-profile" style={s.link}>Trader Profile</Link>
    <h1 style={s.h1}>AI Coach v2</h1>
    <p style={s.muted}>LLM-ready coaching with deterministic fallback. It explains process, risk, discipline, and strategy quality without giving financial advice.</p>
    {msg && <div style={s.danger}>{msg}</div>}

    <div style={s.card}>
      <div style={{ color: '#94a3b8', fontSize: 12 }}>VERDICT</div>
      <h2>{coach.verdict || 'NEEDS_MORE_DATA'}</h2>
      <p style={s.muted}>{coach.narrative || coach.summary || 'No coach data yet.'}</p>
      <small style={{ color: '#64748b' }}>Mode: {coach.llm_status || 'fallback_rule_based_active'}</small>
    </div>

    <div style={s.grid}>
      <div style={s.card}><h3>Strengths</h3>{(coach.strengths || []).map((x: string, i: number) => <p key={i}>✅ {x}</p>) || <p style={s.muted}>No strengths yet.</p>}</div>
      <div style={s.card}><h3>Weaknesses</h3>{(coach.weaknesses || []).map((x: string, i: number) => <p key={i}>⚠️ {x}</p>) || <p style={s.muted}>No weaknesses yet.</p>}</div>
      <div style={s.card}><h3>Next actions</h3>{(coach.next_actions || []).map((x: string, i: number) => <p key={i}>→ {x}</p>) || <p style={s.muted}>Run more paper sessions.</p>}</div>
    </div>

    <div style={s.card}>
      <h3>Trade-by-trade review demo</h3>
      <button style={s.btn} onClick={runTradeReview}>Run Trade Review</button>
      {tradeReview && <pre style={{ whiteSpace: 'pre-wrap', color: '#c4b5fd' }}>{JSON.stringify(tradeReview, null, 2)}</pre>}
    </div>

    <div style={s.card}>
      <h3>Strategy improvement suggestions demo</h3>
      <button style={s.btn} onClick={runStrategyAdvice}>Run Strategy Advice</button>
      {strategyAdvice && <pre style={{ whiteSpace: 'pre-wrap', color: '#c4b5fd' }}>{JSON.stringify(strategyAdvice, null, 2)}</pre>}
    </div>
  </div></div>;
}
