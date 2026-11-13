import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue, type AuthStatus } from "./AuthProvider";
import { AuthGate } from "./AuthGate";

function renderGate(status: AuthStatus, retry = vi.fn()) {
  const value: AuthContextValue = {
    status,
    signOutNotice: null,
    setUp: vi.fn(),
    signIn: vi.fn(),
    signOut: vi.fn(),
    retry,
  };
  return render(
    <AuthContext.Provider value={value}>
      <AuthGate>
        <p>Signed-in content</p>
      </AuthGate>
    </AuthContext.Provider>,
  );
}

describe("AuthGate", () => {
  it("renders the app only when signed in", () => {
    renderGate("signedIn");

    expect(screen.getByText("Signed-in content")).toBeTruthy();
  });

  it("renders the setup screen when no owner account exists yet", () => {
    renderGate("setup");

    expect(screen.getByText("Set Up FinSight")).toBeTruthy();
    expect(screen.queryByText("Signed-in content")).toBeNull();
  });

  it("renders the sign-in screen when signed out", () => {
    renderGate("signedOut");

    expect(screen.getByText("Sign In to FinSight")).toBeTruthy();
    expect(screen.queryByText("Signed-in content")).toBeNull();
  });

  it("shows a loading status while the session is being checked", () => {
    renderGate("loading");

    expect(screen.getByRole("status").textContent).toBe("Loading FinSight");
    expect(screen.queryByText("Signed-in content")).toBeNull();
  });

  it("explains that the server is unreachable and offers Try Again, which retries", async () => {
    const user = userEvent.setup();
    const retry = vi.fn();
    renderGate("unavailable", retry);

    expect(screen.getByText("FinSight is not reachable")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Try Again" }));

    expect(retry).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Signed-in content")).toBeNull();
  });
});
