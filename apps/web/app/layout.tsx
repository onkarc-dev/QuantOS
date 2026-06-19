import './globals.css';
import type { Metadata } from 'next';
import AuthProvider from '../components/AuthProvider';
import TopNav from '../components/TopNav';

export const metadata: Metadata = {
  title: 'QuantOS — Personal Quant Operating System',
  description: 'Paper-trading quant research, analytics, competitions, Quant Coach, and market intelligence.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <TopNav />
        <main><AuthProvider>{children}</AuthProvider></main>
      </body>
    </html>
  );
}
