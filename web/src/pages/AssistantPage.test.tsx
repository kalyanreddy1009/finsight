import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "../auth/AuthProvider";
import { AssistantPage } from "./AssistantPage";

function renderAssistant(signOut: AuthContextValue["signOut"]) {
  const value: AuthContextValue = {
    status: "signedIn",
    signOutNotice: null,
    setUp: vi.fn(),
    signIn: vi.fn(),
    signOut,
    retry: vi.fn(),
  };
  return render(
    <AuthContext.Provider value={value}>
      <AssistantPage />
    </AuthContext.Provider>,
  );
}

describe("AssistantPage", () => {
  it("says the assistant is not available yet", () => {
    renderAssistant(vi.fn());

    expect(screen.getByRole("heading", { name: "Assistant" })).toBeTruthy();
    expect(screen.getByText(/The assistant is not available yet/)).toBeTruthy();
  });

  it("signs out and disables the button while signing out", async () => {
    const user = userEvent.setup();
    const signOut = vi.fn(() => new Promise<void>(() => undefined));
    renderAssistant(signOut);

    await user.click(screen.getByRole("button", { name: "Sign Out" }));

    expect(signOut).toHaveBeenCalledTimes(1);
    const button = await screen.findByRole("button", { name: "Signing Out…" });
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });
});
