'use client';
import { Suspense } from 'react';
import LoginForm from './LoginForm';

export default function Login() {
  return (
    <Suspense fallback={<div className="hero"><h1>Login / Register</h1><p className="muted">Loading…</p></div>}>
      <LoginForm />
    </Suspense>
  );
}
