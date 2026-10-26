import { useEffect, useState } from 'react';
import { Api } from '../lib/api';
import { money, shortId } from '../lib/money';
import {
  SYSTEM_ACCOUNT,
  type Account,
  type Entry,
  type History,
  type Transfer,
} from '../lib/types';
import { Icon } from './Icon';
import { CopyButton, EmptyState, ErrorNotice, Loading, Modal } from './ui';

export function useHistory(api: Api, accountId: string | undefined, revision: number) {
  const [state, setState] = useState<{
    key: string;
    data: History | null;
    busy: boolean;
    error: unknown;
  }>({ key: '', data: null, busy: false, error: null });
  const key = `${accountId}:${revision}`;
  const [pages, setPages] = useState(1);
  useEffect(() => {
    setPages(1);
  }, [key]);
  useEffect(() => {
    let active = true;
    if (!accountId) return;
    setState({ key, data: null, busy: true, error: null });
    (async () => {
      const items: Entry[] = [];
      let cursor: string | null = null;
      for (let i = 0; i < pages; i++) {
        const page: History = await api.request(
          `/accounts/${accountId}/transactions?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`,
        );
        if (!active) return;
        items.push(...page.items);
        cursor = page.next_cursor;
        if (!cursor) break;
      }
      if (active) setState({ key, data: { items, next_cursor: cursor }, busy: false, error: null });
    })().catch((error) => {
      if (active) setState({ key, data: null, busy: false, error });
    });
    return () => {
      active = false;
    };
  }, [api, accountId, key, pages]);
  return {
    ...(state.key === key ? state : { data: null, busy: !!accountId, error: null }),
    more: () => setPages((n) => n + 1),
  };
}

export function ActivityTable({
  entries,
  onSelect,
  filter,
  onFilter,
}: {
  entries: Entry[];
  onSelect: (entry: Entry) => void;
  filter: string;
  onFilter: (filter: string) => void;
}) {
  const visible = entries.filter(
    (entry) => filter === 'all' || (filter === 'in' ? entry.amount > 0n : entry.amount < 0n),
  );
  return (
    <>
      <div className="filter-tabs" aria-label="Filter activity">
        {[
          ['all', 'All activity'],
          ['in', 'Money in'],
          ['out', 'Money out'],
        ].map(([value, label]) => (
          <button
            type="button"
            key={value}
            aria-pressed={filter === value}
            className={filter === value ? 'active' : ''}
            onClick={() => onFilter(value)}
          >
            {label}
          </button>
        ))}
      </div>
      {!visible.length ? (
        <EmptyState icon="swap" title="A fresh start">
          {entries.length
            ? 'No matching payments in the loaded activity. Try another filter or load more.'
            : 'Your transfers will appear here. Open an account, then receive your first payment.'}
        </EmptyState>
      ) : (
        <div className="transaction-table">
          <div className="transaction-heading">
            <span>Transaction</span>
            <span>Date</span>
            <span>Status</span>
            <span>Amount</span>
          </div>
          {visible.map((entry) => (
            <button
              type="button"
              className="transaction-row"
              key={entry.id}
              onClick={() => onSelect(entry)}
              aria-label={`${entry.amount > 0n ? 'Received' : 'Sent'} ${money(entry.amount < 0n ? -entry.amount : entry.amount)}, transaction ${entry.transaction_id}`}
            >
              <span className="transaction-title">
                <span className={`transaction-icon ${entry.amount > 0n ? 'incoming' : 'outgoing'}`}>
                  <Icon name={entry.amount > 0n ? 'receive' : 'send'} />
                </span>
                <span>
                  <strong>{entry.amount > 0n ? 'Payment received' : 'Payment sent'}</strong>
                  <small>{shortId(entry.transaction_id)}</small>
                </span>
              </span>
              <time dateTime={entry.created_at}>
                {new Date(entry.created_at).toLocaleDateString('en-GB', {
                  month: 'short',
                  day: 'numeric',
                })}
                <small>
                  {new Date(entry.created_at).toLocaleTimeString('en-GB', {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </small>
              </time>
              <span>
                <span className="completed-badge">Completed</span>
              </span>
              <strong className={entry.amount > 0n ? 'amount-positive' : ''}>
                {money(entry.amount, true)}
                <Icon name="chevron" size={14} />
              </strong>
            </button>
          ))}
        </div>
      )}
    </>
  );
}

export function TransferDetails({
  api,
  entry,
  account,
  onClose,
  onRefund,
}: {
  api: Api;
  entry: Entry;
  account: Account;
  onClose: () => void;
  onRefund: (transfer: Transfer) => void;
}) {
  const [transfer, setTransfer] = useState<Transfer | null>(null);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    let active = true;
    api.request<Transfer>(`/transfers/${entry.transaction_id}`).then(
      (value) => {
        if (active) setTransfer(value);
      },
      (e) => {
        if (active) setError(e);
      },
    );
    return () => {
      active = false;
    };
  }, [api, entry.transaction_id]);
  const refundable =
    transfer &&
    transfer.destination_account_id === account.id &&
    !transfer.reversal_of &&
    transfer.source_account_id !== SYSTEM_ACCOUNT;
  return (
    <Modal
      title="Payment details"
      subtitle="A permanent record of this movement."
      onClose={onClose}
    >
      <ErrorNotice error={error} />
      {!transfer && !error && <Loading label="Loading payment…" />}
      {transfer && (
        <>
          <div className="transfer-detail-amount">
            <span className={`transaction-icon ${entry.amount > 0n ? 'incoming' : 'outgoing'}`}>
              <Icon name={entry.amount > 0n ? 'receive' : 'send'} />
            </span>
            <h3>{money(entry.amount, true)}</h3>
            <span className="completed-badge">Completed</span>
          </div>
          <dl className="detail-list">
            <div>
              <dt>Type</dt>
              <dd>
                {transfer.reversal_of
                  ? 'Refund'
                  : transfer.source_account_id === SYSTEM_ACCOUNT
                    ? 'Demo funding'
                    : 'Account transfer'}
              </dd>
            </div>
            <div>
              <dt>Date</dt>
              <dd>{new Date(transfer.created_at).toLocaleString('en-GB')}</dd>
            </div>
            <div>
              <dt>From</dt>
              <dd className="mono break-word">{transfer.source_account_id}</dd>
            </div>
            <div>
              <dt>To</dt>
              <dd className="mono break-word">{transfer.destination_account_id}</dd>
            </div>
            {transfer.reversal_reason && (
              <div>
                <dt>Refund reason</dt>
                <dd>{transfer.reversal_reason}</dd>
              </div>
            )}
            {transfer.reversal_of && (
              <div>
                <dt>Original transfer</dt>
                <dd className="mono break-word">{transfer.reversal_of}</dd>
              </div>
            )}
          </dl>
          <div className="receipt">
            <span>Transaction ID</span>
            <code>{transfer.id}</code>
            <CopyButton value={transfer.id} label="Copy transaction ID" />
          </div>
          {refundable && (
            <>
              <button
                type="button"
                className="button secondary full-width"
                onClick={() => onRefund(transfer)}
              >
                <Icon name="history" />
                Return this payment
              </button>
              <p className="field-hint">
                Full refunds only, once per payment. The server verifies eligibility and available
                funds.
              </p>
            </>
          )}
        </>
      )}
    </Modal>
  );
}

export function ActivityChart({ entries }: { entries: Entry[] }) {
  const today = new Date();
  const days = Array.from({ length: 7 }, (_, i) => {
    const date = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 6 + i);
    const end = new Date(date);
    end.setDate(end.getDate() + 1);
    const selected = entries.filter(
      (e) => new Date(e.created_at) >= date && new Date(e.created_at) < end,
    );
    return {
      label: date.toLocaleDateString('en-GB', { weekday: 'short' }),
      incoming: selected.reduce((s, e) => s + (e.amount > 0n ? e.amount : 0n), 0n),
      outgoing: selected.reduce((s, e) => s + (e.amount < 0n ? -e.amount : 0n), 0n),
    };
  });
  const max = days.reduce(
    (m, d) =>
      d.incoming > m
        ? d.outgoing > d.incoming
          ? d.outgoing
          : d.incoming
        : d.outgoing > m
          ? d.outgoing
          : m,
    1n,
  );
  const height = (value: bigint) => Number((value * 11200n) / max) / 100;
  return (
    <div className="activity-chart">
      <div className="chart-legend">
        <span>
          <i className="legend-in" />
          Money in
        </span>
        <span>
          <i className="legend-out" />
          Money out
        </span>
      </div>
      <svg
        viewBox="0 0 440 164"
        role="img"
        aria-label="Money in and out over the last seven days, using loaded activity only"
      >
        <path d="M0 20h440 M0 58h440 M0 96h440 M0 134h440" stroke="#e8ede9" strokeDasharray="3 5" />
        {days.map((d, i) => (
          <g key={i}>
            <title>{`${d.label}: received ${money(d.incoming)}, sent ${money(d.outgoing)}`}</title>
            <rect
              x={i * 62 + 17}
              y={134 - height(d.incoming)}
              width="13"
              height={height(d.incoming)}
              rx="4"
              fill="#335b49"
            />
            <rect
              x={i * 62 + 33}
              y={134 - height(d.outgoing)}
              width="13"
              height={height(d.outgoing)}
              rx="4"
              fill="#b8d98d"
            />
            <text x={i * 62 + 31} y="158" textAnchor="middle" fill="#707c74" fontSize="11">
              {d.label}
            </text>
          </g>
        ))}
      </svg>
      <p className="chart-caption">
        Last 7 days · Based on {entries.length} loaded entries · Local time
      </p>
    </div>
  );
}
