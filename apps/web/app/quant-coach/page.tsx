'use client';
import { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, RadarChart, Radar, PolarGrid, PolarAngleAxis
} from 'recharts';

interface Job { id: string; status: string; mode: string; created_at: string; display_strategy_id?: string; user_strategy_id?: string; strategy_code?: string; strategy_id?: string; symbols_json?: string; timeframe?: string; }

function VerdictCard({ verdict, color }: { verdict: string; color: string }) {
  return (
    <div style={{ background: color + '18', border: `2px solid ${color}55`, borderRadius: 12, padding: '20px 28px', textAlign: 'center' as const }}>
      <div style={{ fontSize: 11, color: '#888', textTransform: 'uppercase' as const, letterSpacing: 1, marginBottom: 8 }}>Quant Coach Verdict</div>
      <div style={{ fontSize: 22, fontWeight: 700, color }}>{verdict}</div>
    </div>
  );
}

function MetricRow({ label, value, note, accent }: { label: string; value: any; note?: string; accent?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid #2a2a4a' }}>
      <div>
        <div style={{ fontSize: 14, color: '#cbd5e1' }}>{label}</div>
        {note && <div style={{ fontSize: 11, color: '#666', marginTop: 2 }}>{note}</div>}
      </div>
      <div style={{ fontSize: 16, fontWeight: 600, color: accent || '#e2e8f0' }}>{value ?? '—'}</div>
    </div>
  );
}

function RDistributionChart({ trades }: { trades: number[] }) {
  if (!trades?.length) return <div style={{ color: '#666', padding: 16, fontSize: 13 }}>No trades yet</div>;
  // Build histogram buckets
  const min = Math.floor(Math.min(...trades));
  const max = Math.ceil(Math.max(...trades));
  const step = 0.5;
  const buckets: Record<string, number> = {};
  for (let b = min; b <= max; b += step) {
    buckets[b.toFixed(1)] = 0;
  }
  trades.forEach(v => {
    const key = (Math.floor(v / step) * step).toFixed(1);
    buckets[key] = (buckets[key] || 0) + 1;
  });
  const data = Object.entries(buckets).map(([r, count]) => ({ r, count, positive: parseFloat(r) >= 0 }));
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a" />
        <XAxis dataKey="r" stroke="#666" tick={{ fontSize: 10 }} label={{ value: 'R Multiple', position: 'insideBottom', offset: -2, fill: '#666', fontSize: 11 }} />
        <YAxis stroke="#666" tick={{ fontSize: 11 }} />
        <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid #2a2a4a' }} formatter={(v: any, n: any, p: any) => [v, `R=${p.payload.r}`]} />
        {data.map((entry, i) => (
          <Bar key={i} dataKey="count" fill={entry.positive ? '#22c55e' : '#ef4444'} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

function BehaviorCard({ discipline }: { discipline: any }) {
  if (!discipline) return null;
  const violations = discipline.manual_rule_violations_detected || 0;
  const rImpact = discipline.manual_rule_violation_R_impact || 0;
  const status = discipline.status || 'unknown';
  return (
    <div style={{ background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 12, padding: 24 }}>
      <div style={{ fontSize: 13, color: '#888', textTransform: 'uppercase' as const, letterSpacing: 1, marginBottom: 16 }}>Behavior & Rule Discipline</div>
      <MetricRow label="Manual Overrides / Violations" value={violations} accent={violations > 0 ? '#ef4444' : '#22c55e'} />
      <MetricRow label="Total R Impact of Violations" value={`${rImpact}R`} accent={rImpact < 0 ? '#ef4444' : '#888'} note="Negative = violations cost money" />
      <MetricRow label="Tracking Status" value={status} />
      {discipline.rule_counts && Object.keys(discipline.rule_counts).length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 12, color: '#666', marginBottom: 8 }}>Most common violations:</div>
          {Object.entries(discipline.rule_counts).slice(0, 5).map(([rule, count]: [string, any]) => (
            <div key={rule} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, padding: '4px 0', color: '#94a3b8' }}>
              <span>{rule}</span><span style={{ color: '#ef4444' }}>×{count}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function LifestyleCard({ fit }: { fit: any }) {
  if (!fit) return null;
  const scoreColor = fit.score >= 80 ? '#22c55e' : fit.score >= 55 ? '#f59e0b' : '#ef4444';
  return (
    <div style={{ background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 12, padding: 24 }}>
      <div style={{ fontSize: 13, color: '#888', textTransform: 'uppercase' as const, letterSpacing: 1, marginBottom: 16 }}>Lifestyle Fit</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 20, marginBottom: 16 }}>
        <div style={{ fontSize: 48, fontWeight: 700, color: scoreColor }}>{fit.score}</div>
        <div>
          <div style={{ fontSize: 16, fontWeight: 600, color: scoreColor }}>{fit.label}</div>
          <div style={{ fontSize: 12, color: '#666' }}>out of 100</div>
        </div>
      </div>
      <MetricRow label="Est. Signals/Week" value={fit.signals_per_week_estimate} />
      <MetricRow label="Monitoring Burden" value={fit.monitoring_burden} />
      <MetricRow label="Psychological Burden" value={fit.psychological_burden} />
      {fit.why?.map((w: string, i: number) => (
        <div key={i} style={{ fontSize: 12, color: '#666', padding: '4px 0', borderTop: i === 0 ? '1px solid #2a2a4a' : 'none', marginTop: i === 0 ? 12 : 0 }}>• {w}</div>
      ))}
    </div>
  );
}

function displayStrategy(j: Job) {
  return j.display_strategy_id || j.user_strategy_id || j.strategy_code || j.strategy_id || 'STRATEGY';
}
function coachJobLabel(j: Job) {
  const date = j.created_at ? new Date(j.created_at).toLocaleString(undefined, { hour12: false }) : 'date unknown';
  return `${displayStrategy(j)} · ${(j.mode || 'job').toUpperCase()} · ${j.status} · ${date}`;
}

export default function QuantCoach() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [report, setReport] = useState<any>(null);
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api('/jobs/').then((r:any) => { setJobs(Array.isArray(r) ? r : (r.jobs || [])); setMsg(''); }).catch(e => setMsg('Cannot reach QuantOS API. Start the backend and refresh. Details: ' + e.message));
  }, []);

  async function load(id: string) {
    if (!id) return;
    setMsg(''); setReport(null); setLoading(true);
    try {
      const r = await api(`/coach/${id}/coach-report`);
      setReport(r);
    } catch (e: any) { setMsg(e.message); }
    finally { setLoading(false); }
  }

  const m = report?.metrics || {};
  const mc = report?.monte_carlo || {};
  const fit = report?.lifestyle_fit || {};
  const discipline = report?.rule_discipline || {};
  const stress = report?.stress_testing || {};
  const wf = report?.walk_forward_analysis || {};

  const verdictColor: Record<string, string> = {
    PROMISING_PAPER_SYSTEM: '#22c55e',
    NEEDS_MORE_DATA: '#f59e0b',
    DO_NOT_SCALE_YET: '#ef4444',
  };

  const s = {
    page: { background: '#0d0d1a', minHeight: '100vh', padding: 24, fontFamily: 'system-ui,sans-serif', color: '#e2e8f0' },
    hero: { marginBottom: 28 },
    h1: { fontSize: 26, fontWeight: 700, margin: 0, background: 'linear-gradient(135deg,#6366f1,#8b5cf6)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' },
    sub: { color: '#888', marginTop: 6, fontSize: 14 },
    card: { background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 12, padding: 24, marginBottom: 20 },
    cardTitle: { fontSize: 13, color: '#888', textTransform: 'uppercase' as const, letterSpacing: 1, marginBottom: 16, fontWeight: 600 },
    grid2: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: 16, marginBottom: 20 },
    grid3: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 16, marginBottom: 20 },
    danger: { background: '#2a1a1a', border: '1px solid #ef444433', borderRadius: 8, padding: '12px 16px', color: '#ef4444', marginBottom: 16 },
    select: { width: '100%', background: '#0d0d1a', color: '#e2e8f0', border: '1px solid #2a2a4a', borderRadius: 8, padding: '10px 14px', fontSize: 14 },
    insightItem: { padding: '10px 0', borderBottom: '1px solid #2a2a4a', fontSize: 14, color: '#94a3b8', lineHeight: 1.5 },
    disclaimer: { color: '#555', fontSize: 11, textAlign: 'center' as const, padding: '16px 0', marginTop: 24, borderTop: '1px solid #2a2a4a' },
  };

  const allR: number[] = m.equity_curve_R ? (() => {
    const curve: number[] = m.equity_curve_R;
    return curve.map((v: number, i: number) => (i === 0 ? v : v - curve[i - 1]));
  })() : [];
  const hasCoachData = Number(m.trades || report?.summary?.total_trades || 0) > 0;

  return (
    <div style={s.page}>
      <div style={s.hero}>
        <h1 style={s.h1}>Quant Coach Report</h1>
        <p style={s.sub}>Quant Coach analyzes your completed QuantOS backtest and paper-trading reports using expectancy, drawdown, Monte Carlo risk, discipline, walk-forward stability and stress testing.</p>
      </div>

      {msg && <div style={s.danger}>{msg}</div>}

      <div style={s.card}>
        <div style={s.cardTitle}>Select Completed Job</div>
        <select style={s.select} onChange={e => load(e.target.value)} defaultValue="">
          <option value="">Choose a completed backtest or paper job…</option>
          {jobs.filter(j => j.status === 'completed').map(j => (
            <option key={j.id} value={j.id}>{coachJobLabel(j)}</option>
          ))}
        </select>
        {loading && <div style={{ marginTop: 12, color: '#6366f1' }}>Generating report…</div>}
      </div>

      {report && !hasCoachData && (
        <div style={s.card}>
          <div style={s.cardTitle}>Coach Status</div>
          <h2 style={{ marginTop: 0, color: '#f59e0b' }}>Waiting for completed trades</h2>
          <p style={{ color: '#94a3b8', lineHeight: 1.6 }}>This job/report has no closed trades yet, so expectancy, drawdown, Monte Carlo, profit factor and R-distribution cannot be calculated honestly. Run a backtest/live paper session until at least one trade closes, then reopen this report.</p>
        </div>
      )}

      {report && hasCoachData && (
        <>
          {/* Verdict + key metrics */}
          <div style={s.grid3}>
            <VerdictCard verdict={report.final_verdict || 'NO_DATA'} color={verdictColor[report.final_verdict] || '#6366f1'} />
            <div style={{ background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 12, padding: '20px 24px' }}>
              <div style={{ fontSize: 11, color: '#888', textTransform: 'uppercase' as const, letterSpacing: 1, marginBottom: 8 }}>Expectancy</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: (m.avg_R || 0) > 0 ? '#22c55e' : '#ef4444' }}>{m.avg_R?.toFixed(3) ?? '—'}R</div>
              <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>per trade · {m.trades ?? 0} trades</div>
            </div>
            <div style={{ background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 12, padding: '20px 24px' }}>
              <div style={{ fontSize: 11, color: '#888', textTransform: 'uppercase' as const, letterSpacing: 1, marginBottom: 8 }}>Max Drawdown</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#f59e0b' }}>{m.max_drawdown_R?.toFixed(2) ?? '—'}R</div>
              <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>worst observed</div>
            </div>
          </div>

          {/* R-multiple distribution */}
          <div style={s.card}>
            <div style={s.cardTitle}>R-Multiple Distribution</div>
            <RDistributionChart trades={allR} />
            <div style={{ display: 'flex', gap: 24, marginTop: 12, fontSize: 13, color: '#888' }}>
              <span>Win Rate: <b style={{ color: '#e2e8f0' }}>{m.win_rate != null ? `${(m.win_rate * 100).toFixed(1)}%` : '—'}</b></span>
              <span>Profit Factor: <b style={{ color: '#e2e8f0' }}>{m.profit_factor ?? '—'}</b></span>
              <span>Gross R: <b style={{ color: (m.gross_R || 0) >= 0 ? '#22c55e' : '#ef4444' }}>{m.gross_R?.toFixed(2) ?? '—'}R</b></span>
            </div>
          </div>

          {/* Monte Carlo */}
          <div style={s.card}>
            <div style={s.cardTitle}>Monte Carlo Risk Analysis ({mc.simulations ?? 1000} simulations)</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12 }}>
              {[
                { label: 'Median Final R (p50)', val: mc.final_R?.p50, accent: '#22c55e' },
                { label: 'Bad Case Final R (p05)', val: mc.final_R?.p05, accent: '#ef4444' },
                { label: 'Drawdown p90', val: mc.drawdown_R?.p90 ? `${mc.drawdown_R.p90}R` : '—', accent: '#f59e0b' },
                { label: 'Drawdown p95', val: mc.drawdown_R?.p95 ? `${mc.drawdown_R.p95}R` : '—', accent: '#f59e0b' },
                { label: 'Risk of Ruin (−10R)', val: mc.risk_of_ruin_minus_10R != null ? `${(mc.risk_of_ruin_minus_10R * 100).toFixed(1)}%` : '—', accent: mc.risk_of_ruin_minus_10R > 0.1 ? '#ef4444' : '#22c55e' },
                { label: 'P(positive)', val: mc.probability_final_R_positive != null ? `${(mc.probability_final_R_positive * 100).toFixed(1)}%` : '—', accent: '#8b5cf6' },
              ].map(({ label, val, accent }) => (
                <div key={label} style={{ background: '#0d0d1a', borderRadius: 8, padding: '14px 16px', border: '1px solid #2a2a4a' }}>
                  <div style={{ fontSize: 11, color: '#666', marginBottom: 6 }}>{label}</div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: accent }}>{val ?? '—'}</div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 12, fontSize: 12, color: '#666' }}>
              Objective: {report.objective_analysis?.verdict === 'PASS' ? '✅ PASS' : '❌ FAIL/INSUFFICIENT_EDGE'}
              {' · '}Target: {report.objective_analysis?.target?.minimum_final_R}R / max dd {report.objective_analysis?.target?.maximum_95pct_drawdown_R}R
            </div>
          </div>

          {/* Walk-Forward + Stress Test */}
          <div style={s.grid2}>
            <div style={s.card}>
              <div style={s.cardTitle}>Walk-Forward Stability</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: wf.status === 'PASS' ? '#22c55e' : '#ef4444', marginBottom: 8 }}>
                {wf.status || 'INSUFFICIENT_DATA'}
              </div>
              <div style={{ fontSize: 13, color: '#888', marginBottom: 12 }}>Pass rate: {wf.pass_rate != null ? `${(wf.pass_rate * 100).toFixed(0)}%` : '—'}</div>
              {wf.windows?.slice(0, 4).map((w: any, i: number) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '4px 0', color: '#94a3b8' }}>
                  <span>Window {w.window}</span>
                  <span style={{ color: '#888' }}>Train {w.train_avg_R?.toFixed(2)}R → Test {w.test_avg_R?.toFixed(2)}R</span>
                  <span style={{ color: w.passed ? '#22c55e' : '#ef4444' }}>{w.passed ? '✓' : '✗'}</span>
                </div>
              ))}
            </div>
            <div style={s.card}>
              <div style={s.cardTitle}>Stress Test Robustness</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: stress.status === 'ROBUST' ? '#22c55e' : '#ef4444', marginBottom: 8 }}>
                {stress.status || '—'}
              </div>
              <div style={{ fontSize: 13, color: '#888', marginBottom: 12 }}>Pass rate: {stress.pass_rate != null ? `${(stress.pass_rate * 100).toFixed(0)}%` : '—'}</div>
              {stress.scenarios?.map((sc: any, i: number) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '4px 0', color: '#94a3b8' }}>
                  <span style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>{sc.scenario}</span>
                  <span style={{ color: sc.passed ? '#22c55e' : '#ef4444' }}>{sc.avg_R?.toFixed(2)}R {sc.passed ? '✓' : '✗'}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Behavior + Lifestyle */}
          <div style={s.grid2}>
            <BehaviorCard discipline={discipline} />
            <LifestyleCard fit={fit} />
          </div>

          {/* Coach Insights */}
          <div style={s.card}>
            <div style={s.cardTitle}>Coach Insights</div>
            {report.coach_insights?.map((ins: string, i: number) => (
              <div key={i} style={s.insightItem}>💡 {ins}</div>
            ))}
          </div>

          {/* Next Actions */}
          <div style={s.card}>
            <div style={s.cardTitle}>Next Actions</div>
            {report.next_actions?.map((a: string, i: number) => (
              <div key={i} style={{ ...s.insightItem, color: '#6366f1' }}>→ {a}</div>
            ))}
          </div>
        </>
      )}

      <div style={s.disclaimer}>
        QuantOS Quant Coach is research/analytics only. Paper trading and backtests are hypothetical.
        Not financial advice. Do not use for real-money decisions.
      </div>
    </div>
  );
}
