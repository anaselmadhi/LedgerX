import { expect, test, type Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';

/** Runs only through the isolated verification server (_bench locally / _test in CI). */
test('real browser → FastAPI → PostgreSQL: signup, accounts, funding, transfer, refund', async ({
  page,
  request,
  baseURL,
}) => {
  if (process.env.LEDGERX_ISOLATED_UI_TEST !== '1') {
    throw new Error('Run via scripts/verify_web.sh; an isolated test environment is required.');
  }
  expect(baseURL).toBeTruthy();
  const username = `ui-${randomUUID().slice(0, 12)}`;
  const password = `Ui-${randomUUID()}`;
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');
  await page.getByRole('button', { name: 'Create profile', exact: true }).click();
  await page.getByLabel('Username', { exact: true }).fill(username);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Create my profile' }).click();
  await page.getByRole('button', { name: 'Open my first account' }).click();
  const firstResponse = page.waitForResponse(
    (res) => new URL(res.url()).pathname === '/accounts' && res.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Open EUR account', exact: true }).click();
  const first = (await (await firstResponse).json()).id as string;
  await page.getByRole('button', { name: 'Open an account', exact: true }).click();
  const secondResponse = page.waitForResponse(
    (res) => new URL(res.url()).pathname === '/accounts' && res.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Open EUR account', exact: true }).click();
  const second = (await (await secondResponse).json()).id as string;
  const auth = await request.post('/auth/login', {
    data: { username: process.env.BENCHMARK_USERNAME, password: process.env.BENCHMARK_PASSWORD },
  });
  expect(auth.ok()).toBeTruthy();
  const adminToken = (await auth.json()).access_token as string;
  const adminHeaders = { Authorization: `Bearer ${adminToken}`, 'Idempotency-Key': randomUUID() };
  try {
    const funding = await request.post('/dev/funding', {
      headers: adminHeaders,
      data: { destination_account_id: first, amount: 10000 },
    });
    expect(funding.status()).toBe(201);
    await page.getByRole('button', { name: 'Refresh accounts and activity' }).click();
    await page.getByLabel('Viewing account').selectOption(first);
    // Wait for the balance refresh, not merely the previously rendered account cards.
    await expect(page.getByRole('definition').filter({ hasText: '€100.00' })).toBeVisible();
    await page.getByRole('button', { name: 'Send money', exact: true }).click();
    await page.getByLabel('Destination account ID').fill(second);
    await page.getByLabel('Amount', { exact: true }).fill('12.34');
    await page.getByRole('button', { name: 'Review transfer' }).click();
    await page.getByRole('button', { name: 'Confirm transfer' }).click();
    await expect(page.getByText('Transfer completed.')).toBeVisible();
    await page.getByRole('button', { name: 'Back to my accounts' }).click();
    await page.getByLabel('Viewing account').selectOption(second);
    await page
      .getByRole('navigation', { name: 'Main navigation' })
      .getByRole('button', { name: 'Activity', exact: true })
      .click();
    await page.getByRole('button', { name: /^Received €12.34/ }).click();
    await page.getByRole('button', { name: 'Return this payment' }).click();
    await page.getByLabel('Reason for return').fill('Live browser verification');
    await page.getByRole('button', { name: 'Review refund' }).click();
    await page.getByRole('button', { name: 'Confirm transfer' }).click();
    await expect(page.getByText('Payment returned successfully.')).toBeVisible();
    await page.getByRole('button', { name: 'Back to my accounts' }).click();
    await page
      .getByRole('navigation', { name: 'Main navigation' })
      .getByRole('button', { name: 'Overview', exact: true })
      .click();
    await expect(page.getByTestId('selected-balance')).toHaveText('€0.00');
    await page.getByLabel('Viewing account').selectOption(first);
    await expect(page.getByTestId('selected-balance')).toHaveText('€100.00');
    const audit = await request.get('/operations/reconciliation', { headers: adminHeaders });
    expect(audit.status()).toBe(200);
    expect((await audit.json()).consistent).toBe(true);
    await page.getByRole('button', { name: 'Sign out', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Good to see you.' })).toBeVisible();
    expect(errors).toEqual([]);
  } finally {
    await request.post('/auth/logout', { headers: adminHeaders });
  }
});

test('two real customer sessions transfer and refund without sharing ownership', async ({
  browser,
  page: alice,
  request,
  baseURL,
}) => {
  if (process.env.LEDGERX_ISOLATED_UI_TEST !== '1') {
    throw new Error('Use the isolated verification runner, never the personal or public database.');
  }
  expect(baseURL).toBeTruthy();
  const bobContext = await browser.newContext({ baseURL });
  const bob = await bobContext.newPage();
  const errors: string[] = [];
  alice.on('pageerror', (error) => errors.push(error.message));
  bob.on('pageerror', (error) => errors.push(error.message));
  let adminToken = '';

  async function signupAndOpenAccount(page: Page, prefix: string): Promise<string> {
    await page.goto('/');
    await page.getByRole('button', { name: 'Create profile', exact: true }).click();
    await page
      .getByLabel('Username', { exact: true })
      .fill(`${prefix}-${randomUUID().slice(0, 12)}`);
    await page.getByLabel('Password', { exact: true }).fill(`Ui-${randomUUID()}`);
    await page.getByRole('button', { name: 'Create my profile' }).click();
    await page.getByRole('button', { name: 'Open my first account' }).click();
    const created = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === '/accounts' && response.request().method() === 'POST',
    );
    await page.getByRole('button', { name: 'Open EUR account', exact: true }).click();
    const response = await created;
    expect(response.status()).toBe(201);
    const account = (await response.json()).id as string;
    await expect(page.getByRole('heading', { name: 'Account details' })).toBeVisible();
    await page
      .getByRole('navigation', { name: 'Main navigation' })
      .getByRole('button', { name: 'Overview', exact: true })
      .click();
    await expect(page.getByTestId('selected-balance')).toHaveText('€0.00');
    await expect(
      page
        .getByRole('navigation', { name: 'Main navigation' })
        .getByRole('button', { name: 'Operations', exact: true }),
    ).toHaveCount(0);
    return account;
  }

  try {
    const aliceAccount = await signupAndOpenAccount(alice, 'alice');
    const bobAccount = await signupAndOpenAccount(bob, 'bob');
    expect(aliceAccount).not.toBe(bobAccount);
    const auth = await request.post('/auth/login', {
      data: { username: process.env.BENCHMARK_USERNAME, password: process.env.BENCHMARK_PASSWORD },
    });
    expect(auth.status()).toBe(200);
    adminToken = (await auth.json()).access_token as string;
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };
    const funding = await request.post('/dev/funding', {
      headers: { ...adminHeaders, 'Idempotency-Key': randomUUID() },
      data: { destination_account_id: aliceAccount, amount: 5000 },
    });
    expect(funding.status()).toBe(201);
    await alice.getByRole('button', { name: 'Refresh accounts and activity' }).click();
    await expect(alice.getByTestId('selected-balance')).toHaveText('€50.00');
    await alice.getByRole('button', { name: 'Send money', exact: true }).click();
    await alice.getByLabel('Destination account ID').fill(bobAccount);
    await alice.getByLabel('Amount', { exact: true }).fill('12.34');
    await alice.getByRole('button', { name: 'Review transfer' }).click();
    await alice.getByRole('button', { name: 'Confirm transfer' }).click();
    await expect(alice.getByText('Transfer completed.')).toBeVisible();
    await alice.getByRole('button', { name: 'Back to my accounts' }).click();
    await expect(alice.getByTestId('selected-balance')).toHaveText('€37.66');

    await bob.getByRole('button', { name: 'Refresh accounts and activity' }).click();
    await expect(bob.getByTestId('selected-balance')).toHaveText('€12.34');
    await bob.getByRole('button', { name: /^Received €12.34/ }).click();
    await bob.getByRole('button', { name: 'Return this payment' }).click();
    await bob.getByLabel('Reason for return').fill('Cross-customer browser verification');
    await bob.getByRole('button', { name: 'Review refund' }).click();
    await bob.getByRole('button', { name: 'Confirm transfer' }).click();
    await expect(bob.getByText('Payment returned successfully.')).toBeVisible();
    await bob.getByRole('button', { name: 'Back to my accounts' }).click();
    await expect(bob.getByTestId('selected-balance')).toHaveText('€0.00');
    await alice.getByRole('button', { name: 'Refresh accounts and activity' }).click();
    await expect(alice.getByTestId('selected-balance')).toHaveText('€50.00');
    const audit = await request.get('/operations/reconciliation', { headers: adminHeaders });
    expect(audit.status()).toBe(200);
    expect((await audit.json()).consistent).toBe(true);
    expect(errors).toEqual([]);
    await alice.getByRole('button', { name: 'Sign out', exact: true }).click();
    await bob.getByRole('button', { name: 'Sign out', exact: true }).click();
  } finally {
    await bobContext.close();
    if (adminToken) {
      await request.post('/auth/logout', { headers: { Authorization: `Bearer ${adminToken}` } });
    }
  }
});
