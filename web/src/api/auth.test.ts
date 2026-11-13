import { beforeEach, describe, expect, it, vi } from "vitest";
import { refreshSession, request, setAccessToken } from "./client";
import { DEFAULT_DEVICE_NAME, getAuthConfigured, restoreSession, setupOwner, signIn, signOut } from "./auth";

vi.mock("./client", () => ({
  request: vi.fn(),
  refreshSession: vi.fn(),
  setAccessToken: vi.fn(),
}));

const requestMock = vi.mocked(request);
const refreshMock = vi.mocked(refreshSession);
const setTokenMock = vi.mocked(setAccessToken);

const sessionResponse = { data: { access_token: "token-1" }, meta: null };

describe("auth API", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("reads whether the owner account is configured", async () => {
    requestMock.mockResolvedValue({ data: { configured: true }, meta: null });

    const configured = await getAuthConfigured();

    expect(requestMock).toHaveBeenCalledWith("GET", "/auth/status");
    expect(configured).toBe(true);
  });

  it("sets up the owner with the password, device name and setup code, then stores the token", async () => {
    requestMock.mockResolvedValue(sessionResponse);

    await setupOwner("pw-123", "Laptop", "setup-code");

    expect(requestMock).toHaveBeenCalledWith("POST", "/auth/setup", {
      body: { password: "pw-123", device_name: "Laptop", setup_token: "setup-code" },
    });
    expect(setTokenMock).toHaveBeenCalledWith("token-1");
  });

  it("signs in with the password and the default device name, then stores the token", async () => {
    requestMock.mockResolvedValue(sessionResponse);

    await signIn("pw-123");

    expect(requestMock).toHaveBeenCalledWith("POST", "/auth/login", {
      body: { password: "pw-123", device_name: DEFAULT_DEVICE_NAME },
    });
    expect(setTokenMock).toHaveBeenCalledWith("token-1");
  });

  it("restores the session through a token refresh", async () => {
    refreshMock.mockResolvedValue(undefined);

    await restoreSession();

    expect(refreshMock).toHaveBeenCalledTimes(1);
  });

  it("posts logout and clears the local token", async () => {
    requestMock.mockResolvedValue({ data: null, meta: null });

    await signOut();

    expect(requestMock).toHaveBeenCalledWith("POST", "/auth/logout");
    expect(setTokenMock).toHaveBeenCalledWith(null);
  });

  it("still clears the local token when logout fails, and rethrows the failure", async () => {
    const failure = new Error("server down");
    requestMock.mockRejectedValue(failure);

    await expect(signOut()).rejects.toBe(failure);

    expect(setTokenMock).toHaveBeenCalledWith(null);
  });
});
