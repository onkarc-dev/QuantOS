'use client';

import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const qualityData = [
  { name: 'Discipline', score: 92 },
  { name: 'Setup', score: 80 },
  { name: 'Risk', score: 84 },
  { name: 'Journal', score: 68 },
];

const rMultipleData = [
  { name: '-2R', trades: 1 },
  { name: '-1R', trades: 6 },
  { name: '0R', trades: 4 },
  { name: '+1R', trades: 12 },
  { name: '+2R', trades: 8 },
  { name: '+3R+', trades: 3 },
];

const equityData = [
  { trade: 1, equity: -1.0 },
  { trade: 5, equity: 1.4 },
  { trade: 10, equity: 0.2 },
  { trade: 15, equity: 3.8 },
  { trade: 20, equity: 5.1 },
  { trade: 30, equity: 7.6 },
  { trade: 42, equity: 7.6 },
];

const card = {
  background: '#1a1a2e',
  border: '1px solid #2a2a4a',
  borderRadius: 14,
  padding: 18,
  marginTop: 16,
};

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return <div style={card}>
    <h3 style={{ marginTop: 0 }}>{title}</h3>
    {children}
  </div>;
}

export default function QuantCoachVisuals() {
  return <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(300px,1fr))', gap: 16 }}>
    <ChartCard title="Process Quality">
      <ResponsiveContainer width="100%" height={190}>
        <BarChart data={qualityData} margin={{ top: 10, right: 8, left: -18, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a" />
          <XAxis dataKey="name" stroke="#94a3b8" tick={{ fontSize: 11 }} />
          <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
          <Tooltip contentStyle={{ background: '#111827', border: '1px solid #334155', color: '#e2e8f0' }} />
          <Bar dataKey="score" radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>

    <ChartCard title="R-Multiple Distribution">
      <ResponsiveContainer width="100%" height={190}>
        <BarChart data={rMultipleData} margin={{ top: 10, right: 8, left: -18, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a" />
          <XAxis dataKey="name" stroke="#94a3b8" tick={{ fontSize: 11 }} />
          <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
          <Tooltip contentStyle={{ background: '#111827', border: '1px solid #334155', color: '#e2e8f0' }} />
          <Bar dataKey="trades" radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>

    <ChartCard title="Sample Equity Curve">
      <ResponsiveContainer width="100%" height={190}>
        <LineChart data={equityData} margin={{ top: 10, right: 8, left: -18, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a" />
          <XAxis dataKey="trade" stroke="#94a3b8" tick={{ fontSize: 11 }} />
          <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
          <Tooltip contentStyle={{ background: '#111827', border: '1px solid #334155', color: '#e2e8f0' }} formatter={(v: any) => [`${Number(v).toFixed(2)}R`, 'Cumulative R']} />
          <Line type="monotone" dataKey="equity" strokeWidth={3} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  </div>;
}
