const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

let tokenGetter: () => Promise<string | null> = async () => null;

export function setTokenGetter(fn: () => Promise<string | null>) {
  tokenGetter = fn;
}

export type ApiResult<T = unknown> = {
  ok: boolean;
  status: number;
  data?: T;
  error?: unknown;
};

export type ApiLogEntry = {
  method: string;
  path: string;
  status: number;
  ok: boolean;
  body: unknown;
  at: string;
};

type Listener = (entry: ApiLogEntry) => void;
const listeners = new Set<Listener>();

export function onApiResult(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export async function api<T = unknown>(
  path: string,
  opts: { method?: string; body?: unknown } = {},
): Promise<ApiResult<T>> {
  const method = opts.method ?? "GET";
  const token = await tokenGetter();
  let status = 0;
  let payload: unknown = null;
  try {
    const res = await fetch(`${BASE}/api/v1${path}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
    status = res.status;
    const text = await res.text();
    payload = text ? JSON.parse(text) : null;
    const result: ApiResult<T> = res.ok
      ? { ok: true, status, data: payload as T }
      : { ok: false, status, error: payload };
    emit({ method, path, status, ok: res.ok, body: payload });
    return result;
  } catch (err) {
    emit({ method, path, status, ok: false, body: String(err) });
    return { ok: false, status, error: err };
  }
}

function emit(entry: Omit<ApiLogEntry, "at">) {
  const full: ApiLogEntry = { ...entry, at: new Date().toLocaleTimeString() };
  listeners.forEach((fn) => fn(full));
}
