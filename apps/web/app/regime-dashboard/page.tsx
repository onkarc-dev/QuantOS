'use client';

import Link from 'next/link';
import { useState } from 'react';
import { api, formatApiError } from '../../lib/api';

const SYMBOLS = ['BTCUSDT','ETHUSDT','BNBUSDT','SOLUSDT','XRPUSDT','ADAUSDT','DOGEUSDT','AVAXUSDT','LINKUSDT','TRXUSDT'];

export default function RegimeDashboardPage() {
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [interval, setIntervalValue] = useState('1h');
  const [regime, setRegime] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(false);

  async function detect() {
    setLoading(true); setMsg('');
    try {
      const res = await api(`/market-intel/regime/${symbol}?interval=${interval}&limit=120`);
      setRegime(res);
      const hist = await api(`/market-intel/regime/${symbol}/history`);
      setHistory((hist as any).history || []);
    } catch (e) { setMsg(formatApiError(e)); }
    finally { setLoading(false); }
  }

  const s = {
    page: { background: '#0d0d1a', minHeight: '100vh', padding: 24, color: '#e2e8f0', fontFamily: 'system-ui,sans-serif' },
    wrap: { maxWidth: 1120, margin: '0 auto' },
    h1: { fontSize: 34, fontWeight: 850, margin: '8px 0', background: 'linear-gradient(135deg,#6366f1,#a78bfa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' },
    card: { background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 14, padding: 18, marginTop: 16 },
    grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(220px,1fr))', gap: 14, marginTop: 16 },
    input: { background: '#111827', color: '#e2e8f0', border: '1px solid #334155', borderRadius: 8, padding: '10px 12px', marginRight: 10 },
    btn: { background: '#6366f1', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 16px', cursor: 'pointer', fontWeight: 800 },
    link: { color: '#a78bfa', textDecoration: 'none', marginRight: 14, fontSize: 13 },
    muted: { color: '#94a3b8', lineHeight: 1.6 },
    danger: { background: '#2a1a1a', border: '1px solid #ef444444', borderRadius: 10, padding: 12, color: '#fca5a5', marginTop: 14 },
  };

  return <div style={s.page}><div style={s.wrap}>
    <Link href="/dashboard" style={s.link}>← Dashboard</Link><Link href="/alternative-data" style={s.link}>Alternative Data</Link><Link href="/ai-coach-v2" style={s.link}>AI Coach v2</Link>
    <h1 style={s.h1}>Regime Dashboard</h1>
    <p style={s.muted}>Detect trend/range/high-volatility regimes from public Binance candles. This is context for risk and strategy selection, not a prediction engine.</p>
    {msg && <div style={s.danger}>{msg}</div>}

    <div style={s.card}>
      <select value={symbol} onChange={e => setSymbol(e.target.value)} style={s.input}>{SYMBOLS.map(x => <option key={x}>{x}</option>)}</select>
      <select value={interval} onChange={e => setIntervalValue(e.target.value)} style={s.input}><option>15m</option><option>1h</option><option>4h</option><option>1d</option></select>
      <button style={s.btn} onClick={detect} disabled={loading}>{loading ? 'Detecting…' : 'Detect Regime'}</button>
    </div>

    <div style={s.grid}>
      <div style={s.card}><div style={{ color: '#94a3b8', fontSize: 12 }}>REGIME</div><h2>{regime?.regime || '—'}</h2></div>
      <div style={s.card}><div style={{ color: '#94a3b8', fontSize: 12 }}>CONFIDENCE</div><h2>{Number(regime?.confidence || 0).toFixed(1)}%</h2></div>
      <div style={s.card}><div style={{ color: '#94a3b8', fontSize: 12 }}>VOLATILITY</div><h2>{Number(regime?.volatility_pct || 0).toFixed(2)}%</h2></div>
      <div style={s.card}><div style={{ color: '#94a3b8', fontSize: 12 }}>TREND STRENGTH</div><h2>{Number(regime?.trend_strength || 0).toFixed(1)}</h2></div>
    </div>

    <div style={s.card}>
      <h3>Interpretation</h3>
      <p style={s.muted}>{regime?.regime === 'BULL_TREND' ? 'Trend-following and breakout systems may have better conditions, but risk must still be controlled.' : regime?.regime === 'HIGH_VOL_RANGE' ? 'High volatility range can create false breakouts. Use stricter confirmation and smaller risk.' : regime?.regime ? 'Use this regime as one input when reviewing strategy performance.' : 'Run regime detection to get market context.'}</p>
    </div>

    <div style={s.card}>
      <h3>Recent snapshots</h3>
      {history.length ? history.slice(0, 10).map((h, i) => <div key={i} style={{ borderBottom: '1px solid #2a2a4a', padding: '9px 0' }}>{h.captured_at} · <b>{h.regime}</b> · confidence {Number(h.confidence || 0).toFixed(1)}%</div>) : <p style={s.muted}>No snapshots yet.</p>}
    </div>
  </div></div>;
}
