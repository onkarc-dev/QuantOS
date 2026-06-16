
'use client';

import { useEffect, useMemo, useState } from 'react';
import type { CSSProperties } from 'react';
import { api, formatApiError } from '../../lib/api';

type Job = { id: string; status: string; mode?: string; created_at?: string; symbol?: string; symbols?: string[]; symbols_json?: string; display_strategy_id?: string; user_strategy_id?: string; strategy_code?: string; strategy_id?: string };
type TradeRow = Record<string, any>;

function money(v: any) {
  const n = Number(v);
  if (!Number.isFinite(n)) return '-';
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}
function rFmt(v: any) {
  const n = Number(v);
  if (!Number.isFinite(n)) return '-';
  return `${n > 0 ? '+' : ''}${n.toFixed(3)}R`;
}
function cleanTime(v: any) {
  if (!v) return '-';
  const raw = String(v).replace('+00:00Z', 'Z');
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw.replace('T', ' ').replace('Z', ' UTC');
  return d.toLocaleString(undefined, { hour12: false });
}
function cleanReason(v: any) {
  return String(v || '-')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, c => c.toUpperCase());
}
function resultFromRow(r: TradeRow) {
  const explicit = String(r.result || '').toUpperCase();
  if (['WIN', 'LOSS', 'BREAKEVEN'].includes(explicit)) return explicit;
  const rr = Number(r.r_multiple ?? r.R_multiple ?? r.r);
  if (Number.isFinite(rr)) {
    if (rr > 0.000001) return 'WIN';
    if (rr < -0.000001) return 'LOSS';
    return 'BREAKEVEN';
  }
  const entry = Number(r.entry_price), exit = Number(r.exit_price);
  if (Number.isFinite(entry) && Number.isFinite(exit)) {
    if (exit > entry) return 'WIN';
    if (exit < entry) return 'LOSS';
    return 'BREAKEVEN';
  }
  return '-';
}
function resultStyle(result: any) {
  const r = String(result).toUpperCase();
  if (r === 'WIN') return { color: '#86efac', fontWeight: 800 };
  if (r === 'LOSS') return { color: '#fca5a5', fontWeight: 800 };
  return { color: '#e5e7eb', fontWeight: 800 };
}
function signedStyle(v: any) {
  const n = Number(String(v ?? '').replace(/[R,$,% ]/g, ''));
  if (!Number.isFinite(n)) return {};
  if (n > 0) return { color: '#86efac', fontWeight: 800 };
  if (n < 0) return { color: '#fca5a5', fontWeight: 800 };
  return { color: '#e5e7eb', fontWeight: 800 };
}
function displayStrategy(j: Job) {
  return j.display_strategy_id || j.user_strategy_id || j.strategy_code || j.strategy_id || 'STRATEGY';
}
function jobLabel(j: Job) {
  const date = j.created_at ? new Date(j.created_at).toLocaleString(undefined, { hour12: false }) : 'date unknown';
  let sym = Array.isArray(j.symbols) && j.symbols.length ? j.symbols.join(',') : (j.symbol || 'market');
  if ((!sym || sym === 'market') && j.symbols_json) { try { sym = JSON.parse(j.symbols_json).join(','); } catch {} }
  return `${displayStrategy(j)} · ${(j.mode || 'job').toUpperCase()} · ${sym} · ${j.status} · ${date}`;
}

export default function Journal() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState('');
  const [rows, setRows] = useState<TradeRow[]>([]);
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api('/jobs/')
      .then((r: any) => { setJobs(Array.isArray(r) ? r : (r.jobs || [])); setMsg(''); })
      .catch(e => setMsg(`Backend not reachable or session expired: ${formatApiError(e)}`));
  }, []);

  async function load(id: string) {
    setSelectedJob(id);
    setRows([]);
    if (!id) return;
    setLoading(true);
    setMsg('');
    try {
      const data: any = await api(`/reports/${id}/trade-log`);
      setRows(Array.isArray(data) ? data : (data.rows || []));
    } catch (e: any) {
      setMsg(formatApiError(e));
    } finally {
      setLoading(false);
    }
  }

  const summary = useMemo(() => {
    const total = rows.length;
    const wins = rows.filter(r => resultFromRow(r) === 'WIN').length;
    const losses = rows.filter(r => resultFromRow(r) === 'LOSS').length;
    const be = rows.filter(r => resultFromRow(r) === 'BREAKEVEN').length;
    const gross = rows.reduce((a, r) => a + (Number(r.r_multiple ?? r.R_multiple ?? r.r) || 0), 0);
    return { total, wins, losses, be, gross };
  }, [rows]);

  return <main style={{ padding: 24, maxWidth: 1280, margin: '0 auto' }}>
    <section style={{ marginBottom: 24 }}>
      <h1 style={{ fontSize: 34, marginBottom: 8 }}>Trade Journal</h1>
    </section>

    {msg && <div style={dangerStyle}>{msg}</div>}

    <section style={panelStyle}>
      <label style={{ display: 'grid', gap: 8, color: '#94a3b8', fontSize: 13 }}>
        Select completed job
        <select value={selectedJob} onChange={e => load(e.target.value)}>
          <option value="">Choose a report…</option>
          {jobs.map(j => <option key={j.id} value={j.id}>{jobLabel(j)}</option>)}
        </select>
      </label>
    </section>

    <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 14, margin: '16px 0' }}>
      <Kpi label="Trades" value={String(summary.total)} />
      <Kpi label="Wins / Losses / BE" value={<><span style={{ color:'#86efac' }}>{summary.wins}</span><span style={{ color:'#64748b' }}> / </span><span style={{ color:'#fca5a5' }}>{summary.losses}</span><span style={{ color:'#64748b' }}> / </span><span>{summary.be}</span></>} />
      <Kpi label="Gross R" value={<span style={signedStyle(summary.gross)}>{summary.gross.toFixed(2)}R</span>} />
      <Kpi label="Selected Strategy" value={selectedJob ? displayStrategy(jobs.find(j => j.id === selectedJob) || {} as Job) : '-'} />
    </section>

    <section style={panelStyle}>
      <div style={{ display:'flex', justifyContent:'space-between', gap:12, alignItems:'baseline', marginBottom: 12, flexWrap:'wrap' }}>
        <div>
          <h2 style={{ fontSize: 20, marginBottom: 4 }}>Trades</h2>
          <p style={{ color:'#94a3b8', fontSize:13 }}>Entry, exit, result, R, stop and targets in a clean trade table.</p>
        </div>
        {loading && <span style={{ color:'#93c5fd' }}>Loading trades…</span>}
      </div>
      <div style={{ overflowX:'auto' }}>
        <table className="pro-table" style={{ width:'100%', borderCollapse:'collapse' }}>
          <thead><tr>{['#','Symbol','Entry time','Entry','Stop','Target 1','Target 2','Exit time','Exit','Exit reason','Result','R','Setup score'].map(h => <th key={h}>{h}</th>)}</tr></thead>
          <tbody>
            {rows.length ? rows.map((r, i) => {
              const result = resultFromRow(r);
              const rv = r.r_multiple ?? r.R_multiple ?? r.r;
              return <tr key={i}>
                <td>{r.trade_id ?? i + 1}</td>
                <td style={{ color:'#93c5fd', fontWeight:800 }}>{r.symbol || r.market || '-'}</td>
                <td>{cleanTime(r.entry_time)}</td>
                <td>{money(r.entry_price)}</td>
                <td>{money(r.stop_loss ?? r.stop)}</td>
                <td>{money(r.target1)}</td>
                <td>{money(r.target2)}</td>
                <td>{cleanTime(r.exit_time)}</td>
                <td>{money(r.exit_price)}</td>
                <td>{cleanReason(r.exit_reason)}</td>
                <td style={resultStyle(result)}>{result}</td>
                <td style={signedStyle(rv)}>{rFmt(rv)}</td>
                <td>{r.setup_score_at_entry ?? r.setup_score ?? '-'}</td>
              </tr>;
            }) : <tr><td colSpan={13} style={{ color:'#94a3b8', padding:14 }}>{selectedJob ? 'No trades found for this report.' : 'Select a job to view trades.'}</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  </main>;
}

function Kpi({ label, value }: { label: string; value: any }) {
  return <div style={panelStyle}><div style={{ color:'#94a3b8', fontSize:12, textTransform:'uppercase', letterSpacing:'.08em' }}>{label}</div><div style={{ fontSize:24, fontWeight:900, marginTop:6 }}>{value}</div></div>;
}

const panelStyle: CSSProperties = { background:'#111827', border:'1px solid #243044', borderRadius:16, padding:18 };
const dangerStyle: CSSProperties = { ...panelStyle, borderColor:'#7f1d1d', background:'#2a1214', color:'#fecaca', marginBottom:16 };
