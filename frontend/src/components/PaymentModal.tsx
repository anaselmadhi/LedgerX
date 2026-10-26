import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Api, ApiError, PaymentIntent } from '../lib/api';
import { money, parseAmount, shortId, validAccountId } from '../lib/money';
import { SYSTEM_ACCOUNT, type Account, type Transfer } from '../lib/types';
import { Icon } from './Icon';
import { CopyButton, ErrorNotice, Modal } from './ui';

export type PaymentMode = { kind: 'transfer' | 'funding' } | { kind: 'refund'; transfer: Transfer };
export function PaymentModal({
  api,
  account,
  accounts,
  mode,
  onClose,
  onSuccess,
}: {
  api: Api;
  account: Account;
  accounts: Account[];
  mode: PaymentMode;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [destination, setDestination] = useState('');
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [intent, setIntent] = useState<PaymentIntent | null>(null);
  const [reviewAmount, setReviewAmount] = useState(0n);
  const [result, setResult] = useState<Transfer | null>(null);
  const [attempted, setAttempted] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const inFlight = useRef(false);
  const title =
    mode.kind === 'transfer'
      ? 'Send a transfer'
      : mode.kind === 'funding'
        ? 'Add demo funds'
        : 'Return this payment';
  useEffect(() => {
    if (!(busy || uncertain)) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [busy, uncertain]);
  function review(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const cents = mode.kind === 'refund' ? mode.transfer.amount : parseAmount(amount);
      const target = destination.trim().toLowerCase();
      if (mode.kind === 'transfer') {
        if (!validAccountId(target)) throw new Error('Enter a valid destination account ID.');
        if (target === account.id) throw new Error('Choose a different destination account.');
        if (target === SYSTEM_ACCOUNT)
          throw new Error('The system account cannot receive transfers.');
      }
      if (mode.kind !== 'funding' && cents > account.balance)
        throw new Error('This account has insufficient funds. Refresh your balance if needed.');
      const path =
        mode.kind === 'refund'
          ? `/transfers/${mode.transfer.id}/reversal`
          : mode.kind === 'funding'
            ? '/dev/funding'
            : '/transfers';
      const body =
        mode.kind === 'refund'
          ? { reason: reason.trim() }
          : {
              ...(mode.kind === 'transfer' ? { source_account_id: account.id } : {}),
              destination_account_id: mode.kind === 'funding' ? account.id : target,
              amount: cents,
              currency: 'EUR',
            };
      if (mode.kind === 'refund' && !reason.trim())
        throw new Error('Add a short reason for the refund.');
      setReviewAmount(cents);
      setDestination(target);
      setIntent(new PaymentIntent(path, body));
    } catch (e) {
      setError(e);
    }
  }
  async function confirm() {
    if (!intent || inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    setAttempted(true);
    try {
      const transfer = await intent.send<Transfer>(api);
      setResult(transfer);
      setUncertain(false);
      onSuccess();
    } catch (e) {
      setError(e);
      setUncertain(e instanceof ApiError && e.ambiguous);
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  function close() {
    if (
      uncertain &&
      !window.confirm(
        'This payment may have completed. Closing discards its retry key from memory. Copy the key and check your activity before starting another payment. Close anyway?',
      )
    )
      return;
    onClose();
  }
  const target =
    mode.kind === 'refund'
      ? mode.transfer.source_account_id
      : mode.kind === 'funding'
        ? account.id
        : destination;
  return (
    <Modal
      title={result ? 'All done.' : title}
      subtitle={result ? 'Your account activity has been updated.' : 'EUR · Fictitious funds only'}
      onClose={close}
      locked={busy}
    >
      {result ? (
        <div className="payment-success">
          <span className="success-mark">
            <Icon name="check" size={32} />
          </span>
          <h3>{money(result.amount)}</h3>
          <p>
            {mode.kind === 'refund'
              ? 'Payment returned successfully.'
              : mode.kind === 'funding'
                ? 'Demo funds added.'
                : 'Transfer completed.'}
          </p>
          <div className="receipt">
            <span>Transaction ID</span>
            <code>{result.id}</code>
            <CopyButton value={result.id} label="Copy transaction ID" />
          </div>
          <button type="button" className="button primary full-width" onClick={onClose}>
            Back to my accounts
            <Icon name="arrow" />
          </button>
        </div>
      ) : intent ? (
        <div className="review-payment">
          <p className="eyebrow">
            {mode.kind === 'funding' ? 'ADDING TO YOUR DEMO ACCOUNT' : 'YOU ARE SENDING'}
          </p>
          <div className="review-amount">{money(reviewAmount)}</div>
          <dl className="detail-list">
            <div>
              <dt>From</dt>
              <dd>{mode.kind === 'funding' ? 'Demo funding' : `EUR · ${shortId(account.id)}`}</dd>
            </div>
            <div>
              <dt>Destination ID</dt>
              <dd className="mono break-word">{target}</dd>
            </div>
            {mode.kind === 'refund' && (
              <div>
                <dt>Reason</dt>
                <dd>{reason}</dd>
              </div>
            )}
            <div>
              <dt>Transfer fee</dt>
              <dd>€0.00</dd>
            </div>
          </dl>
          <ErrorNotice error={error} />
          {uncertain && (
            <p className="info-notice">
              The result is uncertain. Retry below using the same request key; this cannot create a
              second transfer. Keep this tab open until you have a result.
            </p>
          )}
          {attempted && (
            <div className="receipt">
              <span>Request key</span>
              <code>{intent.key}</code>
              <CopyButton value={intent.key} label="Copy request key" />
            </div>
          )}
          <div className="modal-actions">
            <button
              type="button"
              className="button secondary"
              disabled={busy || uncertain}
              onClick={() => {
                setIntent(null);
                setAttempted(false);
                setError(null);
              }}
            >
              Edit details
            </button>
            <button type="button" className="button primary" disabled={busy} onClick={confirm}>
              {busy ? (
                <>
                  <span className="spinner" />
                  Processing…
                </>
              ) : (
                <>
                  {attempted ? 'Retry same request' : 'Confirm transfer'}
                  <Icon name="send" size={17} />
                </>
              )}
            </button>
          </div>
          <p className="field-hint">
            Check the destination carefully. Completed payments cannot be edited.
          </p>
        </div>
      ) : (
        <form onSubmit={review}>
          <div className="from-account">
            <span className="currency-icon">€</span>
            <div>
              <strong>EUR account · {account.id.slice(-6)}</strong>
              <span>{money(account.balance)} available</span>
            </div>
          </div>
          {mode.kind === 'transfer' && (
            <>
              <label htmlFor="destination">Destination account ID</label>
              <input
                id="destination"
                required
                autoComplete="off"
                spellCheck={false}
                value={destination}
                onChange={(e) => setDestination(e.target.value)}
                placeholder="Paste the recipient’s account ID"
              />
              {accounts.some((a) => a.id !== account.id) && (
                <div className="own-accounts">
                  <span>Or one of your accounts</span>
                  {accounts
                    .filter((a) => a.id !== account.id)
                    .slice(0, 4)
                    .map((a) => (
                      <button type="button" key={a.id} onClick={() => setDestination(a.id)}>
                        EUR · {a.id.slice(-6)}
                        <Icon name="chevron" size={13} />
                      </button>
                    ))}
                </div>
              )}
            </>
          )}
          {mode.kind === 'refund' ? (
            <>
              <div className="refund-summary">
                <span>Full payment amount</span>
                <strong>{money(mode.transfer.amount)}</strong>
              </div>
              <label htmlFor="reason">Reason for return</label>
              <textarea
                id="reason"
                maxLength={200}
                required
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g. Returning an incorrect payment"
              />
            </>
          ) : (
            <>
              <label htmlFor="amount">Amount</label>
              <div className="amount-input">
                <span>€</span>
                <input
                  id="amount"
                  inputMode="decimal"
                  autoComplete="off"
                  required
                  maxLength={22}
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="0.00"
                />
                <span>EUR</span>
              </div>
            </>
          )}
          {mode.kind === 'funding' && (
            <p className="info-notice">
              Administrator demo tool. These funds are fictitious and cannot be withdrawn.
            </p>
          )}
          <ErrorNotice error={error} />
          <button type="submit" className="button primary full-width">
            Review {mode.kind === 'refund' ? 'refund' : 'transfer'}
            <Icon name="arrow" />
          </button>
        </form>
      )}
    </Modal>
  );
}
