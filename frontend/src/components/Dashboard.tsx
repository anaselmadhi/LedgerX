import { useEffect, useRef, useState } from 'react';
import { Api } from '../lib/api';
import { money, shortId } from '../lib/money';
import type { Account, AccountPage, Audit, Entry, Session } from '../lib/types';
import { ActivityChart, ActivityTable, TransferDetails, useHistory } from './Activity';
import { Brand, Icon, type IconName } from './Icon';
import { PaymentModal, type PaymentMode } from './PaymentModal';
import { CopyButton, ErrorNotice, Loading, Modal } from './ui';

type Page = 'overview' | 'accounts' | 'activity' | 'operations';
const pages: { id: Page; label: string; icon: IconName }[] = [
  { id: 'overview', label: 'Overview', icon: 'grid' },
  { id: 'accounts', label: 'My accounts', icon: 'wallet' },
  { id: 'activity', label: 'Activity', icon: 'swap' },
  { id: 'operations', label: 'Operations', icon: 'shield' },
];

export function Dashboard({
  api,
  user,
  onLogout,
}: {
  api: Api;
  user: Session;
  onLogout: () => Promise<void>;
}) {
  const [page, setPage] = useState<Page>('overview');
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [after, setAfter] = useState<string | null>(null);
  const [selected, setSelected] = useState('');
  const selectedRef = useRef('');
  selectedRef.current = selected;
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(true);
  const [moreBusy, setMoreBusy] = useState(false);
  const generation = useRef(0);
  const [error, setError] = useState<unknown>(null);
  const [filter, setFilter] = useState('all');
  const [create, setCreate] = useState(false);
  const [payment, setPayment] = useState<PaymentMode | null>(null);
  const [detail, setDetail] = useState<Entry | null>(null);
  const [mobileNav, setMobileNav] = useState(false);
  const [logoutBusy, setLogoutBusy] = useState(false);
  const account = accounts.find((a) => a.id === selected);
  const history = useHistory(api, account?.id, revision);
  const entries = history.data?.items || [];
  const incoming = entries.reduce((s, e) => s + (e.amount > 0n ? e.amount : 0n), 0n);
  const outgoing = entries.reduce((s, e) => s + (e.amount < 0n ? -e.amount : 0n), 0n);
  useEffect(() => {
    let active = true;
    generation.current += 1;
    setMoreBusy(false);
    setBusy(true);
    setError(null);
    (async () => {
      const result = await api.request<AccountPage>('/accounts?limit=50');
      const chosen = selectedRef.current;
      if (chosen && !result.items.some((a) => a.id === chosen)) {
        const current = await api.request<Account>(`/accounts/${chosen}`);
        result.items.unshift(current);
      }
      if (!active) return;
      setAccounts(result.items);
      setAfter(result.next_after);
      setSelected((current) => current || result.items[0]?.id || '');
    })()
      .catch((e) => {
        if (active) setError(e);
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, [api, revision]);
  async function moreAccounts() {
    if (!after || moreBusy) return;
    const current = generation.current;
    setMoreBusy(true);
    setError(null);
    try {
      const result = await api.request<AccountPage>(`/accounts?limit=50&after=${after}`);
      if (current !== generation.current) return;
      setAccounts((previous) => [
        ...new Map([...previous, ...result.items].map((a) => [a.id, a])).values(),
      ]);
      setAfter(result.next_after);
    } catch (e) {
      if (current === generation.current) setError(e);
    } finally {
      if (current === generation.current) setMoreBusy(false);
    }
  }
  function refresh() {
    setRevision((n) => n + 1);
  }
  function navigate(next: Page) {
    setPage(next);
    setMobileNav(false);
  }
  const currentTitle = pages.find((p) => p.id === page)!.label;
  return (
    <div className="app-layout">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      {mobileNav && (
        <button
          className="nav-scrim"
          aria-label="Close navigation"
          onClick={() => setMobileNav(false)}
        />
      )}
      <aside className={`sidebar ${mobileNav ? 'is-open' : ''}`}>
        <Brand />
        <div className="workspace-label">
          <span className="workspace-symbol">L</span>
          <div>
            Personal workspace<small>Portfolio edition</small>
          </div>
          <span className="workspace-dot" />
        </div>
        <p className="nav-label">WORKSPACE</p>
        <nav aria-label="Main navigation">
          {pages
            .filter((p) => p.id !== 'operations' || user.is_admin)
            .map((item) => (
              <button
                key={item.id}
                className={page === item.id ? 'active' : ''}
                aria-current={page === item.id ? 'page' : undefined}
                onClick={() => navigate(item.id)}
              >
                <Icon name={item.icon} />
                {item.label}
                {page === item.id && <span className="nav-active-dot" />}
              </button>
            ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <span className="small-symbol">
              <Icon name="shield" />
            </span>
            <h3>
              Small details.
              <br />
              Solid foundations.
            </h3>
            <p>Every movement has a place. Every cent has a record.</p>
            <a href="/docs" target="_blank" rel="noreferrer">
              Explore the API
              <Icon name="send" size={15} />
            </a>
          </div>
          <div className="sidebar-footer">
            <span className="status-dot" />
            <span>Local demo workspace</span>
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              type="button"
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              aria-expanded={mobileNav}
              onClick={() => setMobileNav(!mobileNav)}
            >
              <Icon name="menu" />
            </button>
            <span>Workspace</span>
            <Icon name="chevron" size={13} />
            <strong>{currentTitle}</strong>
          </div>
          <div className="topbar-right">
            <span className="demo-pill">Demo mode</span>
            <div className="profile-avatar">{user.username.slice(0, 2).toUpperCase()}</div>
            <div className="profile-name">
              <strong>{user.username}</strong>
              <small>{user.is_admin ? 'Administrator' : 'Personal account'}</small>
            </div>
            <button
              type="button"
              className="icon-button logout"
              aria-label="Sign out"
              title="Sign out"
              disabled={logoutBusy}
              onClick={async () => {
                setLogoutBusy(true);
                try {
                  await onLogout();
                } catch (e) {
                  setError(e);
                } finally {
                  setLogoutBusy(false);
                }
              }}
            >
              <Icon name="logout" size={18} />
            </button>
          </div>
        </header>
        <main id="main-content" className="main-content">
          <div className="page-heading">
            <div>
              <p className="eyebrow">YOUR MONEY, IN CLEAR VIEW</p>
              <h1>{page === 'overview' ? `Hello, ${user.username}.` : currentTitle}</h1>
              <p>
                {page === 'overview'
                  ? 'A little overview. A lot of peace of mind.'
                  : page === 'accounts'
                    ? 'Your everyday money, organised your way.'
                    : page === 'activity'
                      ? 'Every movement, right where you need it.'
                      : 'Independent checks for a balanced ledger.'}
              </p>
            </div>
            <div className="heading-actions">
              <button
                type="button"
                className="icon-button refresh-button"
                aria-label="Refresh accounts and activity"
                disabled={busy}
                onClick={refresh}
              >
                <Icon name="refresh" />
              </button>
              {page !== 'operations' && (
                <button type="button" className="button secondary" onClick={() => setCreate(true)}>
                  <Icon name="plus" size={17} />
                  Open an account
                </button>
              )}
            </div>
          </div>
          <ErrorNotice error={error} />
          {!!error && accounts.length > 0 && (
            <p className="field-hint">
              Previously loaded balances are shown. Refresh to retrieve current data.
            </p>
          )}
          {page === 'operations' ? (
            <Operations api={api} />
          ) : (
            <>
              {busy && !accounts.length ? (
                <Loading />
              ) : !accounts.length && !error ? (
                <section className="panel onboarding">
                  <div className="onboarding-visual">
                    <span className="currency-icon large">€</span>
                    <span className="onboarding-orbit" />
                  </div>
                  <p className="eyebrow">YOUR NEXT CHAPTER STARTS HERE</p>
                  <h2>A home for your money.</h2>
                  <p>
                    Open your first EUR account. Receive demo funds,
                    <br className="desktop-only" /> send a payment, and watch your activity take
                    shape.
                  </p>
                  <button className="button primary" type="button" onClick={() => setCreate(true)}>
                    <Icon name="plus" size={18} />
                    Open my first account
                  </button>
                  <div className="onboarding-steps">
                    <span>
                      <b>01</b>Open an account
                    </span>
                    <span>
                      <b>02</b>Receive demo funds
                    </span>
                    <span>
                      <b>03</b>Make your first transfer
                    </span>
                  </div>
                  <p className="field-hint">
                    A demo administrator can fund your account using its ID. Regular profiles cannot
                    create money.
                  </p>
                </section>
              ) : (
                account && (
                  <>
                    <div className="account-toolbar">
                      <label htmlFor="active-account">Viewing account</label>
                      <select
                        id="active-account"
                        value={selected}
                        onChange={(e) => setSelected(e.target.value)}
                      >
                        {accounts.map((a) => (
                          <option key={a.id} value={a.id}>
                            EUR account · {a.id.slice(-6)}
                          </option>
                        ))}
                      </select>
                      <span className="toolbar-date">
                        {new Date().toLocaleDateString('en-GB', {
                          weekday: 'short',
                          day: 'numeric',
                          month: 'long',
                          year: 'numeric',
                        })}
                      </span>
                    </div>
                    {page === 'overview' && (
                      <>
                        <div className="overview-grid">
                          <section className="balance-card">
                            <div className="balance-top">
                              <span>
                                <span className="currency-icon">€</span> Euro account
                              </span>
                              <span className="balance-state">Available</span>
                            </div>
                            <p className="balance-label">Your balance</p>
                            <div className="balance-value" data-testid="selected-balance">
                              {money(account.balance)}
                            </div>
                            <div className="balance-id">
                              <span>EUR · {shortId(account.id)}</span>
                              <CopyButton value={account.id} />
                            </div>
                            <div className="balance-actions">
                              <button
                                className="button lime"
                                type="button"
                                onClick={() => setPayment({ kind: 'transfer' })}
                              >
                                <Icon name="send" size={18} />
                                Send money
                              </button>
                              <button
                                className="button glass"
                                type="button"
                                onClick={() => {
                                  setPage('accounts');
                                }}
                              >
                                <Icon name="receive" size={18} />
                                Receive
                              </button>
                            </div>
                            <span className="balance-decoration" aria-hidden="true" />
                          </section>
                          <section className="panel movement-panel">
                            <div className="section-heading">
                              <h2>Money in motion</h2>
                              <span className="subtle-tag">7 days</span>
                            </div>
                            {history.busy ? (
                              <Loading label="Loading activity…" />
                            ) : history.error ? (
                              <ErrorNotice error={history.error} />
                            ) : (
                              <ActivityChart entries={entries} />
                            )}
                          </section>
                        </div>
                        <div className="summary-grid">
                          <div className="summary-card">
                            <span className="transaction-icon incoming">
                              <Icon name="receive" />
                            </span>
                            <div>
                              <span>Money in</span>
                              <strong>
                                {history.busy || history.error ? '—' : money(incoming)}
                              </strong>
                              <small>Loaded activity</small>
                            </div>
                          </div>
                          <div className="summary-card">
                            <span className="transaction-icon outgoing">
                              <Icon name="send" />
                            </span>
                            <div>
                              <span>Money out</span>
                              <strong>
                                {history.busy || history.error ? '—' : money(outgoing)}
                              </strong>
                              <small>Loaded activity</small>
                            </div>
                          </div>
                          <div className="summary-card">
                            <span className="transaction-icon neutral">
                              <Icon name="wallet" />
                            </span>
                            <div>
                              <span>Your accounts</span>
                              <strong>
                                {accounts.length}
                                {after ? '+' : ''}
                                <small> EUR</small>
                              </strong>
                              <small>
                                {after ? 'More accounts available' : 'Ready for the everyday'}
                              </small>
                            </div>
                          </div>
                        </div>
                      </>
                    )}
                    {page === 'accounts' && (
                      <>
                        <div className="accounts-grid">
                          {accounts.map((a) => (
                            <button
                              type="button"
                              key={a.id}
                              className={`account-card ${selected === a.id ? 'selected' : ''}`}
                              aria-pressed={selected === a.id}
                              onClick={() => setSelected(a.id)}
                            >
                              <span className="account-card-top">
                                <span className="currency-icon">€</span>
                                <span>
                                  {selected === a.id ? (
                                    <Icon name="check" />
                                  ) : (
                                    <Icon name="chevron" />
                                  )}
                                </span>
                              </span>
                              <span>Euro account</span>
                              <strong>{money(a.balance)}</strong>
                              <span className="mono">EUR · {shortId(a.id)}</span>
                            </button>
                          ))}
                          <button
                            type="button"
                            className="new-account-card"
                            onClick={() => setCreate(true)}
                          >
                            <span className="empty-icon">
                              <Icon name="plus" />
                            </span>
                            <strong>A little more space</strong>
                            <span>Open another EUR account</span>
                          </button>
                        </div>
                        <section className="panel account-details">
                          <div className="section-heading">
                            <h2>Account details</h2>
                            <span className="completed-badge">{account.currency}</span>
                          </div>
                          <p className="muted">
                            Share this account ID with another LedgerX user to receive a payment.
                          </p>
                          <div className="account-id-box">
                            <code>{account.id}</code>
                            <CopyButton value={account.id} />
                          </div>
                          <dl className="detail-list">
                            <div>
                              <dt>Account holder</dt>
                              <dd>{user.username}</dd>
                            </div>
                            <div>
                              <dt>Opened</dt>
                              <dd>{new Date(account.created_at).toLocaleDateString('en-GB')}</dd>
                            </div>
                            <div>
                              <dt>Available balance</dt>
                              <dd>{money(account.balance)}</dd>
                            </div>
                          </dl>
                          <div className="modal-actions">
                            <button
                              type="button"
                              className="button primary"
                              onClick={() => setPayment({ kind: 'transfer' })}
                            >
                              <Icon name="send" size={17} />
                              Send money
                            </button>
                            {user.dev_funding_enabled && (
                              <button
                                type="button"
                                className="button secondary"
                                onClick={() => setPayment({ kind: 'funding' })}
                              >
                                <Icon name="plus" size={17} />
                                Add demo funds
                              </button>
                            )}
                          </div>
                          <p className="field-hint">
                            This is an internal demo account ID, not an IBAN. Transfers stay inside
                            LedgerX.
                          </p>
                        </section>
                      </>
                    )}
                    {(page === 'overview' || page === 'activity') && (
                      <section className="panel activity-panel">
                        <div className="section-heading">
                          <div>
                            <h2>{page === 'overview' ? 'Recent activity' : 'Account activity'}</h2>
                            <p>
                              {page === 'overview'
                                ? 'The latest moves in your account.'
                                : 'Select a payment to view its details or return funds.'}
                            </p>
                          </div>
                          {page === 'overview' && (
                            <button
                              type="button"
                              className="text-button"
                              onClick={() => navigate('activity')}
                            >
                              View activity
                              <Icon name="arrow" size={16} />
                            </button>
                          )}
                        </div>
                        {history.busy ? (
                          <Loading label="Loading activity…" />
                        ) : history.error ? (
                          <>
                            <ErrorNotice error={history.error} />
                            <button className="button secondary" onClick={refresh}>
                              Try again
                            </button>
                          </>
                        ) : (
                          <>
                            <ActivityTable
                              entries={page === 'overview' ? entries.slice(0, 5) : entries}
                              onSelect={setDetail}
                              filter={filter}
                              onFilter={setFilter}
                            />
                            {page === 'activity' && history.data?.next_cursor && (
                              <div className="load-more">
                                <button className="button secondary" onClick={history.more}>
                                  Load older activity
                                  <Icon name="down" size={16} />
                                </button>
                              </div>
                            )}
                            {page === 'activity' && entries.length > 0 && (
                              <p className="activity-footnote">
                                {entries.length} entries loaded
                                {history.data?.next_cursor
                                  ? ' · More available'
                                  : ' · End of activity'}
                                . Refunds appear as separate payments.
                              </p>
                            )}
                          </>
                        )}
                      </section>
                    )}
                    {after && (
                      <div className="load-more">
                        <button
                          className="button secondary"
                          disabled={moreBusy || busy}
                          onClick={moreAccounts}
                        >
                          {moreBusy ? 'Loading…' : 'Load more accounts'}
                          <Icon name="down" size={16} />
                        </button>
                      </div>
                    )}
                  </>
                )
              )}
            </>
          )}
          <footer className="workspace-footer">
            <span>
              <Icon name="shield" size={14} />
              Fictitious funds. Real engineering.
            </span>
            <span>LedgerX · Portfolio edition</span>
          </footer>
        </main>
      </div>
      {create && (
        <CreateAccount
          api={api}
          onClose={() => setCreate(false)}
          onCreated={(created) => {
            setAccounts((prev) => [created, ...prev]);
            setSelected(created.id);
            setCreate(false);
            setPage('accounts');
          }}
        />
      )}
      {payment && account && (
        <PaymentModal
          key={`${account.id}:${payment.kind}`}
          api={api}
          account={account}
          accounts={accounts}
          mode={payment}
          onClose={() => setPayment(null)}
          onSuccess={refresh}
        />
      )}
      {detail && account && (
        <TransferDetails
          api={api}
          entry={detail}
          account={account}
          onClose={() => setDetail(null)}
          onRefund={(transfer) => {
            setDetail(null);
            setPayment({ kind: 'refund', transfer });
          }}
        />
      )}
    </div>
  );
}

function CreateAccount({
  api,
  onClose,
  onCreated,
}: {
  api: Api;
  onClose: () => void;
  onCreated: (account: Account) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const inFlight = useRef(false);
  return (
    <Modal
      title="A new space for your money."
      subtitle="Open a EUR account in your name."
      onClose={onClose}
      locked={busy}
    >
      <div className="new-account-preview">
        <span className="currency-icon large">€</span>
        <div>
          <h3>Euro account</h3>
          <p>EUR · Starting balance €0.00</p>
        </div>
        <Icon name="check" />
      </div>
      <p className="muted">
        Send and receive payments between LedgerX accounts. No cards, fees or external bank
        connection.
      </p>
      <ErrorNotice error={error} />
      {!!error && (
        <p className="field-hint">
          If the connection failed, close this dialog and refresh your accounts before trying again:
          creation may have completed.
        </p>
      )}
      <button
        className="button primary full-width"
        disabled={busy}
        onClick={async () => {
          if (inFlight.current) return;
          inFlight.current = true;
          setBusy(true);
          setError(null);
          try {
            onCreated(
              await api.request<Account>('/accounts', {
                method: 'POST',
                body: { currency: 'EUR' },
              }),
            );
          } catch (e) {
            setError(e);
          } finally {
            inFlight.current = false;
            setBusy(false);
          }
        }}
      >
        {busy ? 'Opening account…' : 'Open EUR account'}
        <Icon name="arrow" />
      </button>
    </Modal>
  );
}

function Operations({ api }: { api: Api }) {
  const [audit, setAudit] = useState<Audit | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  return (
    <section className="panel operations-panel">
      <div className="operations-intro">
        <span className="empty-icon">
          <Icon name="shield" size={30} />
        </span>
        <p className="eyebrow">ADMINISTRATOR WORKSPACE</p>
        <h2>Trust. Then verify.</h2>
        <p>
          Recalculate balances from the journal and compare them with the accounts.
          <br />
          An independent check that never changes your financial records.
        </p>
        <button
          type="button"
          className="button primary"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError(null);
            setAudit(null);
            try {
              setAudit(await api.request<Audit>('/operations/reconciliation'));
            } catch (e) {
              setError(e);
            } finally {
              setBusy(false);
            }
          }}
        >
          <Icon name="refresh" size={17} />
          {busy ? 'Checking the ledger…' : 'Run reconciliation'}
        </button>
      </div>
      <ErrorNotice error={error} />
      {audit && (
        <div
          className={`audit-result ${audit.consistent ? 'consistent' : 'inconsistent'}`}
          role="status"
        >
          <div className="audit-result-heading">
            <Icon name={audit.consistent ? 'check' : 'info'} />
            <h3>{audit.consistent ? 'Everything balances.' : 'Discrepancies detected.'}</h3>
          </div>
          <p>
            Checked {new Date(audit.checked_at).toLocaleString('en-GB')}. No balances were modified.
          </p>
          <div className="audit-counts">
            <div>
              <strong>{String(audit.account_count)}</strong>
              <span>Accounts</span>
            </div>
            <div>
              <strong>{String(audit.transfer_count)}</strong>
              <span>Transfers</span>
            </div>
            <div>
              <strong>{String(audit.entry_count)}</strong>
              <span>Journal entries</span>
            </div>
          </div>
          {!audit.consistent && (
            <>
              <p>
                {String(audit.mismatched_accounts)} account mismatches ·{' '}
                {String(audit.projection_mismatched_accounts ?? 0n)} journal projection mismatches ·{' '}
                {String(audit.invalid_transfers)} invalid transfers.
              </p>
              <ul>
                {audit.discrepancies.map((d) => (
                  <li key={d.account_id}>
                    <code>{d.account_id}</code> · difference {money(d.difference, true)}
                  </li>
                ))}
                {(audit.projection_discrepancies ?? []).map((d) => (
                  <li key={`projection-${d.account_id}`}>
                    <code>{d.account_id}</code> · journal projection difference{' '}
                    {money(d.difference, true)}
                  </li>
                ))}
              </ul>
              <p>
                Discrepancies are sampled (up to 100). Preserve the evidence and investigate before
                any correction.
              </p>
            </>
          )}
        </div>
      )}
    </section>
  );
}
