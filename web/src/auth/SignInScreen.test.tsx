import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { AuthContext, type AuthContextValue } from "./AuthProvider";
import { SignInScreen } from "./SignInScreen";

function renderSignIn(signIn: AuthContextValue["signIn"]) {
  const value: AuthContextValue = {
    status: "signedOut",
    signOutNotice: null,
    setUp: vi.fn(),
    signIn,
    signOut: vi.fn(),
    retry: vi.fn(),
  };
  return render(
    <AuthContext.Provider value={value}>
      <SignInScreen />
    </AuthContext.Provider>,
  );
}

describe("SignInScreen", () => {
  it("shows a plain-language message next to the password for INVALID_CREDENTIALS", async () => {
    const signIn = vi.fn(() => Promise.reject(new ApiError(401, "INVALID_CREDENTIALS", "Invalid credentials.")));
    renderSignIn(signIn);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Password"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "Sign In" }));

    expect(signIn).toHaveBeenCalledWith("wrong-password");
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe("That password is not right. Check it and try again.");
    expect(screen.getByLabelText("Password").getAttribute("aria-invalid")).toBe("true");
  });

  it("shows the lockout message for TOO_MANY_ATTEMPTS", async () => {
    const signIn = vi.fn(() => Promise.reject(new ApiError(429, "TOO_MANY_ATTEMPTS", "Too many.")));
    renderSignIn(signIn);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Password"), "anything");
    await user.click(screen.getByRole("button", { name: "Sign In" }));

    expect((await screen.findByRole("alert")).textContent).toBe(
      "Too many failed attempts. Wait a few minutes, then try again.",
    );
  });

  it("disables the button and changes its label while signing in", async () => {
    const signIn = vi.fn(() => new Promise<void>(() => undefined));
    renderSignIn(signIn);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Password"), "correct-horse-battery");
    await user.click(screen.getByRole("button", { name: "Sign In" }));

    const button = await screen.findByRole("button", { name: "Signing In…" });
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });

  it("does not prefill the password field", () => {
    renderSignIn(vi.fn());

    expect((screen.getByLabelText("Password") as HTMLInputElement).value).toBe("");
  });
});
