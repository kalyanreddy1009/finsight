import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { deleteBudget, getBudget, saveBudget, type Budget } from "../../api/budgets";
import type { Category } from "../../api/types";
import { installDialogStub } from "../transactions/testDialog";
import { BudgetSection } from "./BudgetSection";

vi.mock("../../api/budgets", () => ({ getBudget: vi.fn(), saveBudget: vi.fn(), deleteBudget: vi.fn() }));

const categories: Category[] = [
  categoryFixture("food", "Food", "EXPENSE"),
  categoryFixture("rent", "Rent", "EXPENSE"),
  categoryFixture("salary", "Salary", "INCOME"),
];

function categoryFixture(id: string, name: string, type: Category["category_type"]): Category {
  return {
    id,
    name,
    parent_category_id: null,
    category_type: type,
    default_tax_section: "NONE",
    is_discretionary: true,
    is_sensitive_private: false,
    is_system_category: false,
    created_at: "2026-01-01T00:00:00Z",
  };
}

// Food is near its 80% alert (₹9,000 of ₹10,000). Fun is over its limit (₹3,500 of ₹3,000).
const budget: Budget = {
  id: "b1",
  name: "November",
  period_month: "2026-11",
  total_limit_minor: 5000000,
  spent_minor: 4200000,
  categories: [
    { category_id: "food", category_name: "Food", limit_minor: 1000000, alert_threshold_pct: 80, spent_minor: 900000 },
    { category_id: "fun", category_name: "Fun", limit_minor: 300000, alert_threshold_pct: 90, spent_minor: 350000 },
  ],
};

beforeEach(() => {
  installDialogStub();
  vi.resetAllMocks();
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 10, 13));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("BudgetSection", () => {
  it("shows the spend against the total, a progress bar and per-category status words", async () => {
    vi.mocked(getBudget).mockResolvedValue({ month: "2026-11", budget });
    render(<BudgetSection categories={categories} />);

    expect(await screen.findByText("₹42,000.00 spent of ₹50,000.00")).toBeTruthy();
    const bar = screen.getByRole("progressbar", { name: "Budget used" });
    expect(bar.getAttribute("aria-valuenow")).toBe("84");
    expect(screen.getByText("₹9,000.00 of ₹10,000.00")).toBeTruthy();
    expect(screen.getByText("Near limit")).toBeTruthy();
    expect(screen.getByText("Over limit")).toBeTruthy();
    expect(getBudget).toHaveBeenCalledWith("2026-11");
  });

  it("states how far the total is over budget in words", async () => {
    vi.mocked(getBudget).mockResolvedValue({ month: "2026-11", budget: { ...budget, spent_minor: 5350000 } });
    render(<BudgetSection categories={categories} />);

    expect(await screen.findByText("₹3,500.00 over budget")).toBeTruthy();
  });

  it("offers to set a budget when the month has none", async () => {
    vi.mocked(getBudget).mockResolvedValue({ month: "2026-11", budget: null });
    render(<BudgetSection categories={categories} />);

    expect(await screen.findByText("No budget for November 2026 yet. Set a total limit to see how much you have spent.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Set Budget" })).toBeTruthy();
  });

  it("shows an error with a retry that loads the budget", async () => {
    const user = userEvent.setup();
    vi.mocked(getBudget).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce({ month: "2026-11", budget });
    render(<BudgetSection categories={categories} />);

    expect(await screen.findByText("Could not load this budget. Check your connection and try again.")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Try Again" }));
    expect(await screen.findByText("₹42,000.00 spent of ₹50,000.00")).toBeTruthy();
  });

  it("loads the next month when Next month is pressed", async () => {
    const user = userEvent.setup();
    vi.mocked(getBudget).mockResolvedValue({ month: "2026-11", budget: null });
    render(<BudgetSection categories={categories} />);
    await screen.findByText(/No budget for November 2026/);

    await user.click(screen.getByRole("button", { name: "Next month" }));

    expect(await screen.findByText(/No budget for December 2026/)).toBeTruthy();
    expect(getBudget).toHaveBeenLastCalledWith("2026-12");
  });

  it("converts rupees to paise in the PUT body and leaves blank categories out", async () => {
    const user = userEvent.setup();
    vi.mocked(getBudget).mockResolvedValue({ month: "2026-11", budget: null });
    vi.mocked(saveBudget).mockResolvedValue({ month: "2026-11", budget: null });
    render(<BudgetSection categories={categories} />);
    await user.click(await screen.findByRole("button", { name: "Set Budget" }));

    const dialog = screen.getByRole("dialog", { name: "Set Budget" });
    await user.type(within(dialog).getByLabelText("Total limit (₹)"), "50000.50");
    await user.type(within(dialog).getByLabelText("Food limit (₹)"), "1,000");
    await user.click(within(dialog).getByRole("button", { name: "Save Budget" }));

    await waitFor(() =>
      expect(saveBudget).toHaveBeenCalledWith("2026-11", {
        total_limit_minor: 5000050,
        categories: [{ category_id: "food", limit_minor: 100000 }],
      }),
    );
  });

  it("blocks saving when the category limits add up to more than the total", async () => {
    const user = userEvent.setup();
    vi.mocked(getBudget).mockResolvedValue({ month: "2026-11", budget: null });
    render(<BudgetSection categories={categories} />);
    await user.click(await screen.findByRole("button", { name: "Set Budget" }));

    const dialog = screen.getByRole("dialog", { name: "Set Budget" });
    await user.type(within(dialog).getByLabelText("Total limit (₹)"), "1000");
    await user.type(within(dialog).getByLabelText("Food limit (₹)"), "600");
    await user.type(within(dialog).getByLabelText("Rent limit (₹)"), "500");
    await user.click(within(dialog).getByRole("button", { name: "Save Budget" }));

    expect(await within(dialog).findByText(/Category limits add up to ₹1,100.00/)).toBeTruthy();
    expect(saveBudget).not.toHaveBeenCalled();
  });

  it("disables Set Budget and Edit Budget while the categories are not loaded", async () => {
    vi.mocked(getBudget).mockResolvedValueOnce({ month: "2026-11", budget: null });
    const { unmount } = render(<BudgetSection categories={null} />);
    expect(((await screen.findByRole("button", { name: "Set Budget" })) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("Categories are still loading.")).toBeTruthy();
    unmount();

    vi.mocked(getBudget).mockResolvedValueOnce({ month: "2026-11", budget });
    render(<BudgetSection categories={null} />);
    expect(((await screen.findByRole("button", { name: "Edit Budget" })) as HTMLButtonElement).disabled).toBe(true);
  });

  it("keeps a category outside the spending list and every threshold when saving", async () => {
    const user = userEvent.setup();
    vi.mocked(getBudget).mockResolvedValue({ month: "2026-11", budget });
    vi.mocked(saveBudget).mockResolvedValue({ month: "2026-11", budget });
    render(<BudgetSection categories={categories} />);
    await user.click(await screen.findByRole("button", { name: "Edit Budget" }));

    const dialog = screen.getByRole("dialog", { name: "Edit Budget" });
    await user.click(within(dialog).getByRole("button", { name: "Save Budget" }));

    await waitFor(() =>
      expect(saveBudget).toHaveBeenCalledWith("2026-11", {
        total_limit_minor: 5000000,
        categories: [
          { category_id: "food", limit_minor: 1000000, alert_threshold_pct: 80 },
          { category_id: "fun", limit_minor: 300000, alert_threshold_pct: 90 },
        ],
      }),
    );
  });

  it("removes the budget only after the second explicit click in the dialog", async () => {
    const user = userEvent.setup();
    vi.mocked(getBudget).mockResolvedValue({ month: "2026-11", budget });
    vi.mocked(deleteBudget).mockResolvedValue();
    render(<BudgetSection categories={categories} />);
    await screen.findByText("₹42,000.00 spent of ₹50,000.00");

    await user.click(screen.getByRole("button", { name: "Remove Budget" }));
    const dialog = screen.getByRole("dialog", { name: "Remove Budget" });
    expect(deleteBudget).not.toHaveBeenCalled();

    await user.click(within(dialog).getByRole("button", { name: "Yes, Remove Budget" }));
    await waitFor(() => expect(deleteBudget).toHaveBeenCalledWith("2026-11"));
    expect(await screen.findByText(/No budget for November 2026/)).toBeTruthy();
  });
});
