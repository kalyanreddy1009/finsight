import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

vi.mock("./api/auth", () => ({
  getAuthConfigured: vi.fn(),
  restoreSession: vi.fn(),
  setupOwner: vi.fn(),
  signIn: vi.fn(),
  signOut: vi.fn(),
}));

// The dashboard never resolves here, so Home stays in its loading state and the test only checks the shell.
vi.mock("./api/dashboard", () => ({
  getDashboardSummary: vi.fn(() => new Promise<never>(() => undefined)),
}));

const TAB_LABELS = ["Home", "Transactions", "Accounts", "Plan", "Assistant"];

function renderAppAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

async function primaryNav(): Promise<HTMLElement> {
  return screen.findByRole("navigation", { name: "Primary" });
}

describe("App", () => {
  beforeEach(async () => {
    const auth = await import("./api/auth");
    vi.mocked(auth.getAuthConfigured).mockResolvedValue(true);
    vi.mocked(auth.restoreSession).mockResolvedValue(undefined);
  });

  it("renders the five tabs for a signed-in user", async () => {
    renderAppAt("/");

    const nav = await primaryNav();

    expect(within(nav).getAllByRole("link").map((link) => link.textContent)).toEqual(TAB_LABELS);
  });

  it("marks the current tab with aria-current and leaves the others unmarked", async () => {
    renderAppAt("/");

    const nav = await primaryNav();

    expect(within(nav).getByRole("link", { name: "Home" }).getAttribute("aria-current")).toBe("page");
    expect(within(nav).getByRole("link", { name: "Accounts" }).getAttribute("aria-current")).toBeNull();
  });

  it("opens the Assistant page and marks its tab current", async () => {
    renderAppAt("/assistant");

    const nav = await primaryNav();

    expect(within(nav).getByRole("link", { name: "Assistant" }).getAttribute("aria-current")).toBe("page");
    expect(await screen.findByRole("heading", { name: "Assistant" })).toBeTruthy();
  });

  it("sends an unknown path to Home", async () => {
    renderAppAt("/no-such-page");

    const nav = await primaryNav();

    expect(within(nav).getByRole("link", { name: "Home" }).getAttribute("aria-current")).toBe("page");
  });
});
