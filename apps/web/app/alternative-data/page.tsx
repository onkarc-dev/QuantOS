'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { api, formatApiError } from '../../lib/api';

const SYMBOLS = ['BTCUSDT','ETHUSDT','BNBUSDT','SOLUSDT','XRPUSDT','ADAUSDT','DOGEUSDT','AVAXUSDT','LINKUSDT','TRXUSDT'];

type Metric = { metric_type: string; symbol?: string; value: number; label?: string; captured_at?: string; payload_json?: string };

type NewsItem = { source: string; title: string; url?: string; sentiment_score?: number; ingested_at?: string; symbols_json?: string };

export default function AlternativeDataPage() {
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [source, setSource] = useState('manual_news_sentiment');
  const [sentiment, setSentiment] = useState(0.1);
  const [confidence, setConfidence] = useState(0.6);
  const [note, setNote] = useState('BTC news sentiment looks mildly positive.');
  const [sources, setSources] = useState<any>(null);
  const [snapshots, setSnapshots] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const [src, snap, metricRes, newsRes] = await Promise.all([
        api('/market-intel/sources'),
        api(`/market-intel/snapshots?symbol=${symbol}`),
        api(`/market-intel/metrics?symbol=${symbol}&metric_type=all`),
        api(`/market-intel/news?symbol=${symbol}`),
      ]);
      setSources(src);
      setSnapshots((snap as any).snapshots || []);
      setMetrics((metricRes as any).snapshots || []);
      setNews((newsRes as any).news || []);
    } catch (e) { setMsg(formatApiError(e)); }
  }

  useEffect(() => { load(); }, [symbol]);

  async function saveSnapshot() {
    setBusy(true); setMsg('');
    try {
      await api('/market-intel/snapshots', {
        method: 'POST',
        body: JSON.stringify({ symbol, source, sentiment_score: Number(sentiment), confidence: Number(confidence), payload: { note, type: 'manual_context', warning: 'context only, not prediction' } }),
      });
      setMsg('Alternative-data snapshot saved.');
      await load();
    } catch (e) { setMsg(formatApiError(e)); }
    finally { setBusy(false); }
  }

  async function ingest(endpoint: string, label: string) {
    setBusy(true); setMsg('');
    try {
      const res = await api(endpoint, { method: 'POST' });
      setMsg(`${label} refreshed successfully.`);
      await load();
      console.log('[QuantOS][market-intel]', res);
    } catch (e) { setMsg(formatApiError(e)); }
    finally { setBusy(false); }
  }

  const latest = (type: string) => metrics.find(m => m.metric_type === type);
  const fearGreed = latest('fear_greed');
  const funding = latest('funding_rate');
  const oi = latest('open_interest');

  const s = {
    page: { background: '#0d0d1a', minHeight: '100vh', padding: 24, color: '#e2e8f0', fontFamily: 'system-ui,sans-serif' },
    wrap: { maxWidth: 1160, margin: '0 auto' },
    h1: { fontSize: 34, fontWeight: 850, margin: '8px 0', background: 'linear-gradient(135deg,#6366f1,#a78bfa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' },
    card: { background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 14, padding: 18, marginTop: 16 },
    grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(260px,1fr))', gap: 14, marginTop: 16 },
    input: { background: '#111827', color: '#e2e8f0', border: '1px solid #334155', borderRadius: 8, padding: '10px 12px', margin: '6px 8px 6px 0', minWidth: 180 },
    textarea: { background: '#111827', color: '#e2e8f0', border: '1px solid #334155', borderRadius: 8, padding: 12, width: '100%', minHeight: 90 },
    btn: { background: '#6366f1', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 16px', cursor: 'pointer', fontWeight: 800, margin: '6px 8px 6px 0' },
    btnSec: { background: '#111827', color: '#c4b5fd', border: '1px solid #6366f1', borderRadius: 8, padding: '10px 16px', cursor: 'pointer', fontWeight: 800, margin: '6px 8px 6px 0' },
    link: { color: '#a78bfa', textDecoration: 'none', marginRight: 14, fontSize: 13 },
    muted: { color: '#94a3b8', lineHeight: 1.6 },
    danger: { background: '#2a1a1a', border: '1px solid #ef444444', borderRadius: 10, padding: 12, color: '#fca5a5', marginTop: 14 },
    metricValue: { fontSize: 28, fontWeight: 900, margin: '8px 0' },
  };

  return <div style={s.page}><div style={s.wrap}>
    <Link href="/dashboard" style={s.link}>← Dashboard</Link><Link href="/regime-dashboard" style={s.link}>Regime Dashboard</Link><Link href="/ai-coach-v2" style={s.link}>AI Coach v2</Link>
    <h1 style={s.h1}>Alternative Data Dashboard</h1>
    <p style={s.muted}>Automated market context for news, Fear & Greed, funding rates, and open interest. This helps risk/regime awareness, not guaranteed prediction.</p>
    {msg && <div style={s.danger}>{msg}</div>}

    <div style={s.card}>
      <h3>Refresh automated signals</h3>
      <select value={symbol} onChange={e => setSymbol(e.target.value)} style={s.input}>{SYMBOLS.map(x => <option key={x}>{x}</option>)}</select>
      <button style={s.btn} onClick={() => ingest('/market-intel/ingest/news', 'News')} disabled={busy}>Ingest News</button>
      <button style={s.btn} onClick={() => ingest('/market-intel/ingest/fear-greed', 'Fear & Greed')} disabled={busy}>Refresh Fear & Greed</button>
      <button style={s.btn} onClick={() => ingest(`/market-intel/ingest/funding-rate/${symbol}`, 'Funding rate')} disabled={busy}>Refresh Funding</button>
      <button style={s.btn} onClick={() => ingest(`/market-intel/ingest/open-interest/${symbol}`, 'Open interest')} disabled={busy}>Refresh Open Interest</button>
      <button style={s.btnSec} onClick={load} disabled={busy}>Reload Data</button>
    </div>

    <div style={s.grid}>
      <div style={s.card}><div style={{ color: '#94a3b8', fontSize: 12 }}>FEAR & GREED</div><div style={s.metricValue}>{fearGreed ? Number(fearGreed.value).toFixed(0) : '—'}</div><b>{fearGreed?.label || 'No snapshot'}</b><p style={s.muted}>{fearGreed?.captured_at || 'Refresh to store latest value.'}</p></div>
      <div style={s.card}><div style={{ color: '#94a3b8', fontSize: 12 }}>FUNDING RATE</div><div style={s.metricValue}>{funding ? Number(funding.value).toFixed(6) : '—'}</div><b>{funding?.label || 'No snapshot'}</b><p style={s.muted}>{funding?.captured_at || 'Refresh to store latest funding.'}</p></div>
      <div style={s.card}><div style={{ color: '#94a3b8', fontSize: 12 }}>OPEN INTEREST</div><div style={s.metricValue}>{oi ? Number(oi.value).toLocaleString(undefined, { maximumFractionDigits: 2 }) : '—'}</div><b>{oi?.label || 'No snapshot'}</b><p style={s.muted}>{oi?.captured_at || 'Refresh to store latest OI.'}</p></div>
    </div>

    <div style={s.card}>
      <h3>Add manual context snapshot</h3>
      <select value={source} onChange={e => setSource(e.target.value)} style={s.input}><option>manual_news_sentiment</option><option>manual_social_sentiment</option><option>funding_rate_context</option><option>open_interest_context</option><option>fear_greed_context</option><option>on_chain_context</option></select>
      <input type="number" step="0.1" value={sentiment} onChange={e => setSentiment(Number(e.target.value))} style={s.input} placeholder="sentiment -1 to +1" />
      <input type="number" step="0.1" value={confidence} onChange={e => setConfidence(Number(e.target.value))} style={s.input} placeholder="confidence 0 to 1" />
      <textarea value={note} onChange={e => setNote(e.target.value)} style={s.textarea} />
      <button style={s.btn} onClick={saveSnapshot} disabled={busy}>{busy ? 'Working…' : 'Save Manual Snapshot'}</button>
    </div>

    <div style={s.grid}>
      {(sources?.free_foundation_sources || []).map((x: any, i: number) => <div key={i} style={s.card}><h3>{x.name}</h3><p style={s.muted}>{x.use}</p><b>{x.status}</b></div>)}
    </div>

    <div style={s.card}>
      <h3>Recent {symbol} news</h3>
      {news.length ? news.slice(0, 12).map((x, i) => <div key={i} style={{ borderBottom: '1px solid #2a2a4a', padding: '10px 0' }}><b>{x.source}</b> · sentiment {Number(x.sentiment_score || 0).toFixed(2)}<br/><span style={s.muted}>{x.title}</span></div>) : <p style={s.muted}>No news stored yet. Click Ingest News.</p>}
    </div>

    <div style={s.card}>
      <h3>Recent manual snapshots</h3>
      {snapshots.length ? snapshots.map((x, i) => <div key={i} style={{ borderBottom: '1px solid #2a2a4a', padding: '10px 0' }}><b>{x.source}</b> · sentiment {Number(x.sentiment_score || 0).toFixed(2)} · confidence {Number(x.confidence || 0).toFixed(2)} · {x.captured_at}</div>) : <p style={s.muted}>No manual snapshots yet.</p>}
    </div>
  </div></div>;
}
