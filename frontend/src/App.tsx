import { Component, useEffect, useState, type ReactNode } from 'react';
import { Api } from './lib/api';
import type { Login, Session } from './lib/types';
import { AuthScreen } from './components/AuthScreen';
import { Dashboard } from './components/Dashboard';

type ActiveSession = { api: Api; user: Session; expiresAt: number };

export function App() {
  const [session, setSession] = useState<ActiveSession | null>(null);
  const [notice, setNotice] = useState('');
  function expire() {
    setSession(null);
    setNotice(
      'Your session has expired. Sign in again. If a payment was pending, check your activity before sending it again.',
    );
  }
  useEffect(() => {
    if (!session) return;
    const timer = window.setTimeout(expire, Math.max(0, session.expiresAt - Date.now()));
    return () => {
      window.clearTimeout(timer);
      // Late responses from this session must not expire a subsequently opened session.
      session.api.dispose();
    };
  }, [session]);
  async function login(result: Login) {
    const api = new Api(result.access_token, expire);
    const user = await api.request<Session>('/auth/me');
    setNotice('');
    setSession({ api, user, expiresAt: Date.now() + Number(result.expires_in) * 1000 });
  }
  async function logout() {
    if (!session) return;
    await session.api.request('/auth/logout', { method: 'POST' });
    setSession(null);
    setNotice('You have been signed out. See you soon.');
  }
  return session ? (
    <Dashboard api={session.api} user={session.user} onLogout={logout} />
  ) : (
    <AuthScreen onLogin={login} notice={notice} />
  );
}

export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed)
      return (
        <main className="fatal-error">
          <h1>Let’s get you back on track.</h1>
          <p>The interface encountered an unexpected error. Reload to sign in again.</p>
          <p>If you were sending a payment, check your activity before creating a new transfer.</p>
          <button className="button primary" onClick={() => location.reload()}>
            Reload LedgerX
          </button>
        </main>
      );
    return this.props.children;
  }
}
