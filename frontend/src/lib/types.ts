export type Account = { id: string; currency: 'EUR'; balance: bigint; created_at: string };
export type AccountPage = { items: Account[]; next_after: string | null };
export type Session = {
  id: string;
  username: string;
  is_admin: boolean;
  dev_funding_enabled: boolean;
};
export type Login = { access_token: string; expires_in: bigint };
export type Entry = {
  id: string;
  transaction_id: string;
  account_id: string;
  amount: bigint;
  currency: 'EUR';
  created_at: string;
};
export type History = { items: Entry[]; next_cursor: string | null };
export type Transfer = {
  id: string;
  source_account_id: string;
  destination_account_id: string;
  amount: bigint;
  currency: 'EUR';
  created_at: string;
  reversal_of: string | null;
  reversal_reason: string | null;
};
export type Audit = {
  checked_at: string;
  consistent: boolean;
  account_count: bigint;
  transfer_count: bigint;
  entry_count: bigint;
  mismatched_accounts: bigint;
  projection_mismatched_accounts: bigint;
  invalid_transfers: bigint;
  discrepancies: {
    account_id: string;
    stored_balance: bigint;
    journal_balance: bigint;
    difference: bigint;
  }[];
  projection_discrepancies: {
    account_id: string;
    stored_balance: bigint;
    journal_balance: bigint;
    difference: bigint;
  }[];
};
export const SYSTEM_ACCOUNT = '00000000-0000-0000-0000-000000000001';
