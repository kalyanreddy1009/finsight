import type { ApiEnvelope, ApiMeta, SessionData } from "./types";

// Paths passed to request() are relative to /api/v1, e.g. "/dashboard/summary".
const API_BASE = "/api/v1";
const AUTH_PATH_PREFIX = "/auth/";
const UNAUTHORIZED = 401;
const CSRF_HEADERS = { "X-Requested-With": "finsight" } as const;
const NETWORK_MESSAGE = "FinSight cannot be reached. Check your connection and try again.";
const GENERIC_MESSAGE = "Something went wrong. Try again.";

export type HttpMethod = "GET" | "POST" | "PATCH" | "DELETE";

export interface RequestOptions {
  body?: unknown;
  headers?: Record<string, string>;
  idempotent?: boolean;
}

export interface ApiResult<T> {
  data: T;
  meta: ApiMeta;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly meta: ApiMeta;

  constructor(status: number, code: string, message: string, meta: ApiMeta = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.meta = meta;
  }
}

// The access token lives in memory only. Never persist it or put it in a URL.
let accessToken: string | null = null;
const signedOutListeners = new Set<() => void>();
let inFlightRefresh: Promise<void> | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function onSignedOut(listener: () => void): () => void {
  signedOutListeners.add(listener);
  return () => {
    signedOutListeners.delete(listener);
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isAuthPath(path: string): boolean {
  return path.startsWith(AUTH_PATH_PREFIX);
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    // A body that is not JSON is reported by the caller as an unexpected response.
    return null;
  }
}

function errorFromBody(status: number, body: unknown, ok: boolean): ApiError {
  const detail = isRecord(body) && isRecord(body.error) ? body.error : null;
  const meta = isRecord(body) && isRecord(body.meta) ? body.meta : null;
  if (detail !== null && typeof detail.code === "string" && typeof detail.message === "string") {
    return new ApiError(status, detail.code, detail.message, meta);
  }
  return ok
    ? new ApiError(status, "INVALID_RESPONSE", GENERIC_MESSAGE)
    : new ApiError(status, "HTTP_ERROR", GENERIC_MESSAGE);
}

async function parseEnvelope<T>(response: Response): Promise<ApiResult<T>> {
  const body = await readJson(response);
  if (response.ok && isRecord(body) && body.error === null && "data" in body) {
    const envelope = body as unknown as ApiEnvelope<T>;
    return { data: envelope.data as T, meta: envelope.meta };
  }
  throw errorFromBody(response.status, body, response.ok);
}

async function send(
  method: HttpMethod,
  path: string,
  options: RequestOptions,
  token: string | null,
  idempotencyKey: string | null,
): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json", ...options.headers };
  const init: RequestInit = { method, credentials: "include", headers };
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(options.body);
  }
  if (token !== null) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (idempotencyKey !== null) {
    headers["Idempotency-Key"] = idempotencyKey;
  }
  try {
    return await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", NETWORK_MESSAGE);
  }
}

async function performRefresh(): Promise<void> {
  try {
    const response = await send("POST", "/auth/refresh", { headers: { ...CSRF_HEADERS } }, null, null);
    const { data } = await parseEnvelope<SessionData>(response);
    accessToken = data.access_token;
  } catch (error) {
    accessToken = null;
    signedOutListeners.forEach((listener) => listener());
    throw error;
  }
}

// Concurrent callers share one refresh. Refresh tokens rotate, so a second refresh would fail.
export function refreshSession(): Promise<void> {
  if (inFlightRefresh === null) {
    inFlightRefresh = performRefresh().finally(() => {
      inFlightRefresh = null;
    });
  }
  return inFlightRefresh;
}

export async function request<T>(
  method: HttpMethod,
  path: string,
  options: RequestOptions = {},
): Promise<ApiResult<T>> {
  const idempotencyKey = options.idempotent === true ? crypto.randomUUID() : null;
  const sentWith = accessToken;
  const response = await send(method, path, options, sentWith, idempotencyKey);
  if (response.status !== UNAUTHORIZED || isAuthPath(path)) {
    return parseEnvelope<T>(response);
  }

  const unauthorized = errorFromBody(response.status, await readJson(response), false);
  if (accessToken === sentWith) {
    try {
      await refreshSession();
    } catch {
      // The session is gone and sign-out listeners were notified. Report the original 401.
      throw unauthorized;
    }
  }
  const retried = await send(method, path, options, accessToken, idempotencyKey);
  return parseEnvelope<T>(retried);
}
