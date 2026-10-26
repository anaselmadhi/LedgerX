import { expect, test } from '@playwright/test';
import { fixture, navigate, SECOND, signIn } from './fixture';

test('polished responsive shell, exact balances and memory-only sessions', async ({
  page,
}, info) => {
  const state = await fixture(page);
  await page.goto('https://ledgerx.test/');
  await expect(page.getByRole('heading', { name: 'Good to see you.' })).toBeVisible();
  await page.screenshot({
    path: `../artifacts/frontend-${info.project.name}-login.png`,
    fullPage: true,
  });
  await signIn(page);
  await expect(page.getByTestId('selected-balance')).toHaveText('€2,350.50');
  await page.screenshot({
    path: `../artifacts/frontend-${info.project.name}-dashboard.png`,
    fullPage: true,
  });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0]);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Good to see you.' })).toBeVisible();
  expect(state.errors).toEqual([]);
});

test('signup, empty state and account creation', async ({ page }) => {
  const state = await fixture(page, true);
  await page.goto('https://ledgerx.test/');
  await page.getByRole('button', { name: 'Create profile', exact: true }).click();
  await page.getByLabel('Username', { exact: true }).fill('new-user');
  await page.getByLabel('Password', { exact: true }).fill('a-long-test-password');
  await page.getByRole('button', { name: 'Create my profile' }).click();
  await page.getByRole('button', { name: 'Open my first account' }).click();
  await page.getByRole('button', { name: 'Open EUR account', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Account details' })).toBeVisible();
  expect(state.accounts).toHaveLength(1);
  expect(state.accounts[0].balance).toBe(0n);
  expect(state.errors).toEqual([]);
});

test('ambiguous transfer retries the original intent and renders a single debit', async ({
  page,
}) => {
  const state = await fixture(page);
  await signIn(page);
  await page.getByRole('button', { name: 'Send money', exact: true }).click();
  await page.getByLabel('Destination account ID').fill(SECOND);
  await page.getByLabel('Amount', { exact: true }).fill('25.01');
  await page.getByRole('button', { name: 'Review transfer' }).click();
  state.abortAfterCommit();
  await page.getByRole('button', { name: 'Confirm transfer' }).click();
  await expect(page.getByText('The result is uncertain.', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Edit details' })).toBeDisabled();
  await page.getByRole('button', { name: 'Retry same request' }).click();
  await expect(page.getByRole('heading', { name: 'All done.' })).toBeVisible();
  await page.getByRole('button', { name: 'Back to my accounts' }).click();
  await expect(page.getByTestId('selected-balance')).toHaveText('€2,325.49');
  expect(state.payments).toHaveLength(2);
  expect(state.payments[0]).toEqual(state.payments[1]);
  expect(state.errors).toEqual([]);
});

test('payment details lead to a full compensating refund', async ({ page }) => {
  const state = await fixture(page);
  await signIn(page);
  await page.getByRole('button', { name: /^Received €850.00/ }).click();
  await page.getByRole('button', { name: 'Return this payment' }).click();
  await page.getByLabel('Reason for return').fill('Returned for browser test');
  await page.getByRole('button', { name: 'Review refund' }).click();
  await page.getByRole('button', { name: 'Confirm transfer' }).click();
  await expect(page.getByText('Payment returned successfully.')).toBeVisible();
  expect(state.payments).toHaveLength(1);
  expect(state.errors).toEqual([]);
});

test('administrative controls are capability gated', async ({ page }) => {
  const state = await fixture(page, false, true);
  await signIn(page);
  await navigate(page, 'Operations');
  await page.getByRole('button', { name: 'Run reconciliation' }).click();
  await expect(page.getByRole('heading', { name: 'Everything balances.' })).toBeVisible();
  await navigate(page, 'My accounts');
  await page.getByRole('button', { name: 'Add demo funds' }).click();
  await expect(page.getByText('Administrator demo tool.', { exact: false })).toBeVisible();
  expect(state.errors).toEqual([]);
});
