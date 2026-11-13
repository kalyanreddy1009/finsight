import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "../auth/AuthProvider";
import { AppShell } from "./AppShell";

function renderShell(path: string, signOut: AuthContextValue["signOut"] = vi.fn()) {
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
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<p>home body</p>} />
            <Route path="transactions" element={<p>transactions body</p>} />
            <Route path="accounts" element={<p>accounts body</p>} />
            <Route path="plan" element={<p>plan body</p>} />
            <Route path="assistant" element={<p>assistant body</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe("AppShell", () => {
  it("renders the five primary links inside the Primary navigation", () => {
    renderShell("/");

    const nav = screen.getByRole("navigation", { name: "Primary" });
    const links = within(nav).getAllByRole("link");

    expect(links.map((link) => link.textContent)).toEqual([
      "Home",
      "Transactions",
      "Accounts",
      "Plan",
      "Assistant",
    ]);
  });

  it("marks only the active route with aria-current=page", () => {
    renderShell("/transactions");

    const nav = screen.getByRole("navigation", { name: "Primary" });
    const current = within(nav)
      .getAllByRole("link")
      .filter((link) => link.getAttribute("aria-current") === "page");

    expect(current.map((link) => link.textContent)).toEqual(["Transactions"]);
  });

  it("keeps Home inactive on other routes", () => {
    renderShell("/plan");

    const home = within(screen.getByRole("navigation", { name: "Primary" })).getByRole("link", {
      name: "Home",
    });

    expect(home.getAttribute("aria-current")).toBeNull();
  });

  it("offers a skip link to the main content", () => {
    renderShell("/");

    const skip = screen.getByRole("link", { name: "Skip to content" });
    const main = screen.getByRole("main");

    expect(skip.getAttribute("href")).toBe("#main");
    expect(main.id).toBe("main");
    expect(screen.getByText("home body")).toBeTruthy();
  });

  it("puts a Sign Out button in the header, outside the navigation", () => {
    renderShell("/");

    const header = screen.getByRole("banner");
    const button = within(header).getByRole("button", { name: "Sign Out" });

    expect(button).toBeTruthy();
    expect(within(screen.getByRole("navigation", { name: "Primary" })).queryByRole("button")).toBeNull();
  });

  it("signs out once and disables the button while signing out", async () => {
    const user = userEvent.setup();
    const signOut = vi.fn(() => new Promise<void>(() => undefined));
    renderShell("/", signOut);

    await user.click(screen.getByRole("button", { name: "Sign Out" }));

    expect(signOut).toHaveBeenCalledTimes(1);
    const pending = await screen.findByRole("button", { name: "Signing Out…" });
    expect((pending as HTMLButtonElement).disabled).toBe(true);
  });
});
