'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { api, formatApiError } from '../../lib/api';

type Badge = { name: string; icon: string; description: string };

export default function AchievementsPage() {
  const [badges, setBadges] = useState<Badge[]>([]);
  const [profile, setProfile] = useState<any>(null);
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api('/trader-profile/me/achievements')
      .then((res: any) => { setBadges(res.achievements || []); setProfile(res.profile || null); })
      .catch(e => setMsg(formatApiError(e)))
      .finally(() => setLoading(false));
  }, []);

  const s = {
    page: { background: '#0d0d1a', minHeight: '100vh', padding: 24, color: '#e2e8f0', fontFamily: 'system-ui,sans-serif' },
    wrap: { maxWidth: 1100, margin: '0 auto' },
    h1: { fontSize: 34, fontWeight: 850, margin: '8px 0', background: 'linear-gradient(135deg,#6366f1,#a78bfa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' },
    sub: { color: '#94a3b8', lineHeight: 1.6 },
    grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(230px,1fr))', gap: 16, marginTop: 20 },
    card: { background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 14, padding: 20 },
    badge: { background: '#111827', border: '1px solid #334155', borderRadius: 16, padding: 18, minHeight: 150 },
    link: { color: '#a78bfa', textDecoration: 'none', marginRight: 14, fontSize: 13 },
    danger: { background: '#2a1a1a', border: '1px solid #ef444444', borderRadius: 10, padding: 12, color: '#fca5a5', marginTop: 14 },
  };

  if (loading) return <div style={s.page}><div style={s.wrap}><h1 style={s.h1}>Loading achievements…</h1></div></div>;

  return <div style={s.page}><div style={s.wrap}>
    <Link href="/dashboard" style={s.link}>← Dashboard</Link><Link href="/trader-profile" style={s.link}>Trader Profile</Link><Link href="/competitions" style={s.link}>Competitions</Link>
    <h1 style={s.h1}>Achievements</h1>
    <p style={s.sub}>Badges reward repeatable process: challenge participation, drawdown control, discipline, Quant Score, and larger paper-trade samples.</p>
    {msg && <div style={s.danger}>{msg}</div>}

    <div style={s.card}>
      <b>{profile?.user?.name || 'Trader'}</b> · {profile?.trader_type || 'New Quant'} · Best Quant Score: {Number(profile?.stats?.best_quant_score || 0).toFixed(1)}
    </div>

    <div style={s.grid}>
      {badges.map((b, i) => <div key={i} style={s.badge}>
        <div style={{ fontSize: 42 }}>{b.icon}</div>
        <h3 style={{ margin: '10px 0 6px' }}>{b.name}</h3>
        <p style={{ color: '#94a3b8', fontSize: 13, lineHeight: 1.5 }}>{b.description}</p>
      </div>)}
    </div>
  </div></div>;
}
