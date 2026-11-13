import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { getAuthConfigured, restoreSession, setupOwner, signIn, signOut } from "../api/auth";
import { AuthProvider, SIGN_OUT_FAILED_NOTICE } from "./AuthProvider";
import { useAuth } from "./useAuth";

const signedOutListeners = vi.hoisted(() => new Set<() => void>());

vi.mock("../api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/client")>()),
  onSignedOut: (listener: () => void) => {
    signedOutListeners.add(listener);
    return () => {
      signedOutListeners.delete(listener);
    };
  },
}));

vi.mock("../api/auth", () => ({
  getAuthConfigured: vi.fn(),
  restoreSession: vi.fn(),
  setupOwner: vi.fn(),
  signIn: vi.fn(),
  signOut: vi.fn(),
}));

// Shows the provider state as text and exposes each action as a button.
function Probe() {
  const auth = useAuth();
  return (
    <>
      <p data-testid="status">{auth.status}</p>
      <p data-testid="notice">{auth.signOutNotice ?? "none"}</p>
      <button type="button" onClick={() => void auth.signIn("pw-123").catch(() => undefined)}>
        Sign In
      </button>
      <button type="button" onClick={() => void auth.signOut()}>
        Sign Out
      </button>
      <button type="button" onClick={() => void auth.setUp("pw-123", "Laptop", "setup-code")}>
        Set Up
      </button>
      <button type="button" onClick={auth.retry}>
        Retry
      </button>
    </>
  );
}

function renderProvider() {
  return render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
}

async function expectStatus(status: string) {
  await waitFor(() => expect(screen.getByTestId("status").textContent).toBe(status));
}

const configuredMock = vi.mocked(getAuthConfigured);
const restoreMock = vi.mocked(restoreSession);
const setUpMock = vi.mocked(setupOwner);
const signInMock = vi.mocked(signIn);
const signOutMock = vi.mocked(signOut);

describe("AuthProvider", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    signedOutListeners.clear();
  });

  it("shows setup and does not try to restore a session when no owner exists yet", async () => {
    configuredMock.mockResolvedValue(false);

    renderProvider();

    await expectStatus("setup");
    expect(restoreMock).not.toHaveBeenCalled();
  });

  it("signs in silently when the server is configured and the refresh succeeds", async () => {
    configuredMock.mockResolvedValue(true);
    restoreMock.mockResolvedValue(undefined);

    renderProvider();

    await expectStatus("signedIn");
  });

  it("shows signed out when the silent refresh is rejected", async () => {
    configuredMock.mockResolvedValue(true);
    restoreMock.mockRejectedValue(new ApiError(401, "UNAUTHORIZED", "Session ended."));

    renderProvider();

    await expectStatus("signedOut");
  });

  it("shows unavailable when the status check fails, and Try Again checks once more", async () => {
    const user = userEvent.setup();
    configuredMock.mockRejectedValueOnce(new ApiError(0, "NETWORK_ERROR", "unreachable"));
    configuredMock.mockResolvedValueOnce(true);
    restoreMock.mockResolvedValue(undefined);
    renderProvider();

    await expectStatus("unavailable");
    await user.click(screen.getByRole("button", { name: "Retry" }));

    await expectStatus("signedIn");
    expect(configuredMock).toHaveBeenCalledTimes(2);
  });

  it("signs in with the password and moves to signed in", async () => {
    const user = userEvent.setup();
    configuredMock.mockResolvedValue(true);
    restoreMock.mockRejectedValue(new ApiError(401, "UNAUTHORIZED", "Session ended."));
    signInMock.mockResolvedValue(undefined);
    renderProvider();
    await expectStatus("signedOut");

    await user.click(screen.getByRole("button", { name: "Sign In" }));

    await expectStatus("signedIn");
    expect(signInMock).toHaveBeenCalledWith("pw-123");
  });

  it("stays signed out and reports the failure to the caller when sign-in fails", async () => {
    const user = userEvent.setup();
    configuredMock.mockResolvedValue(true);
    restoreMock.mockRejectedValue(new ApiError(401, "UNAUTHORIZED", "Session ended."));
    signInMock.mockRejectedValue(new ApiError(401, "INVALID_CREDENTIALS", "Invalid credentials."));
    renderProvider();
    await expectStatus("signedOut");

    await user.click(screen.getByRole("button", { name: "Sign In" }));

    await waitFor(() => expect(signInMock).toHaveBeenCalledTimes(1));
    expect(screen.getByTestId("status").textContent).toBe("signedOut");
  });

  it("sets up the owner and moves to signed in", async () => {
    const user = userEvent.setup();
    configuredMock.mockResolvedValue(false);
    setUpMock.mockResolvedValue(undefined);
    renderProvider();
    await expectStatus("setup");

    await user.click(screen.getByRole("button", { name: "Set Up" }));

    await expectStatus("signedIn");
    expect(setUpMock).toHaveBeenCalledWith("pw-123", "Laptop", "setup-code");
  });

  it("signs out, clears any notice, and returns to signed out", async () => {
    const user = userEvent.setup();
    configuredMock.mockResolvedValue(true);
    restoreMock.mockResolvedValue(undefined);
    signOutMock.mockResolvedValue(undefined);
    renderProvider();
    await expectStatus("signedIn");

    await user.click(screen.getByRole("button", { name: "Sign Out" }));

    await expectStatus("signedOut");
    expect(screen.getByTestId("notice").textContent).toBe("none");
    expect(signOutMock).toHaveBeenCalledTimes(1);
  });

  it("still signs out locally and shows the notice when the server cannot end the session", async () => {
    const user = userEvent.setup();
    configuredMock.mockResolvedValue(true);
    restoreMock.mockResolvedValue(undefined);
    signOutMock.mockRejectedValue(new ApiError(0, "NETWORK_ERROR", "unreachable"));
    renderProvider();
    await expectStatus("signedIn");

    await user.click(screen.getByRole("button", { name: "Sign Out" }));

    await expectStatus("signedOut");
    expect(screen.getByTestId("notice").textContent).toBe(SIGN_OUT_FAILED_NOTICE);
  });

  it("signs out when the API reports that the session has ended", async () => {
    configuredMock.mockResolvedValue(true);
    restoreMock.mockResolvedValue(undefined);
    renderProvider();
    await expectStatus("signedIn");

    act(() => {
      signedOutListeners.forEach((listener) => listener());
    });

    await expectStatus("signedOut");
  });
});
