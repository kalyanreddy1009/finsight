import { refreshSession, request, setAccessToken } from "./client";
import type { AuthStatusData, SessionData } from "./types";

export const DEFAULT_DEVICE_NAME = "Web browser";

async function storeSession(path: string, body: unknown): Promise<void> {
  const { data } = await request<SessionData>("POST", path, { body });
  setAccessToken(data.access_token);
}

export async function getAuthConfigured(): Promise<boolean> {
  const { data } = await request<AuthStatusData>("GET", "/auth/status");
  return data.configured;
}

export function setupOwner(password: string, deviceName: string, setupToken: string): Promise<void> {
  return storeSession("/auth/setup", { password, device_name: deviceName, setup_token: setupToken });
}

export function signIn(password: string): Promise<void> {
  return storeSession("/auth/login", { password, device_name: DEFAULT_DEVICE_NAME });
}

export function restoreSession(): Promise<void> {
  return refreshSession();
}

// The local session always ends. If the server could not end it, the error is rethrown so the
// caller can tell the user the server-side device is still active.
export async function signOut(): Promise<void> {
  try {
    await request("POST", "/auth/logout");
  } finally {
    setAccessToken(null);
  }
}
