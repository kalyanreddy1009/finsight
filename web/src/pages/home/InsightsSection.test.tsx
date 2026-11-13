import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { getInsightsSummary } from "../../api/insights";
import type { InsightsSummary } from "../../api/types";
import { InsightsSection } from "./InsightsSection";
import { categoryTakeaway, percentText, trendTakeaway } from "./insightFormat";

vi.mock("../../api/insights", () => ({ getInsightsSummary: vi.fn() }));

const getInsightsMock = vi.mocked(getInsightsSummary);

function category(id: string, name: string, spent: number, shareBp: number) {
  return { category_id: id, name, spent_minor: spent, previous_minor: 0, share_bp: shareBp };
}

function insightsFixture(overrides: Partial<InsightsSummary> = {}): InsightsSummary {
  return {
    as_of: "2026-11-12",
    month: "2026-11",
    income_minor: 9000000,
    expense_minor: 2500000,
    net_minor: 6500000,
    previous_expense_minor: 3125000,
    categories: [
      category("rent", "Rent", 600000, 2400),
      category("food", "Groceries", 900000, 3600),
      category("c3", "Dining out", 400000, 1250),
      category("c4", "Transport", 300000, 1200),
      category("c5", "Utilities", 200000, 800),
      category("c6", "Shopping", 100000, 400),
      category("c7", "Other", 50000, 200),
    ],
    trend: [
      { year_month: "2026-09", income_minor: 9000000, expense_minor: 2600000 },
      { year_month: "2026-10", income_minor: 9000000, expense_minor: 3125000 },
      { year_month: "2026-11", income_minor: 9000000, expense_minor: 2500000 },
    ],
    highlights: [
      { kind: "spend_up", severity: "warning", title: "Dining out is up 40%", detail: "You spent more than last month." },
      { kind: "saving", severity: "info", title: "You saved 72% of income", detail: "Net ₹65,000.00." },
    ],
    ...overrides,
  };
}

describe("InsightsSection", () => {
  beforeEach(() => {
    getInsightsMock.mockReset();
  });

  it("shows a loading status while the insights load", () => {
    getInsightsMock.mockReturnValue(new Promise(() => undefined));

    render(<InsightsSection />);

    expect(screen.getByRole("status").textContent).toBe("Loading your insights");
  });

  it("lists the top six categories largest first with amounts and percents as text", async () => {
    getInsightsMock.mockResolvedValue(insightsFixture());

    render(<InsightsSection />);

    const card = (await screen.findByRole("heading", { name: "Spending by Category" })).closest("section") as HTMLElement;
    expect(within(card).getByText("Groceries is your largest category this month.")).toBeTruthy();
    const rows = within(card).getAllByRole("listitem");
    expect(rows).toHaveLength(6);
    expect(rows[0]?.textContent).toContain("Groceries");
    expect(rows[0]?.textContent).toContain("₹9,000.00");
    expect(rows[0]?.textContent).toContain("36%");
    expect(within(card).queryByText("Other")).toBeNull();
    expect(within(card).getByText("12.5%")).toBeTruthy();
  });

  it("describes the trend in words, as an image label and as a table with every month", async () => {
    getInsightsMock.mockResolvedValue(insightsFixture());

    render(<InsightsSection />);

    const card = (await screen.findByRole("heading", { name: "Six-Month Trend" })).closest("section") as HTMLElement;
    expect(within(card).getByText(/Spending so far this month is 20% lower than last month/)).toBeTruthy();
    const chart = within(card).getByRole("img");
    expect(chart.getAttribute("aria-label")).toContain("income ₹90,000.00, spending ₹26,000.00");
    const table = within(card).getByRole("table", { name: "Income and spending by month" });
    expect(within(table).getAllByRole("row")).toHaveLength(4);
    // The legend names both series in text, in addition to the table headers.
    expect(within(card).getAllByText("Income")).toHaveLength(2);
    expect(within(card).getAllByText("Spending")).toHaveLength(2);
  });

  it("labels warning highlights with Heads up and leaves info highlights unlabelled", async () => {
    getInsightsMock.mockResolvedValue(insightsFixture());

    render(<InsightsSection />);

    const card = (await screen.findByRole("heading", { name: "Highlights" })).closest("section") as HTMLElement;
    const items = within(card).getAllByRole("listitem");
    expect(within(items[0] as HTMLElement).getByText("Heads up")).toBeTruthy();
    expect(within(items[1] as HTMLElement).queryByText("Heads up")).toBeNull();
    expect(within(items[1] as HTMLElement).getByText("You saved 72% of income")).toBeTruthy();
  });

  it("shows its own sentences when there is no data", async () => {
    getInsightsMock.mockResolvedValue(
      insightsFixture({ categories: [], trend: [], highlights: [], expense_minor: 0, previous_expense_minor: 0 }),
    );

    render(<InsightsSection />);

    expect(await screen.findByText("No spending has been recorded this month yet.")).toBeTruthy();
    expect(screen.getByText("There is no spending from last month to compare with yet.")).toBeTruthy();
    expect(screen.getByText(/Nothing stands out yet/)).toBeTruthy();
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("shows an error with Try Again that reloads the insights", async () => {
    getInsightsMock.mockRejectedValueOnce(new ApiError(0, "NETWORK_ERROR", "offline"));
    getInsightsMock.mockResolvedValueOnce(insightsFixture());
    const user = userEvent.setup();
    render(<InsightsSection />);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Could not load your insights.");
    await user.click(within(alert).getByRole("button", { name: "Try Again" }));

    expect(await screen.findByRole("heading", { name: "Highlights" })).toBeTruthy();
    expect(getInsightsMock).toHaveBeenCalledTimes(2);
  });
});

describe("insight wording helpers", () => {
  it("formats basis points as whole or one-decimal percents", () => {
    expect(percentText(3600)).toBe("36%");
    expect(percentText(1250)).toBe("12.5%");
  });

  it("says higher, equal and lower for the month comparison", () => {
    expect(trendTakeaway({ expense_minor: 120000, previous_expense_minor: 100000 })).toContain("20% higher");
    expect(trendTakeaway({ expense_minor: 100000, previous_expense_minor: 100000 })).toContain("matches last month");
    expect(trendTakeaway({ expense_minor: 50000, previous_expense_minor: 100000 })).toContain("50% lower");
  });

  it("rounds the month comparison half up using whole paise", () => {
    expect(trendTakeaway({ expense_minor: 500, previous_expense_minor: 300 })).toContain("67% higher");
    expect(trendTakeaway({ expense_minor: 9, previous_expense_minor: 8 })).toContain("13% higher");
    expect(trendTakeaway({ expense_minor: 400, previous_expense_minor: 300 })).toContain("33% higher");
  });

  it("names the largest category regardless of server order", () => {
    expect(categoryTakeaway([category("a", "Small", 1, 100), category("b", "Big", 9, 9900)])).toBe(
      "Big is your largest category this month.",
    );
  });
});
