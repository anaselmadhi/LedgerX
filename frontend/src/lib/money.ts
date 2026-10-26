export const MAX_CENTS = 9_000_000_000_000_000_000n;

/** Decimal input -> exact cents. No float, exponent, grouping or implicit rounding. */
export function parseAmount(value: string): bigint {
  const text = value.trim();
  if (!/^\d+(?:[.,]\d{1,2})?$/.test(text)) {
    throw new Error('Enter a positive amount with at most two decimal places, e.g. 25.50.');
  }
  const [whole, fraction = ''] = text.replace(',', '.').split('.');
  const cents = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
  if (cents <= 0n) throw new Error('The amount must be greater than zero.');
  if (cents > MAX_CENTS) throw new Error('This amount exceeds the account limit.');
  return cents;
}

export function money(cents: bigint, signed = false): string {
  if (typeof cents !== 'bigint') throw new Error('An exact integer amount is required.');
  const abs = cents < 0n ? -cents : cents;
  const whole = (abs / 100n).toLocaleString('en-IE');
  const sign = cents < 0n ? '−' : signed && cents > 0n ? '+' : '';
  return `${sign}€${whole}.${(abs % 100n).toString().padStart(2, '0')}`;
}

export function shortId(id: string): string {
  return `${id.slice(0, 4)}…${id.slice(-6)}`;
}

export function validAccountId(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
}
