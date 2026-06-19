'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { api, formatApiError } from '../../lib/api';

export default function AdminPage() {
  const [summary, setSummary] = useState<Record<string, number>>({});
  const [modules, setModules] = useState<any[]>([]);
  const [msg, setMsg] = useState('');

  async function load() {
    try {
      const [s, m] = await Promise.all([api('/admin/summary'), api('/admin/modules')]);
      setSummary((s as any).summary || {});
      setModules((m as any).modules || []);
    } catch (e) { setMsg(formatApiError(e)); }
  }
  useEffect(() => { load(); }, []);

  const st = {
    page: { background: '#0d0d1a', minHeight: '100vh', padding: 24, color: '#e2e8f0', fontFamily: 'system-ui,sans-serif' },
    wrap: { maxWidth: 1120, margin: '0 auto' },
    h1: { fontSize: 34, fontWeight: 850, background: 'linear-gradient(135deg,#6366f1,#a78bfa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' },
    grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(180px,1fr))', gap: 14 },
    card: { background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 14, padding: 18, marginTop: 16 },
    link: { color: '#a78bfa', marginRight: 14, textDecoration: 'none', fontSize: 13 },
    muted: { color: '#94a3b8' },
    danger: { background: '#2a1a1a', border: '1px solid #ef444444', borderRadius: 10, padding: 12, color: '#fca5a5', marginTop: 14 },
  };

  return <div style={st.page}><div style={st.wrap}>
    <Link href="/dashboard" style={st.link}>← Dashboard</Link><Link href="/organizations" style={st.link}>Organizations</Link><Link href="/growth" style={st.link}>Growth</Link>
    <h1 style={st.h1}>Admin Panel</h1>
    <p style={st.muted}>Founder/admin monitoring for QuantOS. Harden with admin RBAC before public production.</p>
    {msg && <div style={st.danger}>{msg}</div>}
    <div style={st.grid}>{Object.entries(summary).map(([k,v]) => <div key={k} style={st.card}><div style={{ color: '#94a3b8', fontSize: 12 }}>{k.replaceAll('_',' ').toUpperCase()}</div><div style={{ fontSize: 28, fontWeight: 900 }}>{v}</div></div>)}</div>
    <div style={st.card}><h3>Module readiness</h3>{modules.map((m,i) => <div key={i} style={{ borderBottom: '1px solid #2a2a4a', padding: '10px 0' }}><b>{m.name}</b> · <span style={st.muted}>{m.status}</span></div>)}</div>
  </div></div>;
}
