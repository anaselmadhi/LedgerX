import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { ApiError } from '../lib/api';
import { Icon, type IconName } from './Icon';

export function ErrorNotice({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <div className="error-notice" role="alert">
      <Icon name="info" />
      <div>
        {error instanceof Error ? error.message : 'Something went wrong. Please try again.'}
        {error instanceof ApiError && error.requestId && (
          <small>Support reference: {error.requestId}</small>
        )}
      </div>
    </div>
  );
}
export function EmptyState({
  icon = 'wallet',
  title,
  children,
}: {
  icon?: IconName;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon name={icon} size={26} />
      </span>
      <h3>{title}</h3>
      <div>{children}</div>
    </div>
  );
}
export function Loading({ label = 'Loading your accounts…' }: { label?: string }) {
  return (
    <div className="loading" role="status">
      <span className="spinner" />
      {label}
    </div>
  );
}
export function CopyButton({
  value,
  label = 'Copy account ID',
}: {
  value: string;
  label?: string;
}) {
  const [state, setState] = useState('');
  return (
    <button
      type="button"
      className="icon-button"
      aria-label={state || label}
      title={state || label}
      onClick={() => {
        if (!navigator.clipboard) {
          setState('Select and copy the ID below');
          return;
        }
        navigator.clipboard.writeText(value).then(
          () => setState('Copied'),
          () => setState('Select and copy the ID below'),
        );
      }}
    >
      <Icon name={state === 'Copied' ? 'check' : 'copy'} />
      <span className="sr-only" role="status">
        {state}
      </span>
    </button>
  );
}

export function Modal({
  title,
  subtitle,
  children,
  onClose,
  locked = false,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  onClose: () => void;
  locked?: boolean;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const element = dialog.current!;
    const previous = document.activeElement as HTMLElement | null;
    element.showModal();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      element.close();
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      ref={dialog}
      className="modal"
      aria-labelledby={titleId}
      onCancel={(e) => {
        e.preventDefault();
        if (!locked) onClose();
      }}
    >
      <div className="modal-head">
        <div>
          <p className="eyebrow">LEDGERX / ACCOUNTS</p>
          <h2 id={titleId}>{title}</h2>
          {subtitle && <p className="muted">{subtitle}</p>}
        </div>
        <button
          type="button"
          className="icon-button"
          aria-label="Close dialog"
          disabled={locked}
          onClick={onClose}
        >
          <Icon name="close" />
        </button>
      </div>
      {children}
    </dialog>
  );
}
