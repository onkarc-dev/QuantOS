'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api, AuthUser, fetchMe, formatApiError } from '../../lib/api';
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts';

// ─── Types ────────────────────────────────────────────────────────────────────
interface Job { id: string; status: string; mode: string; created_at: string; display_strategy_id?: string; strategy_id?: string; }
interface Strategy { id: string; name: string; }
interface CoachReport {
  final_verdict?: string;
  metrics?: { avg_R?: number; max_drawdown_R?: number; trades?: number; win_rate?: number; equity_curve_R?: number[]; };
  monte_carlo?: { final_R?: { p50?: number }; drawdown_R?: { p95?: number }; risk_of_ruin_minus_10R?: number; };
  lifestyle_fit?: { score?: number; label?: string; };
  rule_discipline?: { manual_rule_violations_detected?: number; };
  strengths?: string[];
  weaknesses?: string[];
}

// ─── Sub-components ───────────────────────────────────────────────────────────
function StatCard({ label, value, sub, accent }: { label: string; value: any; sub?: string; accent?: string }) {
  return (
    <div style={{ background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 12, padding: '20px 24px' }}>
      <div style={{ color: '#888', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, color: accent || '#e2e8f0' }}>{value ?? '—'}</div>
      {sub && <div style={{ color: '#666', fontSize: 12, marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function VerdictBadge({ verdict }: { verdict?: string }) {
  const colors: Record<string, string> = {
    PROMISING_PAPER_SYSTEM: '#22c55e',
    NEEDS_MORE_DATA: '#f59e0b',
    DO_NOT_SCALE_YET: '#ef4444',
  };
  const color = colors[verdict || ''] || '#6366f1';
  return (
    <span style={{
      background: color + '22', color, border: `1px solid ${color}44`,
      borderRadius: 8, padding: '4px 12px', fontSize: 13, fontWeight: 600,
    }}>{verdict || 'NO DATA'}</span>
  );
}

function EquityCurveChart({ data }: { data: number[] }) {
  if (!data?.length) return <div style={{ color: '#666', padding: 20 }}>No trade data yet</div>;
  const points = data.map((v, i) => ({ trade: i + 1, equity: v, positive: v >= 0 }));
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={points} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a" />
        <XAxis dataKey="trade" stroke="#666" tick={{ fontSize: 11 }} />
        <YAxis stroke="#666" tick={{ fontSize: 11 }} tickFormatter={v => `${v}R`} />
        <Tooltip formatter={(v: any) => [`${Number(v).toFixed(2)}R`, 'Equity']} contentStyle={{ background: '#1a1a2e', border: '1px solid #2a2a4a' }} />
        <ReferenceLine y={0} stroke="#444" strokeDasharray="4 2" />
        <Area type="monotone" dataKey="equity" stroke="#6366f1" fill="url(#eqGrad)" strokeWidth={2} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function DrawdownChart({ data }: { data: number[] }) {
  if (!data?.length) return <div style={{ color: '#666', padding: 20 }}>No trade data yet</div>;
  let peak = data[0];
  const dd = data.map((v, i) => {
    peak = Math.max(peak, v);
    const drawdown = v - peak;
    return { trade: i + 1, drawdown };
  });
  return (
    <ResponsiveContainer width="100%" height={160}>
      <AreaChart data={dd} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.4} />
            <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a" />
        <XAxis dataKey="trade" stroke="#666" tick={{ fontSize: 11 }} />
        <YAxis stroke="#666" tick={{ fontSize: 11 }} tickFormatter={v => `${v}R`} />
        <Tooltip formatter={(v: any) => [`${Number(v).toFixed(2)}R`, 'Drawdown']} contentStyle={{ background: '#1a1a2e', border: '1px solid #2a2a4a' }} />
        <ReferenceLine y={0} stroke="#444" />
        <Area type="monotone" dataKey="drawdown" stroke="#ef4444" fill="url(#ddGrad)" strokeWidth={2} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────
export default function Dashboard() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [report, setReport] = useState<CoachReport | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadDashboard() {
      try {
        const me = await fetchMe();
        setUser(me);
        const [jobsRes, strategiesRes] = await Promise.all([
          api('/jobs/'),
          api('/strategies'),
        ]);
        const jobList = Array.isArray(jobsRes) ? jobsRes : (jobsRes as { jobs?: Job[] }).jobs || [];
        const strategyList = Array.isArray(strategiesRes) ? strategiesRes : [];
        setJobs(jobList);
        setStrategies(strategyList);
      } catch (e) {
        setMsg(formatApiError(e));
      } finally {
        setLoading(false);
      }
    }
    loadDashboard();
  }, []);

  useEffect(() => {
    if (jobs.length > 0) {
      const lastCompleted = jobs.find(j => j.status === 'completed');
      if (lastCompleted) {
        api(`/coach/${lastCompleted.id}/coach-report`).then(setReport).catch(() => {});
      }
    }
  }, [jobs]);

  const m = report?.metrics || {};
  const mc = report?.monte_carlo || {};
  const fit = report?.lifestyle_fit || {};
  const discipline = report?.rule_discipline || {};

  const style = {
    page: { background: '#0d0d1a', minHeight: '100vh', padding: '24px', fontFamily: 'system-ui, sans-serif', color: '#e2e8f0' },
    hero: { marginBottom: 32 },
    h1: { fontSize: 28, fontWeight: 700, margin: 0, background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' },
    sub: { color: '#888', marginTop: 6, fontSize: 14 },
    grid4: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16, marginBottom: 24 },
    grid2: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))', gap: 16, marginBottom: 24 },
    card: { background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 12, padding: 24, marginBottom: 0 },
    cardTitle: { fontSize: 14, fontWeight: 600, color: '#888', textTransform: 'uppercase' as const, letterSpacing: 1, marginBottom: 16 },
    disclaimer: { color: '#666', fontSize: 12, textAlign: 'center' as const, padding: '16px 0', borderTop: '1px solid #2a2a4a', marginTop: 32 },
    btn: { background: '#6366f1', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 20px', cursor: 'pointer', fontWeight: 600, textDecoration: 'none', display: 'inline-block', fontSize: 14 },
    btnSec: { background: 'transparent', color: '#6366f1', border: '1px solid #6366f1', borderRadius: 8, padding: '10px 20px', cursor: 'pointer', fontWeight: 600, textDecoration: 'none', display: 'inline-block', fontSize: 14, marginLeft: 12 },
    danger: { background: '#2a1a1a', border: '1px solid #ef444444', borderRadius: 8, padding: '12px 16px', color: '#ef4444', marginBottom: 16 },
    tag: { background: '#1e293b', borderRadius: 6, padding: '2px 8px', fontSize: 12, color: '#94a3b8', display: 'inline-block', marginRight: 6 },
  };

  if (loading) return <div style={style.page}><div style={style.hero}><h1 style={style.h1}>Loading…</h1></div></div>;

  return (
    <div style={style.page}>
      {/* Header */}
      <div style={style.hero}>
        <h1 style={style.h1}>QuantOS – Personal Quant Research Paper Trading Platform</h1>
        <p style={style.sub}>Research-grade quant strategy builder · Backtesting · Live paper trading only</p>
      </div>

      {msg && <div style={style.danger}>{msg}</div>}

      {/* Stats row */}
      <div style={style.grid4}>
        <StatCard label="Trader" value={user?.name || 'Demo'} sub={user?.email || ''} />
        <StatCard label="Strategies" value={strategies.length} sub="10 symbols supported" />
        <StatCard label="Jobs Run" value={jobs.length} />
        <StatCard label="Real Money" value="DISABLED" accent="#ef4444" sub="Paper only — safe" />
      </div>

      {/* Quant Coach summary (if report available) */}
      {report ? (
        <>
          <div style={style.grid4}>
            <StatCard label="Verdict" value={<VerdictBadge verdict={report.final_verdict} />} />
            <StatCard label="Avg R/Trade" value={m.avg_R != null ? `${m.avg_R?.toFixed(3)}R` : '—'} accent={m.avg_R != null && m.avg_R > 0 ? '#22c55e' : '#ef4444'} />
            <StatCard label="Max Drawdown" value={m.max_drawdown_R != null ? `${m.max_drawdown_R?.toFixed(2)}R` : '—'} accent="#f59e0b" sub="Worst observed" />
            <StatCard label="Lifestyle Fit" value={`${fit.score ?? '—'}/100`} sub={fit.label} accent="#8b5cf6" />
          </div>

          <div style={style.grid4}>
            <StatCard label="Trades" value={m.trades ?? 0} sub={m.trades && m.trades < 30 ? '⚠ Need 30+ for confidence' : '✓ Sample size ok'} />
            <StatCard label="Win Rate" value={m.win_rate != null ? `${(m.win_rate * 100).toFixed(1)}%` : '—'} />
            <StatCard label="MC Median (50 trades)" value={mc.final_R?.p50 != null ? `${mc.final_R.p50}R` : '—'} sub="Monte Carlo p50" />
            <StatCard label="Rule Violations" value={discipline.manual_rule_violations_detected ?? 0} accent={discipline.manual_rule_violations_detected ? '#ef4444' : '#22c55e'} sub="Journaled overrides" />
          </div>

          {/* Charts */}
          <div style={style.grid2}>
            <div style={style.card}>
              <div style={style.cardTitle}>Equity Curve (R)</div>
              <EquityCurveChart data={m.equity_curve_R || []} />
            </div>
            <div style={style.card}>
              <div style={style.cardTitle}>Drawdown from Peak (R)</div>
              <DrawdownChart data={m.equity_curve_R || []} />
            </div>
          </div>

          {/* Strengths / Weaknesses */}
          <div style={style.grid2}>
            <div style={style.card}>
              <div style={style.cardTitle}>✅ Strengths</div>
              {report.strengths?.length ? report.strengths.map((s, i) => (
                <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid #2a2a4a', fontSize: 14, color: '#22c55e' }}>• {s}</div>
              )) : <div style={{ color: '#666', fontSize: 14 }}>No strengths detected yet. Run more trades.</div>}
            </div>
            <div style={style.card}>
              <div style={style.cardTitle}>⚠️ Weaknesses</div>
              {report.weaknesses?.length ? report.weaknesses.map((w, i) => (
                <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid #2a2a4a', fontSize: 14, color: '#f59e0b' }}>• {w}</div>
              )) : <div style={{ color: '#666', fontSize: 14 }}>No weaknesses detected. Good sign.</div>}
            </div>
          </div>
        </>
      ) : (
        <div style={style.card}>
          <div style={style.cardTitle}>Quant Coach Summary</div>
          <p style={{ color: '#888', fontSize: 14 }}>No completed jobs yet. Run a backtest to see equity curve, drawdown, and R-distribution analytics.</p>
        </div>
      )}

      {/* Recent jobs */}
      <div style={style.card}>
        <div style={style.cardTitle}>Latest Strategy Runs</div>
        {jobs.length > 0 ? jobs.slice(0, 5).map(j => (
          <div key={j.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #2a2a4a', fontSize: 14 }}>
            <span style={{ color: '#94a3b8' }}>{j.display_strategy_id || j.strategy_id || j.id}</span>
            <span style={style.tag}>{j.mode}</span>
            <span style={{ color: j.status === 'completed' ? '#22c55e' : j.status === 'failed' ? '#ef4444' : '#f59e0b' }}>{j.status}</span>
          </div>
        )) : (
          <p style={{ color: '#888', fontSize: 14 }}>No jobs yet.</p>
        )}
      </div>

      {/* Actions */}
      <div style={{ marginTop: 24, display: 'flex', gap: 12, flexWrap: 'wrap' as const }}>
        <Link href="/strategy-builder" style={style.btn}>+ Build Strategy</Link>
        <Link href="/quant-coach" style={style.btnSec}>Quant Coach Report</Link>
        <Link href="/trade-journal" style={style.btnSec}>Trade Journal</Link>
      </div>

      <div style={style.disclaimer}>
        QuantOS is research/analytics only. Paper trading and backtests are hypothetical.
        Not financial advice. No real-money execution. No broker integration.
      </div>
    </div>
  );
}
