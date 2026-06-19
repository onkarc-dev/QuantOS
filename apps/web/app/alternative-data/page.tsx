'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { api, formatApiError } from '../../lib/api';

const SYMBOLS = ['BTCUSDT','ETHUSDT','BNBUSDT','SOLUSDT','XRPUSDT','ADAUSDT','DOGEUSDT','AVAXUSDT','LINKUSDT','TRXUSDT'];

export default function AlternativeDataPage() {
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [source, setSource] = useState('manual_news_sentiment');
  const [sentiment, setSentiment] = useState(0.1);
  const [confidence, setConfidence] = useState(0.6);
  const [note, setNote] = useState('BTC news sentiment looks mildly positive.');
  const [sources, setSources] = useState<any>(null);
  const [snapshots, setSnapshots] = useState<any[]>([]);
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const [src, snap] = await Promise.all([
        api('/market-intel/sources'),
        api(`/market-intel/snapshots?symbol=${symbol}`),
      ]);
      setSources(src);
      setSnapshots((snap as any).snapshots || []);
    } catch (e) { setMsg(formatApiError(e)); }
  }

  useEffect(() => { load(); }, [symbol]);

  async function saveSnapshot() {
    setBusy(true); setMsg('');
    try {
      await api('/market-intel/snapshots', {
        method: 'POST',
        body: JSON.stringify({
          symbol,
          source,
          sentiment_score: Number(sentiment),
          confidence: Number(confidence),
          payload: { note, type: 'manual_context', warning: 'context only, not prediction' },
        }),
      });
      setMsg('Alternative-data snapshot saved.');
      await load();
    } catch (e) { setMsg(formatApiError(e)); }
    finally { setBusy(false); }
  }

  const s = {
    page: { background: '#0d0d1a', minHeight: '100vh', padding: 24, color: '#e2e8f0', fontFamily: 'system-ui,sans-serif' },
    wrap: { maxWidth: 1120, margin: '0 auto' },
    h1: { fontSize: 34, fontWeight: 850, margin: '8px 0', background: 'linear-gradient(135deg,#6366f1,#a78bfa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' },
    card: { background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 14, padding: 18, marginTop: 16 },
    grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(260px,1fr))', gap: 14, marginTop: 16 },
    input: { background: '#111827', color: '#e2e8f0', border: '1px solid #334155', borderRadius: 8, padding: '10px 12px', margin: '6px 8px 6px 0', minWidth: 180 },
    textarea: { background: '#111827', color: '#e2e8f0', border: '1px solid #334155', borderRadius: 8, padding: 12, width: '100%', minHeight: 90 },
    btn: { background: '#6366f1', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 16px', cursor: 'pointer', fontWeight: 800, marginTop: 10 },
    link: { color: '#a78bfa', textDecoration: 'none', marginRight: 14, fontSize: 13 },
    muted: { color: '#94a3b8', lineHeight: 1.6 },
    danger: { background: '#2a1a1a', border: '1px solid #ef444444', borderRadius: 10, padding: 12, color: '#fca5a5', marginTop: 14 },
  };

  return <div style={s.page}><div style={s.wrap}>
    <Link href="/dashboard" style={s.link}>← Dashboard</Link><Link href="/regime-dashboard" style={s.link}>Regime Dashboard</Link><Link href="/ai-coach-v2" style={s.link}>AI Coach v2</Link>
    <h1 style={s.h1}>Alternative Data Dashboard</h1>
    <p style={s.muted}>Store context layers like news/social sentiment, funding, open interest, fear & greed, and on-chain signals. At this stage, QuantOS treats this as context, not guaranteed prediction.</p>
    {msg && <div style={s.danger}>{msg}</div>}

    <div style={s.card}>
      <h3>Add context snapshot</h3>
      <select value={symbol} onChange={e => setSymbol(e.target.value)} style={s.input}>{SYMBOLS.map(x => <option key={x}>{x}</option>)}</select>
      <select value={source} onChange={e => setSource(e.target.value)} style={s.input}>
        <option>manual_news_sentiment</option><option>manual_social_sentiment</option><option>funding_rate_context</option><option>open_interest_context</option><option>fear_greed_context</option><option>on_chain_context</option>
      </select>
      <input type="number" step="0.1" value={sentiment} onChange={e => setSentiment(Number(e.target.value))} style={s.input} placeholder="sentiment -1 to +1" />
      <input type="number" step="0.1" value={confidence} onChange={e => setConfidence(Number(e.target.value))} style={s.input} placeholder="confidence 0 to 1" />
      <textarea value={note} onChange={e => setNote(e.target.value)} style={s.textarea} />
      <button style={s.btn} onClick={saveSnapshot} disabled={busy}>{busy ? 'Saving…' : 'Save Snapshot'}</button>
    </div>

    <div style={s.grid}>
      {(sources?.free_foundation_sources || []).map((x: any, i: number) => <div key={i} style={s.card}>
        <h3>{x.name}</h3><p style={s.muted}>{x.use}</p><b>{x.status}</b>
      </div>)}
    </div>

    <div style={s.card}>
      <h3>Recent {symbol} snapshots</h3>
      {snapshots.length ? snapshots.map((x, i) => <div key={i} style={{ borderBottom: '1px solid #2a2a4a', padding: '10px 0' }}>
        <b>{x.source}</b> · sentiment {Number(x.sentiment_score || 0).toFixed(2)} · confidence {Number(x.confidence || 0).toFixed(2)} · {x.captured_at}
      </div>) : <p style={s.muted}>No snapshots yet. Add your first context snapshot above.</p>}
    </div>
  </div></div>;
}
