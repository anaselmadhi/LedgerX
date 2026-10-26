/** Browser contract fixture only. These synthetic balances never ship with the app. */
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { expect, type Page } from '@playwright/test';
import { encodeWire, parseWire } from '../src/lib/api';
import type { Account, Entry, Transfer } from '../src/lib/types';

export const FIRST = 'a0000000-0000-4000-8000-000000000001';
export const SECOND = 'b0000000-0000-4000-8000-000000000002';
const NOW = new Date().toISOString();
export async function fixture(page: Page, empty = false, admin = false) {
  const accounts: Account[] = empty
    ? []
    : [
        { id: FIRST, currency: 'EUR', balance: 235050n, created_at: NOW },
        { id: SECOND, currency: 'EUR', balance: 60000n, created_at: NOW },
      ];
  const entries: Entry[] = empty
    ? []
    : [
        {
          id: crypto.randomUUID(),
          transaction_id: 'c0000000-0000-4000-8000-000000000003',
          account_id: FIRST,
          amount: 85000n,
          currency: 'EUR',
          created_at: NOW,
        },
        {
          id: crypto.randomUUID(),
          transaction_id: 'c0000000-0000-4000-8000-000000000004',
          account_id: FIRST,
          amount: -3450n,
          currency: 'EUR',
          created_at: NOW,
        },
      ];
  const transfers = new Map<string, Transfer>();
  for (const entry of entries)
    transfers.set(entry.transaction_id, {
      id: entry.transaction_id,
      source_account_id: entry.amount > 0 ? SECOND : FIRST,
      destination_account_id: entry.amount > 0 ? FIRST : SECOND,
      amount: entry.amount > 0 ? entry.amount : -entry.amount,
      currency: 'EUR',
      created_at: NOW,
      reversal_of: null,
      reversal_reason: null,
    });
  const intents = new Map<string, Transfer>();
  const payments: { key: string; body: string }[] = [];
  let abortNext = false;
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.route('https://ledgerx.test/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname;
    const method = request.method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: 'application/json', body: encodeWire(body) });
    if (pathname === '/' || pathname.startsWith('/assets/')) {
      const file = pathname === '/' ? 'index.html' : `assets/${path.basename(pathname)}`;
      const contentType = file.endsWith('.js')
        ? 'text/javascript'
        : file.endsWith('.css')
          ? 'text/css'
          : 'text/html';
      return route.fulfill({
        contentType,
        body: await readFile(path.resolve('../app/web', file)),
        headers: {
          'Content-Security-Policy':
            "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
        },
      });
    }
    if (pathname === '/auth/register') return json({ id: 'user' }, 201);
    if (pathname === '/auth/login')
      return json({ access_token: 'test-memory-token', expires_in: 3600n });
    if (pathname === '/auth/me')
      return json({
        id: 'user',
        username: 'alex.morgan',
        is_admin: admin,
        dev_funding_enabled: admin,
      });
    if (pathname === '/auth/logout') return route.fulfill({ status: 204 });
    if (pathname === '/accounts' && method === 'GET')
      return json({ items: accounts, next_after: null });
    if (pathname === '/accounts' && method === 'POST') {
      const account: Account = {
        id: crypto.randomUUID(),
        currency: 'EUR',
        balance: 0n,
        created_at: NOW,
      };
      accounts.push(account);
      return json(account, 201);
    }
    if (pathname.endsWith('/transactions'))
      return json({
        items: entries.filter((e) => pathname.includes(e.account_id)),
        next_cursor: null,
      });
    if (pathname.startsWith('/accounts/'))
      return json(accounts.find((a) => a.id === pathname.split('/')[2]));
    if (
      (pathname === '/transfers' ||
        pathname.endsWith('/reversal') ||
        pathname === '/dev/funding') &&
      method === 'POST'
    ) {
      const key = request.headers()['idempotency-key'];
      payments.push({ key, body: request.postData()! });
      if (intents.has(key)) return json(intents.get(key), 201);
      const body = parseWire<Record<string, string | bigint>>(request.postData()!);
      const original = pathname.endsWith('/reversal')
        ? transfers.get(pathname.split('/')[2])
        : null;
      const result: Transfer = {
        id: crypto.randomUUID(),
        source_account_id: original?.destination_account_id || String(body.source_account_id),
        destination_account_id: original?.source_account_id || String(body.destination_account_id),
        amount: original?.amount || BigInt(body.amount),
        currency: 'EUR',
        created_at: NOW,
        reversal_of: original?.id || null,
        reversal_reason: original ? String(body.reason) : null,
      };
      const source = accounts.find((a) => a.id === result.source_account_id);
      const target = accounts.find((a) => a.id === result.destination_account_id);
      if (source) source.balance -= result.amount;
      if (target) target.balance += result.amount;
      for (const [accountId, value] of [
        [result.source_account_id, -result.amount],
        [result.destination_account_id, result.amount],
      ] as const)
        entries.unshift({
          id: crypto.randomUUID(),
          transaction_id: result.id,
          account_id: accountId,
          amount: value,
          currency: 'EUR',
          created_at: NOW,
        });
      transfers.set(result.id, result);
      intents.set(key, result);
      if (abortNext) {
        abortNext = false;
        return route.abort('failed');
      }
      return json(result, 201);
    }
    if (pathname.startsWith('/transfers/')) return json(transfers.get(pathname.split('/')[2]));
    if (pathname === '/operations/reconciliation')
      return json({
        checked_at: NOW,
        consistent: true,
        account_count: 3n,
        transfer_count: 2n,
        entry_count: 4n,
        mismatched_accounts: 0n,
        projection_mismatched_accounts: 0n,
        invalid_transfers: 0n,
        discrepancies: [],
        projection_discrepancies: [],
      });
    return json({ detail: 'Not found' }, 404);
  });
  return {
    accounts,
    errors,
    payments,
    abortAfterCommit: () => {
      abortNext = true;
    },
  };
}

export async function signIn(page: Page) {
  await page.goto('https://ledgerx.test/');
  await page.getByLabel('Username', { exact: true }).fill('alex.morgan');
  await page.getByLabel('Password', { exact: true }).fill('a-long-test-password');
  await page.getByRole('button', { name: 'Sign in to LedgerX' }).click();
  await expect(page.getByRole('heading', { name: 'Hello, alex.morgan.' })).toBeVisible();
}
export async function navigate(page: Page, label: string) {
  const mobile = page.getByRole('button', { name: 'Open navigation' });
  if (await mobile.isVisible()) await mobile.click();
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('button', { name: label, exact: true })
    .click();
}
