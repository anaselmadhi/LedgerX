import { parse, stringify } from 'lossless-json';

/** Every JSON integer stays a BigInt, including counts. API contracts remain unchanged. */
export function parseWire<T>(text: string): T {
  return parse(text, null, (value) => (/^-?\d+$/.test(value) ? BigInt(value) : Number(value))) as T;
}
export function encodeWire(value: unknown): string {
  const encoded = stringify(value);
  if (encoded === undefined) throw new Error('Cannot encode the request.');
  return encoded;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly requestId: string | null = null,
    public readonly ambiguous = false,
  ) {
    super(message);
  }
}

type RequestOptions = { method?: 'GET' | 'POST'; body?: unknown; key?: string };

export class Api {
  private disposed = false;
  // Only in memory: never in URLs, localStorage, sessionStorage or browser logs.
  constructor(
    private token = '',
    private expired: () => void = () => {},
  ) {}

  dispose(): void {
    this.disposed = true;
    this.token = '';
    this.expired = () => {};
  }

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    if (this.disposed) throw new ApiError('This session has ended. Please sign in again.', 401);
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    if (options.key) headers['Idempotency-Key'] = options.key;
    let response: Response;
    try {
      response = await fetch(path, {
        method: options.method || 'GET',
        headers,
        body: options.body === undefined ? undefined : encodeWire(options.body),
        cache: 'no-store',
        credentials: 'omit',
        signal: AbortSignal.timeout(20_000),
      });
    } catch {
      throw new ApiError(
        'The server could not be reached. Check your connection and try again.',
        0,
        null,
        true,
      );
    }
    if (response.status === 401 && this.token) this.expired();
    if (response.status === 204) return undefined as T;
    const requestId = response.headers.get('X-Request-ID');
    let data: { detail?: unknown };
    try {
      data = parseWire(await response.text());
    } catch {
      throw new ApiError(
        'The server returned an unreadable response. Please try again.',
        response.status,
        requestId,
        true,
      );
    }
    if (!response.ok) {
      let message = 'The request could not be completed.';
      if (typeof data.detail === 'string') message = data.detail;
      if (response.status === 422)
        message = 'Check the fields and try again. Some values are invalid.';
      if (response.status === 401)
        message = this.token
          ? 'Your session has expired. Please sign in again.'
          : 'Username or password is incorrect.';
      throw new ApiError(message, response.status, requestId, response.status >= 500);
    }
    return data as T;
  }
}

/** A confirmed payment intent owns one key and one immutable payload, across retries. */
export class PaymentIntent {
  readonly key: string;
  private readonly encoded: string;
  constructor(
    readonly path: string,
    body: unknown,
  ) {
    if (typeof crypto.randomUUID !== 'function') {
      throw new Error('Open LedgerX on localhost or HTTPS to send payments securely.');
    }
    this.key = crypto.randomUUID();
    this.encoded = encodeWire(body);
  }
  send<T>(api: Api): Promise<T> {
    return api.request<T>(this.path, {
      method: 'POST',
      body: parseWire(this.encoded),
      key: this.key,
    });
  }
}
