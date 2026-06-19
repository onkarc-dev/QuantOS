'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import ProfileMenu from './ProfileMenu';

const NAV = [
  { href: '/dashboard', label: 'Command Center' },
  { href: '/strategy-builder', label: 'Strategy' },
  { href: '/backtests', label: 'Backtests' },
  { href: '/paper-trading', label: 'Paper Trading' },
  { href: '/analytics', label: 'Analytics' },
  { href: '/quant-coach', label: 'Quant Coach' },
  { href: '/alternative-data', label: 'Market Intel' },
  { href: '/regime-dashboard', label: 'Regime' },
  { href: '/competitions', label: 'Competitions' },
  { href: '/achievements', label: 'Achievements' },
  { href: '/trader-profile', label: 'Profile' },
  { href: '/admin', label: 'Admin' },
];

export default function TopNav() {
  const pathname = usePathname() || '/dashboard';
  return <nav style={{
    background: '#0d0d1a',
    borderBottom: '1px solid #2a2a4a',
    padding: '0 24px',
    display: 'flex',
    alignItems: 'center',
    minHeight: 56,
    gap: 0,
    position: 'sticky',
    top: 0,
    zIndex: 100,
  }}>
    <Link href="/dashboard" style={{
      fontWeight: 900,
      fontSize: 18,
      color: '#6366f1',
      textDecorationLine: 'none',
      marginRight: 22,
      letterSpacing: -0.5,
      whiteSpace: 'nowrap',
    }}>
      Quant<span style={{ color: '#8b5cf6' }}>OS</span>
    </Link>
    <div style={{ display: 'flex', gap: 4, flex: 1, overflowX: 'auto', padding: '8px 0' }}>
      {NAV.map(({ href, label }) => {
        const active = pathname === href || pathname.startsWith(href + '/');
        return <Link key={href} href={href} style={{
          color: active ? '#ffffff' : '#94a3b8',
          textDecorationLine: active ? 'underline' : 'none',
          textUnderlineOffset: 7,
          textDecorationThickness: 2,
          background: active ? '#312e81' : 'transparent',
          border: active ? '1px solid #6366f177' : '1px solid transparent',
          padding: '7px 11px',
          borderRadius: 8,
          fontSize: 12,
          fontWeight: active ? 900 : 650,
          whiteSpace: 'nowrap',
        }}>
          {label}
        </Link>;
      })}
    </div>
    <div style={{
      fontSize: 11,
      color: '#94a3b8',
      background: '#1a1a2e',
      border: '1px solid #2a2a4a',
      borderRadius: 6,
      padding: '4px 10px',
      whiteSpace: 'nowrap',
      marginLeft: 10,
    }}>
      📄 Paper only · No real money
    </div>
    <ProfileMenu />
  </nav>;
}
