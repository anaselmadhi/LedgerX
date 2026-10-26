import { describe, expect, it } from 'vitest';
import { MAX_CENTS, money, parseAmount, validAccountId } from '../src/lib/money';
import { encodeWire, parseWire } from '../src/lib/api';

describe('exact monetary values across the browser / API boundary', () => {
  it.each([
    ['0.01', 1n],
    ['12', 1200n],
    ['12,50', 1250n],
    [' 12.5 ', 1250n],
    ['90071992547409.93', 9007199254740993n],
    ['90000000000000000.00', MAX_CENTS],
  ])('parses %s without float arithmetic', (text, expected) => {
    expect(parseAmount(text)).toBe(expected);
  });
  it.each([
    '0',
    '-1',
    '1e3',
    'Infinity',
    'NaN',
    '1.001',
    '1,000.00',
    '1 000',
    '.25',
    '1.',
    '',
    '90000000000000000.01',
  ])('rejects ambiguous or out of range input %s', (text) => {
    expect(() => parseAmount(text)).toThrow();
  });
  it('preserves cents larger than Number.MAX_SAFE_INTEGER in both directions', () => {
    const data = parseWire<{ balance: bigint; account_count: bigint }>(
      ' {"balance":9007199254740993,"account_count":2} ',
    );
    expect(data.balance).toBe(9007199254740993n);
    expect(data.account_count).toBe(2n);
    expect(encodeWire({ amount: data.balance })).toBe('{"amount":9007199254740993}');
    expect(money(data.balance)).toBe('€90,071,992,547,409.93');
    expect(money(-1n, true)).toBe('−€0.01');
    expect(money(1n, true)).toBe('+€0.01');
  });
  it('does not treat numeric-looking identifiers as amounts', () => {
    expect(parseWire<{ id: string }>('{"id":"9007199254740993"}').id).toBe('9007199254740993');
    expect(validAccountId('00000000-0000-4000-8000-000000000001')).toBe(true);
    expect(validAccountId('not-an-account')).toBe(false);
  });
});
