'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { api, formatApiError } from '../../lib/api';

type Badge = { name: string; icon: string; description: string };
type Profile = {
  user?: { name?: string; email?: string };
  trader_type?: string;
  stats?: Record<string, any>;
  recent_competitions?: Array<Record<string, any>>;
  badges_preview?: Badge[];
};

function n(v: any, d = 0) { const x = Number(v); return Number.isFinite(x) ? x : d; }
function pct(v: any) { return `${n(v).toFixed(2)}%`; }

export default function TraderProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api('/trader-profile/me')
      .then(setProfile)
      .catch(e => setMsg(formatApiError(e)))
      .finally(() => setLoading(false));
  }, []);

  const stats = profile?.stats || {};
  const badges = profile?.badges_preview || [];

  const s = {
    page: { background: '#0d0d1a', minHeight: '100vh', padding: 24, fontFamily: 'system-ui,sans-serif', color: '#e2e8f0' },
    wrap: { maxWidth: 1120, margin: '0 auto' },
    h1: { fontSize: 34, fontWeight: 850, margin: '8px 0', background: 'linear-gradient(135deg,#6366f1,#a78bfa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' },
    sub: { color: '#94a3b8', lineHeight: 1.6 },
    grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(210px,1fr))', gap: 14, marginTop: 22 },
    card: { background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 14, padding: 18 },
    label: { color: '#94a3b8', fontSize: 12, textTransform: 'uppercase' as const, letterSpacing: 0.8 },
    value: { fontSize: 25, fontWeight: 850, marginTop: 7 },
    badge: { background: '#111827', border: '1px solid #334155', borderRadius: 14, padding: 16 },
    danger: { background: '#2a1a1a', border: '1px solid #ef444444', borderRadius: 10, padding: 12, color: '#fca5a5', marginTop: 14 },
    btn: { color: '#a78bfa', textDecoration: 'none', marginRight: 14, fontSize: 13 },
  };

  if (loading) return <div style={s.page}><div style={s.wrap}><h1 style={s.h1}>Loading profile…</h1></div></div>;

  return (
    <div style={s.page}>
      <div style={s.wrap}>
        <div><Link href="/dashboard" style={s.btn}>← Dashboard</Link><Link href="/ai-coach-v2" style={s.btn}>AI Coach v2 →</Link></div>
        <h1 style={s.h1}>Trader Profile</h1>
        <p style={s.sub}>Your QuantOS identity: strategy activity, competition record, discipline, risk behavior, and achievement progress.</p>
        {msg && <div style={s.danger}>{msg}</div>}

        <div style={{ ...s.card, marginTop: 18 }}>
          <div style={s.label}>Trader type</div>
          <div style={{ ...s.value, color: '#a78bfa' }}>{profile?.trader_type || 'New Quant'}</div>
          <div style={{ color: '#94a3b8', marginTop: 8 }}>{profile?.user?.name || 'Trader'} · {profile?.user?.email || ''}</div>
        </div>

        <div style={s.grid}>
          <div style={s.card}><div style={s.label}>Competitions</div><div style={s.value}>{n(stats.competitions_joined)}</div></div>
          <div style={s.card}><div style={s.label}>Avg return</div><div style={s.value}>{pct(stats.avg_return_pct)}</div></div>
          <div style={s.card}><div style={s.label}>Avg drawdown</div><div style={s.value}>{pct(stats.avg_drawdown_pct)}</div></div>
          <div style={s.card}><div style={s.label}>Best Quant Score</div><div style={s.value}>{n(stats.best_quant_score).toFixed(1)}</div></div>
          <div style={s.card}><div style={s.label}>Discipline</div><div style={s.value}>{n(stats.avg_discipline_score, 100).toFixed(0)}/100</div></div>
          <div style={s.card}><div style={s.label}>Strategies</div><div style={s.value}>{n(stats.strategies_created)}</div></div>
        </div>

        <h2 style={{ marginTop: 30 }}>Achievements</h2>
        <div style={s.grid}>
          {badges.map((b, i) => (
            <div key={i} style={s.badge}>
              <div style={{ fontSize: 34 }}>{b.icon}</div>
              <div style={{ fontWeight: 850, marginTop: 8 }}>{b.name}</div>
              <div style={{ color: '#94a3b8', marginTop: 6, fontSize: 13 }}>{b.description}</div>
            </div>
          ))}
        </div>

        <h2 style={{ marginTop: 30 }}>Recent competitions</h2>
        <div style={s.card}>
          {(profile?.recent_competitions || []).length ? profile!.recent_competitions!.map((e, i) => (
            <div key={i} style={{ borderBottom: '1px solid #2a2a4a', padding: '10px 0' }}>
              <b>{e.status}</b> · Return {pct(e.return_pct)} · DD {pct(e.max_drawdown_pct)} · Quant Score {n(e.quant_score).toFixed(1)}
            </div>
          )) : <div style={{ color: '#94a3b8' }}>No competition history yet. Join a weekly challenge to build your profile.</div>}
        </div>
      </div>
    </div>
  );
}
