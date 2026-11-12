import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, onSignedOut, request, setAccessToken } from "./client";

type FetchHandler = (url: string, init: RequestInit) => Response | Promise<Response>;

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function envelope(data: unknown, meta: Record<string, unknown> | null = null): unknown {
  return { data, error: null, meta };
}

function errorEnvelope(code: string, message: string): unknown {
  return { data: null, error: { code, message }, meta: null };
}

function authHeader(init: RequestInit): string | null {
  const headers = init.headers as Record<string, string>;
  return headers.Authorization ?? null;
}

function mockFetch(handler: FetchHandler) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
    handler(String(input), init ?? {}),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function callsTo(fetchMock: ReturnType<typeof mockFetch>, path: string): RequestInit[] {
  return fetchMock.mock.calls
    .filter(([input]) => String(input) === `/api/v1${path}`)
    .map(([, init]) => init ?? {});
}

describe("api client", () => {
  let unsubscribe: (() => void) | null = null;

  beforeEach(() => {
    setAccessToken(null);
  });

  afterEach(() => {
    unsubscribe?.();
    unsubscribe = null;
    vi.unstubAllGlobals();
  });

  it("unwraps the envelope into data and meta", async () => {
    mockFetch(() => jsonResponse(200, envelope({ value: 42 }, { next_cursor: "abc" })));

    const result = await request<{ value: number }>("GET", "/dashboard/summary");

    expect(result.data).toEqual({ value: 42 });
    expect(result.meta).toEqual({ next_cursor: "abc" });
  });

  it("throws ApiError with status, code, message and meta for an error envelope", async () => {
    mockFetch(() =>
      jsonResponse(429, {
        data: null,
        error: { code: "TOO_MANY_ATTEMPTS", message: "Too many failed sign-in attempts." },
        meta: { retry: 1 },
      }),
    );

    const failure = await request("GET", "/dashboard/summary").catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).toMatchObject({
      status: 429,
      code: "TOO_MANY_ATTEMPTS",
      message: "Too many failed sign-in attempts.",
      meta: { retry: 1 },
    });
  });

  it("reports a network failure as NETWORK_ERROR", async () => {
    mockFetch(() => {
      throw new TypeError("Failed to fetch");
    });

    const failure = await request("GET", "/dashboard/summary").catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).toMatchObject({ status: 0, code: "NETWORK_ERROR" });
  });

  it("sends credentials and the bearer token from memory", async () => {
    setAccessToken("token-1");
    const fetchMock = mockFetch(() => jsonResponse(200, envelope([])));

    await request("GET", "/accounts");

    const firstCall = fetchMock.mock.calls[0];
    expect(String(firstCall?.[0])).toBe("/api/v1/accounts");
    expect(firstCall?.[1]?.credentials).toBe("include");
    expect(authHeader(firstCall?.[1] ?? {})).toBe("Bearer token-1");
  });

  it("shares one refresh between concurrent 401s and retries both requests", async () => {
    setAccessToken("expired");
    const fetchMock = mockFetch((url, init) => {
      if (url === "/api/v1/auth/refresh") {
        return jsonResponse(200, envelope({ access_token: "fresh", token_type: "Bearer" }));
      }
      return authHeader(init) === "Bearer fresh"
        ? jsonResponse(200, envelope({ ok: true }))
        : jsonResponse(401, errorEnvelope("UNAUTHORIZED", "Authentication required."));
    });

    const [first, second] = await Promise.all([
      request<{ ok: boolean }>("GET", "/dashboard/summary"),
      request<{ ok: boolean }>("GET", "/accounts"),
    ]);

    expect(first.data).toEqual({ ok: true });
    expect(second.data).toEqual({ ok: true });
    expect(callsTo(fetchMock, "/auth/refresh")).toHaveLength(1);
    const refreshHeaders = callsTo(fetchMock, "/auth/refresh")[0]?.headers as Record<string, string>;
    expect(refreshHeaders["X-Requested-With"]).toBe("finsight");
  });

  it("notifies sign-out listeners and reports the original 401 when refresh fails", async () => {
    setAccessToken("expired");
    const onSignedOutSpy = vi.fn();
    unsubscribe = onSignedOut(onSignedOutSpy);
    mockFetch((url) =>
      url === "/api/v1/auth/refresh"
        ? jsonResponse(401, errorEnvelope("UNAUTHORIZED", "Authentication required."))
        : jsonResponse(401, errorEnvelope("UNAUTHORIZED", "Authentication required.")),
    );

    const failure = await request("GET", "/dashboard/summary").catch((error: unknown) => error);

    expect(failure).toMatchObject({ status: 401, code: "UNAUTHORIZED" });
    expect(onSignedOutSpy).toHaveBeenCalledTimes(1);
  });

  it("does not attempt a refresh for auth routes", async () => {
    const fetchMock = mockFetch(() => jsonResponse(401, errorEnvelope("INVALID_CREDENTIALS", "Invalid credentials.")));

    const failure = await request("POST", "/auth/login", { body: { password: "x" } }).catch(
      (error: unknown) => error,
    );

    expect(failure).toMatchObject({ code: "INVALID_CREDENTIALS" });
    expect(callsTo(fetchMock, "/auth/refresh")).toHaveLength(0);
  });

  it("reuses the same Idempotency-Key on the retry after a refresh", async () => {
    setAccessToken("expired");
    const fetchMock = mockFetch((url, init) => {
      if (url === "/api/v1/auth/refresh") {
        return jsonResponse(200, envelope({ access_token: "fresh", token_type: "Bearer" }));
      }
      return authHeader(init) === "Bearer fresh"
        ? jsonResponse(201, envelope({ id: "tx-1" }))
        : jsonResponse(401, errorEnvelope("UNAUTHORIZED", "Authentication required."));
    });

    const result = await request<{ id: string }>("POST", "/transactions", {
      body: { kind: "expense" },
      idempotent: true,
    });

    const attempts = callsTo(fetchMock, "/transactions");
    expect(result.data).toEqual({ id: "tx-1" });
    expect(attempts).toHaveLength(2);
    const keys = attempts.map((init) => (init.headers as Record<string, string>)["Idempotency-Key"]);
    expect(keys[0]).toMatch(/^[0-9a-f-]{36}$/);
    expect(keys[1]).toBe(keys[0]);
  });
});
