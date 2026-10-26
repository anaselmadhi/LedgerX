import { useState, type FormEvent } from 'react';
import { Api } from '../lib/api';
import type { Login } from '../lib/types';
import { Brand, Icon } from './Icon';
import { ErrorNotice } from './ui';

export function AuthScreen({
  onLogin,
  notice,
}: {
  onLogin: (login: Login) => Promise<void>;
  notice: string;
}) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [created, setCreated] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const api = new Api();
      const body = { username: username.trim(), password };
      if (mode === 'register') {
        await api.request('/auth/register', { method: 'POST', body });
        setCreated(true);
        setMode('login');
      }
      const result = await api.request<Login>('/auth/login', { method: 'POST', body });
      await onLogin(result);
      setPassword('');
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="auth-page">
      <section className="auth-story">
        <Brand />
        <span className="outline-pill">
          <span className="status-dot" />A little more clarity. A lot more control.
        </span>
        <div className="auth-headline">
          <p className="eyebrow">MONEY, MINUS THE NOISE</p>
          <h1>
            Your money.
            <br />
            In clear <em>view.</em>
          </h1>
          <p>A thoughtful space for your accounts, transfers and everything in between.</p>
        </div>
        <div className="auth-art" aria-hidden="true">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="art-card">
            <Brand compact />
            <span>BUILT FOR CLARITY</span>
            <div className="art-lines">
              <i />
              <i />
              <i />
            </div>
            <p>
              Every movement.
              <br />
              Accounted for.
            </p>
            <span className="art-card-footer">
              LEDGERX <Icon name="swap" />
            </span>
          </div>
          <span className="art-badge">
            <Icon name="check" /> Every cent counts
          </span>
        </div>
        <footer>
          <span>Independent by design.</span>
          <span>Portfolio edition / 01</span>
        </footer>
      </section>
      <section className="auth-form-side">
        <div className="auth-top">
          <span className="demo-pill">Fictitious funds only</span>
          <a href="/docs" target="_blank" rel="noreferrer">
            Explore the API <Icon name="send" size={14} />
          </a>
        </div>
        <div className="auth-form-wrap">
          <div className="auth-mobile-brand">
            <Brand />
          </div>
          <div className="small-symbol">
            <Icon name={mode === 'login' ? 'lock' : 'plus'} size={25} />
          </div>
          <h2>{mode === 'login' ? 'Good to see you.' : 'Make room for clarity.'}</h2>
          <p className="muted">
            {mode === 'login'
              ? 'Sign in to your LedgerX workspace.'
              : 'Create your profile. Your first account is a click away.'}
          </p>
          <div className="auth-tabs" aria-label="Authentication mode">
            <button
              type="button"
              className={mode === 'login' ? 'active' : ''}
              disabled={busy}
              onClick={() => {
                setMode('login');
                setError(null);
              }}
            >
              Sign in
            </button>
            <button
              type="button"
              className={mode === 'register' ? 'active' : ''}
              disabled={busy}
              onClick={() => {
                setMode('register');
                setError(null);
              }}
            >
              Create profile
            </button>
          </div>
          {notice && (
            <p className="info-notice" role="status">
              {notice}
            </p>
          )}
          {created && <p className="info-notice">Profile created. You can now sign in.</p>}
          <form onSubmit={submit}>
            <fieldset disabled={busy}>
              <label htmlFor="username">Username</label>
              <input
                id="username"
                name="username"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                minLength={3}
                maxLength={64}
                pattern="[a-zA-Z0-9][a-zA-Z0-9_.\-]*"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="your.username"
              />
              <label htmlFor="password">Password</label>
              <div className="password-input">
                <input
                  id="password"
                  name="password"
                  type={visible ? 'text' : 'password'}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  minLength={12}
                  maxLength={128}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 12 characters"
                />
                <button
                  type="button"
                  className="icon-button"
                  aria-label={visible ? 'Hide password' : 'Show password'}
                  onClick={() => setVisible(!visible)}
                >
                  <Icon name="eye" />
                </button>
              </div>
              {mode === 'register' && (
                <p className="field-hint">
                  Use 3–64 letters, numbers, dots, underscores or hyphens for your username. Choose
                  a unique password.
                </p>
              )}
              <ErrorNotice error={error} />
              <button className="button primary auth-submit" type="submit">
                {busy ? (
                  <>
                    <span className="spinner" />
                    Just a moment…
                  </>
                ) : (
                  <>
                    {mode === 'login' ? 'Sign in to LedgerX' : 'Create my profile'}
                    <Icon name="arrow" />
                  </>
                )}
              </button>
            </fieldset>
          </form>
          <p className="auth-note">
            <Icon name="shield" size={17} /> Your session stays in this tab’s memory.
            <br />
            Reloading the page signs you out.
          </p>
        </div>
        <footer className="auth-disclaimer">
          A local financial demo. No real money, bank connection or deposit protection.
        </footer>
      </section>
    </main>
  );
}
