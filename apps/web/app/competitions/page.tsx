'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { api, formatApiError } from '../../lib/api';

type Competition = {
  id: string;
  title: string;
  description?: string;
  status: string;
  start_at: string;
  end_at: string;
  starting_balance: number;
  allowed_symbols?: string[];
  prize?: Record<string, string>;
  rules?: Record<string, unknown>;
};

type LeaderboardEntry = {
  id: string;
  display_name: string;
  return_pct: number;
  max_drawdown_pct: number;
  total_trades: number;
  win_rate_pct: number;
  gross_r: number;
  discipline_score: number;
  risk_score: number;
  quant_score: number;
  rank?: number;
  status: string;
};

const demoCompetition: Competition = {
  id: 'demo-weekly-quant-challenge',
  title: 'Weekly QuantOS BTC Discipline Challenge',
  description: 'A paper-only challenge where traders compete by risk-adjusted Quant Score, not profit alone.',
  status: 'scheduled',
  start_at: 'Next Sunday',
  end_at: 'Next Sunday + 2h',
  starting_balance: 100000,
  allowed_symbols: ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'],
  prize: { first: '3 months premium', second: '1 month premium', third: 'profile badge' },
  rules: { ranking: 'risk_adjusted_quant_score', no_real_money: true },
};

function fmtMoney(n?: number) {
  return `$${Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function fmtDate(value?: string) {
  if (!value) return '—';
  if (!value.includes('T')) return value;
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export default function CompetitionsPage() {
  const [competitions, setCompetitions] = useState<Competition[]>([]);
  const [selected, setSelected] = useState<Competition | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const activeCompetition = selected || competitions[0] || demoCompetition;

  async function loadCompetitions() {
    setLoading(true);
    setMsg('');
    try {
      const res = await api('/competitions');
      const items = (res as { competitions?: Competition[] }).competitions || [];
      setCompetitions(items);
      if (items.length) setSelected(items[0]);
    } catch (err) {
      setMsg(formatApiError(err));
    } finally {
      setLoading(false);
    }
  }

  async function loadLeaderboard(competitionId: string) {
    if (!competitionId || competitionId === demoCompetition.id) {
      setLeaderboard([]);
      return;
    }
    try {
      const res = await api(`/competitions/${competitionId}/leaderboard`);
      setLeaderboard((res as { leaderboard?: LeaderboardEntry[] }).leaderboard || []);
    } catch (err) {
      setMsg(formatApiError(err));
    }
  }

  useEffect(() => {
    loadCompetitions();
  }, []);

  useEffect(() => {
    if (activeCompetition?.id) loadLeaderboard(activeCompetition.id);
  }, [activeCompetition?.id]);

  const statusBuckets = useMemo(() => {
    const source = competitions.length ? competitions : [demoCompetition];
    return {
      active: source.filter(c => c.status === 'active'),
      scheduled: source.filter(c => c.status === 'scheduled' || c.status === 'draft'),
      completed: source.filter(c => c.status === 'completed'),
    };
  }, [competitions]);

  async function createDemoCompetition() {
    setBusy(true);
    setMsg('');
    try {
      const now = new Date();
      const start = new Date(now.getTime() + 24 * 60 * 60 * 1000);
      const end = new Date(start.getTime() + 2 * 60 * 60 * 1000);
      await api('/competitions', {
        method: 'POST',
        body: JSON.stringify({
          title: 'Weekly QuantOS Discipline Challenge',
          description: 'Paper-only competition ranked by risk-adjusted Quant Score. Highest profit alone does not win.',
          status: 'scheduled',
          start_at: start.toISOString(),
          end_at: end.toISOString(),
          starting_balance: 100000,
          allowed_symbols: ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT'],
          prize: { first: '3 months premium', second: '1 month premium', third: 'profile badge' },
          rules: {
            ranking: 'risk_adjusted_quant_score',
            max_drawdown_matters: true,
            no_real_money: true,
            goal: 'reward systematic paper trading, not gambling',
          },
        }),
      });
      setMsg('Competition created. Refreshing hub…');
      await loadCompetitions();
    } catch (err) {
      setMsg(formatApiError(err));
    } finally {
      setBusy(false);
    }
  }

  async function joinCompetition() {
    if (!activeCompetition?.id || activeCompetition.id === demoCompetition.id) {
      setMsg('Create a real competition first, then join it.');
      return;
    }
    setBusy(true);
    setMsg('');
    try {
      await api(`/competitions/${activeCompetition.id}/join`, { method: 'POST' });
      setMsg('Joined competition successfully. Start paper trading and submit your result after the session.');
      await loadLeaderboard(activeCompetition.id);
    } catch (err) {
      setMsg(formatApiError(err));
    } finally {
      setBusy(false);
    }
  }

  const s = {
    page: { background: '#0d0d1a', minHeight: '100vh', padding: 24, fontFamily: 'system-ui, sans-serif', color: '#e2e8f0' },
    hero: { maxWidth: 1100, margin: '0 auto 24px' },
    h1: { fontSize: 34, fontWeight: 800, margin: 0, background: 'linear-gradient(135deg,#6366f1,#8b5cf6,#a78bfa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' },
    sub: { color: '#94a3b8', fontSize: 15, lineHeight: 1.6, maxWidth: 820 },
    grid: { maxWidth: 1100, margin: '0 auto', display: 'grid', gridTemplateColumns: 'minmax(280px, 360px) 1fr', gap: 18 },
    card: { background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 14, padding: 20 },
    cardTitle: { fontSize: 13, color: '#94a3b8', textTransform: 'uppercase' as const, letterSpacing: 1, marginBottom: 12, fontWeight: 700 },
    compCard: { background: '#111827', border: '1px solid #2a2a4a', borderRadius: 12, padding: 14, marginBottom: 10, cursor: 'pointer' },
    compCardActive: { border: '1px solid #6366f1', background: '#1e1b4b' },
    btn: { background: '#6366f1', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 16px', cursor: 'pointer', fontWeight: 700, textDecoration: 'none', display: 'inline-block' },
    btnSec: { background: 'transparent', color: '#a78bfa', border: '1px solid #6366f1', borderRadius: 8, padding: '10px 16px', cursor: 'pointer', fontWeight: 700, textDecoration: 'none', display: 'inline-block', marginLeft: 10 },
    tag: { display: 'inline-block', background: '#312e81', border: '1px solid #6366f155', borderRadius: 999, padding: '4px 9px', color: '#c4b5fd', fontSize: 12, margin: '0 6px 6px 0' },
    danger: { background: '#2a1a1a', border: '1px solid #ef444444', borderRadius: 10, padding: 12, color: '#fca5a5', margin: '0 auto 18px', maxWidth: 1100 },
    table: { width: '100%', borderCollapse: 'collapse' as const, fontSize: 13 },
    th: { color: '#94a3b8', textAlign: 'left' as const, borderBottom: '1px solid #2a2a4a', padding: '10px 8px' },
    td: { borderBottom: '1px solid #2a2a4a', padding: '10px 8px', color: '#e2e8f0' },
    statGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12, margin: '16px 0' },
    stat: { background: '#0f172a', border: '1px solid #25324a', borderRadius: 10, padding: 12 },
    statLabel: { fontSize: 11, color: '#94a3b8', textTransform: 'uppercase' as const, letterSpacing: 0.5 },
    statValue: { fontSize: 18, fontWeight: 800, marginTop: 4 },
  };

  const allCompetitions = competitions.length ? competitions : [demoCompetition];

  return (
    <div style={s.page}>
      <div style={s.hero}>
        <Link href="/dashboard" style={{ color: '#94a3b8', textDecoration: 'none', fontSize: 13 }}>← Dashboard</Link>
        <h1 style={s.h1}>QuantOS Competition Hub</h1>
        <p style={s.sub}>
          Weekly paper-trading challenges with equal virtual capital, the same market window, and a risk-adjusted leaderboard.
          QuantOS rewards controlled returns, drawdown control, R quality, and discipline — not reckless all-in gambling.
        </p>
        <button style={s.btn} onClick={createDemoCompetition} disabled={busy}>{busy ? 'Working…' : 'Create Weekly Challenge'}</button>
        <Link href="/paper-trading" style={s.btnSec}>Go to Paper Trading</Link>
      </div>

      {msg && <div style={s.danger}>{msg}</div>}

      <div style={s.grid}>
        <div style={s.card}>
          <div style={s.cardTitle}>Competitions</div>
          {loading ? <div style={{ color: '#94a3b8' }}>Loading competitions…</div> : allCompetitions.map(c => (
            <div key={c.id} onClick={() => setSelected(c)} style={{ ...s.compCard, ...(activeCompetition.id === c.id ? s.compCardActive : {}) }}>
              <div style={{ fontWeight: 800, marginBottom: 6 }}>{c.title}</div>
              <div style={{ color: '#94a3b8', fontSize: 12, marginBottom: 8 }}>{c.status?.toUpperCase()} · {fmtDate(c.start_at)}</div>
              <div style={{ color: '#64748b', fontSize: 13 }}>{c.description || 'Paper challenge'}</div>
            </div>
          ))}

          <div style={{ marginTop: 18 }}>
            <div style={s.cardTitle}>Buckets</div>
            <div style={s.statGrid}>
              <div style={s.stat}><div style={s.statLabel}>Active</div><div style={s.statValue}>{statusBuckets.active.length}</div></div>
              <div style={s.stat}><div style={s.statLabel}>Scheduled</div><div style={s.statValue}>{statusBuckets.scheduled.length}</div></div>
              <div style={s.stat}><div style={s.statLabel}>Completed</div><div style={s.statValue}>{statusBuckets.completed.length}</div></div>
            </div>
          </div>
        </div>

        <div style={s.card}>
          <div style={s.cardTitle}>Challenge details</div>
          <h2 style={{ margin: '0 0 8px', fontSize: 24 }}>{activeCompetition.title}</h2>
          <p style={{ color: '#94a3b8', lineHeight: 1.6 }}>{activeCompetition.description}</p>
          <div style={s.statGrid}>
            <div style={s.stat}><div style={s.statLabel}>Starting balance</div><div style={s.statValue}>{fmtMoney(activeCompetition.starting_balance)}</div></div>
            <div style={s.stat}><div style={s.statLabel}>Start</div><div style={s.statValue}>{fmtDate(activeCompetition.start_at)}</div></div>
            <div style={s.stat}><div style={s.statLabel}>End</div><div style={s.statValue}>{fmtDate(activeCompetition.end_at)}</div></div>
            <div style={s.stat}><div style={s.statLabel}>Ranking</div><div style={s.statValue}>Quant Score</div></div>
          </div>

          <div style={{ marginTop: 12 }}>
            {(activeCompetition.allowed_symbols || []).map(sym => <span key={sym} style={s.tag}>{sym}</span>)}
          </div>

          <div style={{ marginTop: 16 }}>
            <button style={s.btn} onClick={joinCompetition} disabled={busy}>Join Challenge</button>
            <span style={{ color: '#94a3b8', marginLeft: 12, fontSize: 13 }}>Paper only · no broker · no real money</span>
          </div>

          <div style={{ marginTop: 28 }}>
            <div style={s.cardTitle}>Leaderboard</div>
            {leaderboard.length ? (
              <table style={s.table}>
                <thead>
                  <tr>
                    <th style={s.th}>Rank</th>
                    <th style={s.th}>Trader</th>
                    <th style={s.th}>Return</th>
                    <th style={s.th}>Max DD</th>
                    <th style={s.th}>Gross R</th>
                    <th style={s.th}>Discipline</th>
                    <th style={s.th}>Quant Score</th>
                  </tr>
                </thead>
                <tbody>
                  {leaderboard.map((e, i) => (
                    <tr key={e.id || i}>
                      <td style={s.td}>#{e.rank || i + 1}</td>
                      <td style={s.td}>{e.display_name}</td>
                      <td style={{ ...s.td, color: e.return_pct >= 0 ? '#22c55e' : '#ef4444' }}>{e.return_pct.toFixed(2)}%</td>
                      <td style={s.td}>{e.max_drawdown_pct.toFixed(2)}%</td>
                      <td style={s.td}>{e.gross_r.toFixed(2)}R</td>
                      <td style={s.td}>{e.discipline_score.toFixed(0)}/100</td>
                      <td style={{ ...s.td, fontWeight: 900, color: '#a78bfa' }}>{e.quant_score.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div style={{ color: '#94a3b8', background: '#0f172a', border: '1px dashed #334155', padding: 18, borderRadius: 12 }}>
                No leaderboard entries yet. Join the challenge, trade in paper mode, and submit a score after the session.
              </div>
            )}
          </div>

          <div style={{ marginTop: 24, color: '#64748b', fontSize: 12, lineHeight: 1.6 }}>
            Scoring model: return + gross R + win quality + discipline - drawdown penalty. This protects the product from becoming a gambling leaderboard.
          </div>
        </div>
      </div>
    </div>
  );
}
