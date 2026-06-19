'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { api, formatApiError } from '../../lib/api';
import QuantCoachVisuals from '../../components/QuantCoachVisuals';

function cleanLabel(value?: string) {
  return String(value || '').replaceAll('_', ' ');
}

function BulletList({ items, empty }: { items?: string[]; empty: string }) {
  if (!items?.length) return <p style={{ color: '#94a3b8' }}>{empty}</p>;
  return <div>{items.map((x, i) => <div key={i} style={{ margin: '10px 0', lineHeight: 1.55 }}>• {x}</div>)}</div>;
}

function CoachBubble({ title, text }: { title: string; text: string }) {
  return <div style={{ display: 'flex', gap: 12, marginTop: 14 }}>
    <div style={{ width: 38, height: 38, borderRadius: 999, background: '#6366f1', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 900 }}>Q</div>
    <div style={{ background: '#111827', border: '1px solid #334155', borderRadius: 16, padding: 16, flex: 1 }}>
      <div style={{ color: '#a78bfa', fontSize: 12, fontWeight: 800, marginBottom: 6 }}>{title}</div>
      <div style={{ color: '#e2e8f0', lineHeight: 1.65 }}>{text}</div>
    </div>
  </div>;
}

export default function QuantCoachPage() {
  const [data, setData] = useState<any>(null);
  const [tradeReview, setTradeReview] = useState<any>(null);
  const [strategyAdvice, setStrategyAdvice] = useState<any>(null);
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');

  useEffect(() => {
    api('/trader-profile/me/ai-coach-v2')
      .then(setData)
      .catch(e => setMsg(formatApiError(e)))
      .finally(() => setLoading(false));
  }, []);

  async function runTradeReview() {
    setBusy('trade'); setMsg('');
    try {
      const res = await api('/trader-profile/ai-coach-v2/trade-review', {
        method: 'POST',
        body: JSON.stringify({ symbol: 'BTCUSDT', side: 'LONG', entry: 65000, exit: 65800, stop: 64500, r_multiple: 1.6, pnl: 800, setup_score: 8, rule_followed: true, note: 'Demo review' }),
      });
      setTradeReview(res);
    } catch (e) { setMsg(formatApiError(e)); }
    finally { setBusy(''); }
  }

  async function runStrategyAdvice() {
    setBusy('strategy'); setMsg('');
    try {
      const res = await api('/trader-profile/ai-coach-v2/strategy-advice', {
        method: 'POST',
        body: JSON.stringify({ strategy_name: 'BTC Breakout Strategy', trades: 42, win_rate_pct: 41, avg_r: 0.18, gross_r: 7.6, max_drawdown_r: 5.2, profit_factor: 1.34, regime: 'BULL_TREND' }),
      });
      setStrategyAdvice(res);
    } catch (e) { setMsg(formatApiError(e)); }
    finally { setBusy(''); }
  }

  const coach = data?.ai_coach_v2 || {};
  const s = {
    page: { background: '#0d0d1a', minHeight: '100vh', padding: 24, color: '#e2e8f0', fontFamily: 'system-ui,sans-serif' },
    wrap: { maxWidth: 1120, margin: '0 auto' },
    h1: { fontSize: 34, fontWeight: 850, margin: '8px 0', background: 'linear-gradient(135deg,#6366f1,#a78bfa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' },
    card: { background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 14, padding: 18, marginTop: 16 },
    grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(300px,1fr))', gap: 16 },
    btn: { background: '#6366f1', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 16px', cursor: 'pointer', fontWeight: 800, marginRight: 10 },
    link: { color: '#a78bfa', textDecoration: 'none', marginRight: 14, fontSize: 13 },
    muted: { color: '#94a3b8', lineHeight: 1.6 },
    danger: { background: '#2a1a1a', border: '1px solid #ef444444', borderRadius: 10, padding: 12, color: '#fca5a5', marginTop: 14 },
    pill: { display: 'inline-block', background: '#312e81', border: '1px solid #6366f155', borderRadius: 999, padding: '5px 10px', color: '#c4b5fd', fontSize: 12, marginBottom: 10 },
  };

  if (loading) return <div style={s.page}><div style={s.wrap}><h1 style={s.h1}>Loading Quant Coach…</h1></div></div>;

  return <div style={s.page}><div style={s.wrap}>
    <Link href="/dashboard" style={s.link}>← Command Center</Link><Link href="/trader-profile" style={s.link}>Trader Profile</Link><Link href="/alternative-data" style={s.link}>Market Context</Link>
    <h1 style={s.h1}>Quant Coach</h1>
    <p style={s.muted}>Professional coaching for paper-trading behavior, strategy process, risk discipline, and improvement loops. Visuals explain what the text means.</p>
    {msg && <div style={s.danger}>{msg}</div>}

    <div style={s.card}>
      <span style={s.pill}>Coach mode: {coach.llm_status || 'fallback coaching active'}</span>
      <h2 style={{ marginTop: 0 }}>{cleanLabel(coach.verdict || 'Needs more data')}</h2>
      <CoachBubble title="QuantOS Coach Review" text={coach.narrative || coach.summary || 'I need more paper-trading history before giving a strong review. Start with one backtest or one paper session, then come back here for a process review.'} />
    </div>

    <QuantCoachVisuals />

    <div style={s.grid}>
      <div style={s.card}><h3>Strengths</h3><BulletList items={coach.strengths} empty="No strong strengths detected yet. Build more trade history." /></div>
      <div style={s.card}><h3>Risk / Weaknesses</h3><BulletList items={coach.weaknesses} empty="No major weaknesses detected yet, but sample size may still be low." /></div>
      <div style={s.card}><h3>Next Actions</h3><BulletList items={coach.next_actions} empty="Run a few more paper sessions using the same rules before changing parameters." /></div>
    </div>

    <div style={s.card}>
      <h3>Trade Review</h3>
      <p style={s.muted}>Run a sample trade review to see how QuantOS explains process quality.</p>
      <button style={s.btn} onClick={runTradeReview} disabled={busy === 'trade'}>{busy === 'trade' ? 'Reviewing…' : 'Review Sample Trade'}</button>
      {tradeReview && <div style={{ marginTop: 18 }}>
        <CoachBubble title="Trade-by-trade review" text={tradeReview.narrative || 'Trade reviewed.'} />
        <div style={s.grid}>
          <div style={s.card}><h3>What went well</h3><BulletList items={tradeReview.positives} empty="No positives detected." /></div>
          <div style={s.card}><h3>What to check</h3><BulletList items={tradeReview.issues} empty="No process issues detected." /></div>
          <div style={s.card}><h3>Next step</h3><BulletList items={tradeReview.next_steps} empty="Keep journaling similar trades." /></div>
        </div>
      </div>}
    </div>

    <div style={s.card}>
      <h3>Strategy Improvement Review</h3>
      <p style={s.muted}>Run a sample strategy review to see how QuantOS gives structured improvement advice.</p>
      <button style={s.btn} onClick={runStrategyAdvice} disabled={busy === 'strategy'}>{busy === 'strategy' ? 'Analyzing…' : 'Review Sample Strategy'}</button>
      {strategyAdvice && <div style={{ marginTop: 18 }}>
        <CoachBubble title={`${strategyAdvice.strategy_name || 'Strategy'} review`} text={strategyAdvice.narrative || 'Strategy reviewed.'} />
        <div style={s.grid}>
          <div style={s.card}><h3>Recommendations</h3><BulletList items={strategyAdvice.suggestions} empty="No recommendations yet." /></div>
          <div style={s.card}><h3>Risks</h3><BulletList items={strategyAdvice.risks} empty="No major risks detected in this sample." /></div>
        </div>
      </div>}
    </div>
  </div></div>;
}
