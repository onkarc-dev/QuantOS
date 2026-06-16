'use client';
import { useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { ApiError, api, formatApiError, saveAuth } from '../../lib/api';

export default function LoginForm() {
  const searchParams = useSearchParams();
  const expired = searchParams.get('expired') === '1';

  const [email, setEmail] = useState('demo@prismflow.com');
  const [password, setPassword] = useState('demo123');
  const [name, setName] = useState('Onkar');
  const [otp, setOtp] = useState('');
  const [resetOtp, setResetOtp] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [resetRequested, setResetRequested] = useState(false);
  const [otpRequested, setOtpRequested] = useState(false);
  const [msg, setMsg] = useState(
    expired
      ? 'Your session expired. Please log in again.'
      : 'Login with your email and password, or register once with email OTP.'
  );
  const [busy, setBusy] = useState(false);

  async function login() {
    if (!email.trim() || !password) {
      setMsg('Email and password are required.');
      return;
    }
    setBusy(true);
    setMsg('Logging in…');
    try {
      const data = await api('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email: email.trim(), password }),
      });
      saveAuth(data);
      setMsg('Login successful. Redirecting…');
      window.location.href = '/dashboard';
    } catch (e) {
      setMsg('Login failed: ' + formatApiError(e));
      setBusy(false);
    }
  }

  async function requestOtp() {
    if (!email.trim() || !password) {
      setMsg('Email and password are required.');
      return;
    }
    if (password.length < 6) {
      setMsg('Password must be at least 6 characters.');
      return;
    }
    setBusy(true);
    setMsg('Generating OTP…');
    try {
      const data = await api('/auth/register/request-otp', {
        method: 'POST',
        body: JSON.stringify({ email: email.trim(), password, name: name.trim() }),
      }) as { message?: string; otp?: string };
      setOtpRequested(true);
      if (data.otp) setOtp(data.otp);
      setMsg(data.otp ? `OTP generated: ${data.otp}. Enter it and click Verify OTP.` : (data.message || 'OTP generated.'));
    } catch (e) {
      const text = formatApiError(e);
      if (e instanceof ApiError && e.status === 409) {
        window.alert('This email id is already registered. Go for login.');
      }
      setMsg('Register failed: ' + text);
    } finally {
      setBusy(false);
    }
  }

  async function requestPasswordReset() {
    if (!email.trim()) { setMsg('Enter your email first.'); return; }
    setBusy(true); setMsg('Sending password reset OTP…');
    try {
      const data = await api('/auth/password-reset/request-otp', { method: 'POST', body: JSON.stringify({ email: email.trim() }) }) as { message?: string; otp?: string };
      setResetRequested(true);
      if (data.otp) setResetOtp(data.otp);
      setMsg(data.otp ? `Reset OTP generated: ${data.otp}. Enter it with your new password.` : (data.message || 'Reset OTP sent.'));
    } catch (e) { setMsg('Password reset failed: ' + formatApiError(e)); }
    finally { setBusy(false); }
  }

  async function verifyPasswordReset() {
    if (!email.trim() || !resetOtp.trim() || !newPassword) { setMsg('Email, reset OTP and new password are required.'); return; }
    setBusy(true); setMsg('Updating password…');
    try {
      const data = await api('/auth/password-reset/verify', { method: 'POST', body: JSON.stringify({ email: email.trim(), otp: resetOtp.trim(), new_password: newPassword }) }) as { message?: string };
      setPassword(newPassword); setResetRequested(false); setNewPassword(''); setResetOtp('');
      setMsg(data.message || 'Password updated. Please log in.');
    } catch (e) { setMsg('Password reset failed: ' + formatApiError(e)); }
    finally { setBusy(false); }
  }

  async function verifyOtp() {
    if (!email.trim() || !otp.trim()) {
      setMsg('Email and OTP are required.');
      return;
    }
    setBusy(true);
    setMsg('Verifying OTP…');
    try {
      const data = await api('/auth/register/verify', {
        method: 'POST',
        body: JSON.stringify({ email: email.trim(), otp: otp.trim() }),
      });
      saveAuth(data);
      setMsg('Registration complete. Redirecting…');
      window.location.href = '/dashboard';
    } catch (e) {
      const text = formatApiError(e);
      if (e instanceof ApiError && e.status === 409) {
        window.alert('This email id is already registered. Go for login.');
      }
      setMsg('OTP verification failed: ' + text);
      setBusy(false);
    }
  }

  return (
    <>
      <div className="hero">
        <h1>Login / Register</h1>
        <p className="muted">First-time users register using email OTP. Existing users should log in.</p>
      </div>
      <div className="card" style={{ maxWidth: 620 }}>
        <label>Name<input value={name} onChange={e => setName(e.target.value)} disabled={busy} /></label><br /><br />
        <label>Email<input value={email} onChange={e => { setEmail(e.target.value); setOtpRequested(false); }} disabled={busy} /></label><br /><br />
        <label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} disabled={busy} /></label><br /><br />
        {otpRequested && (
          <>
            <label>Registration OTP<input value={otp} onChange={e => setOtp(e.target.value)} disabled={busy} placeholder="Enter 6-digit OTP" /></label><br /><br />
          </>
        )}
        {resetRequested && (
          <>
            <label>Password reset OTP<input value={resetOtp} onChange={e => setResetOtp(e.target.value)} disabled={busy} placeholder="Enter reset OTP" /></label><br /><br />
            <label>New password<input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} disabled={busy} /></label><br /><br />
          </>
        )}
        <button onClick={login} disabled={busy}>Login</button>{' '}
        <button className="secondary" onClick={requestOtp} disabled={busy}>Generate OTP</button>{' '}
        {otpRequested && <button className="secondary" onClick={verifyOtp} disabled={busy}>Verify OTP & Register</button>}{' '}
        <button className="secondary" onClick={requestPasswordReset} disabled={busy}>Forgot password?</button>{' '}
        {resetRequested && <button className="secondary" onClick={verifyPasswordReset} disabled={busy}>Verify Reset OTP</button>}
        <p className="muted">{msg}</p>
      </div>
    </>
  );
}
