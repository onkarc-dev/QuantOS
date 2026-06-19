import './globals.css';
import type { Metadata } from 'next';
import Link from 'next/link';
import AuthProvider from '../components/AuthProvider';
import ProfileMenu from '../components/ProfileMenu';

export const metadata: Metadata = {
  title: 'QuantOS — Personal Quant Operating System',
  description: 'Paper-trading quant research, analytics, competitions, AI coaching, and market intelligence. Not financial advice.',
};

const NAV = [
  { href: '/dashboard', label: 'Command Center' },
  { href: '/strategy-builder', label: 'Strategy' },
  { href: '/backtests', label: 'Backtests' },
  { href: '/paper-trading', label: 'Paper Trading' },
  { href: '/analytics', label: 'Analytics' },
  { href: '/ai-coach-v2', label: 'AI Coach' },
  { href: '/alternative-data', label: 'Market Intel' },
  { href: '/regime-dashboard', label: 'Regime' },
  { href: '/competitions', label: 'Competitions' },
  { href: '/achievements', label: 'Achievements' },
  { href: '/trader-profile', label: 'Profile' },
  { href: '/admin', label: 'Admin' },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <nav style={{
          background: '#0d0d1a',
          borderBottom: '1px solid #2a2a4a',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          minHeight: 56,
          gap: 0,
          position: 'sticky' as const,
          top: 0,
          zIndex: 100,
        }}>
          <Link href="/dashboard" style={{
            fontWeight: 900,
            fontSize: 18,
            color: '#6366f1',
            textDecoration: 'none',
            marginRight: 22,
            letterSpacing: -0.5,
            whiteSpace: 'nowrap' as const,
          }}>
            Quant<span style={{ color: '#8b5cf6' }}>OS</span>
          </Link>
          <div style={{ display: 'flex', gap: 4, flex: 1, overflowX: 'auto' as const, padding: '8px 0' }}>
            {NAV.map(({ href, label }) => (
              <Link key={href} href={href} style={{
                color: '#94a3b8',
                textDecoration: 'none',
                padding: '6px 10px',
                borderRadius: 8,
                fontSize: 12,
                fontWeight: 650,
                whiteSpace: 'nowrap' as const,
              }}>
                {label}
              </Link>
            ))}
          </div>
          <div style={{
            fontSize: 11,
            color: '#94a3b8',
            background: '#1a1a2e',
            border: '1px solid #2a2a4a',
            borderRadius: 6,
            padding: '4px 10px',
            whiteSpace: 'nowrap' as const,
            marginLeft: 10,
          }}>
            📄 Paper only · No real money
          </div>
          <ProfileMenu />
        </nav>
        <main><AuthProvider>{children}</AuthProvider></main>
      </body>
    </html>
  );
}
