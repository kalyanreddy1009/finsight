import { createContext, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { getAuthConfigured, restoreSession, setupOwner, signIn, signOut } from "../api/auth";
import { onSignedOut } from "../api/client";

export const SIGN_OUT_FAILED_NOTICE =
  "Signed out on this device, but the server could not be reached. Sign in and sign out again to end the session.";

export type AuthStatus = "loading" | "unavailable" | "setup" | "signedOut" | "signedIn";

export interface AuthContextValue {
  status: AuthStatus;
  // Shown on the sign-in screen after a sign-out the server did not confirm.
  signOutNotice: string | null;
  setUp: (password: string, deviceName: string, setupToken: string) => Promise<void>;
  signIn: (password: string) => Promise<void>;
  signOut: () => Promise<void>;
  retry: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

// Status check first; if already configured, try a silent refresh to restore the session.
async function bootstrap(): Promise<AuthStatus> {
  let configured: boolean;
  try {
    configured = await getAuthConfigured();
  } catch {
    return "unavailable";
  }
  if (!configured) {
    return "setup";
  }
  try {
    await restoreSession();
    return "signedIn";
  } catch {
    return "signedOut";
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [attempt, setAttempt] = useState(0);
  const [signOutNotice, setSignOutNotice] = useState<string | null>(null);

  useEffect(() => onSignedOut(() => setStatus("signedOut")), []);

  useEffect(() => {
    let cancelled = false;
    void bootstrap().then((next) => {
      if (!cancelled) {
        setStatus(next);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const retry = useCallback(() => {
    setStatus("loading");
    setAttempt((count) => count + 1);
  }, []);

  const setUp = useCallback(async (password: string, deviceName: string, setupToken: string) => {
    await setupOwner(password, deviceName, setupToken);
    setStatus("signedIn");
  }, []);

  const signInWithPassword = useCallback(async (password: string) => {
    await signIn(password);
    setSignOutNotice(null);
    setStatus("signedIn");
  }, []);

  const signOutOfApp = useCallback(async () => {
    try {
      await signOut();
      setSignOutNotice(null);
    } catch {
      setSignOutNotice(SIGN_OUT_FAILED_NOTICE);
    }
    setStatus("signedOut");
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ status, signOutNotice, setUp, signIn: signInWithPassword, signOut: signOutOfApp, retry }),
    [status, signOutNotice, setUp, signInWithPassword, signOutOfApp, retry],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
