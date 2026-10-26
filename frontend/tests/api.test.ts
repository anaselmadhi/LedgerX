import { afterEach, describe, expect, it, vi } from 'vitest';
import { Api, ApiError, PaymentIntent } from '../src/lib/api';

afterEach(() => vi.unstubAllGlobals());
describe('payment retry contract', () => {
  it('discards a closed session before a late 401 can invalidate a new session', async () => {
    let respond!: (response: Response) => void;
    const fetcher = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          respond = resolve;
        }),
    );
    vi.stubGlobal('fetch', fetcher);
    const expire = vi.fn();
    const api = new Api('old-session-token', expire);
    const pending = api.request('/accounts');
    api.dispose();
    respond(new Response('{"detail":"Expired"}', { status: 401 }));
    await expect(pending).rejects.toBeInstanceOf(ApiError);
    expect(expire).not.toHaveBeenCalled();
    await expect(api.request('/accounts')).rejects.toMatchObject({ status: 401 });
    expect(fetcher).toHaveBeenCalledOnce();
  });
  it('retains the exact key and payload after an uncertain network result', async () => {
    const fetcher = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('network'))
      .mockResolvedValueOnce(new Response('{"id":"confirmed"}', { status: 201 }));
    vi.stubGlobal('fetch', fetcher);
    const body = { amount: 9007199254740993n, destination_account_id: 'recipient' };
    const intent = new PaymentIntent('/transfers', body);
    body.amount = 1n;
    const api = new Api('memory-token');
    await expect(intent.send(api)).rejects.toMatchObject({ ambiguous: true, status: 0 });
    await expect(intent.send(api)).resolves.toEqual({ id: 'confirmed' });
    const requests = fetcher.mock.calls.map((call) => call[1]);
    expect(requests[0].body).toBe(requests[1].body);
    expect(requests[0].body).toContain('9007199254740993');
    expect(requests[0].headers['Idempotency-Key']).toBe(requests[1].headers['Idempotency-Key']);
    expect(requests[0].headers.Authorization).toBe('Bearer memory-token');
    expect(requests[0].cache).toBe('no-store');
    expect(requests[0].credentials).toBe('omit');
  });
  it('reports a 503 as uncertain, with a safe support reference', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response('{"detail":"Database temporarily unavailable"}', {
          status: 503,
          headers: { 'X-Request-ID': 'req-123' },
        }),
      ),
    );
    await expect(new Api().request('/transfers')).rejects.toMatchObject({
      ambiguous: true,
      requestId: 'req-123',
    });
  });
  it('does not mark a definite business rejection as an uncertain commit', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('{"detail":"Insufficient funds"}', { status: 409 })),
    );
    await expect(new Api().request('/transfers')).rejects.toMatchObject({
      message: 'Insufficient funds',
      ambiguous: false,
    });
  });
  it('expires an authenticated session on 401 and never retries automatically', async () => {
    const expired = vi.fn();
    const fetcher = vi
      .fn()
      .mockResolvedValue(new Response('{"detail":"Unauthorized"}', { status: 401 }));
    vi.stubGlobal('fetch', fetcher);
    await expect(new Api('expired-token', expired).request('/accounts')).rejects.toBeInstanceOf(
      ApiError,
    );
    expect(expired).toHaveBeenCalledOnce();
    expect(fetcher).toHaveBeenCalledOnce();
  });
  it('treats malformed successful responses as uncertain and supports empty logout', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(new Response('truncated', { status: 201 }))
        .mockResolvedValueOnce(new Response(null, { status: 204 })),
    );
    await expect(new Api().request('/transfers')).rejects.toMatchObject({ ambiguous: true });
    await expect(new Api().request('/auth/logout', { method: 'POST' })).resolves.toBeUndefined();
  });
});
