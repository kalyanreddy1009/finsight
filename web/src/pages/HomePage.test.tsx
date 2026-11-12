import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getDashboardSummary } from "../api/dashboard";
import { ApiError } from "../api/client";
import type { DashboardSummary } from "../api/types";
import { HomePage } from "./HomePage";

vi.mock("../api/dashboard", () => ({ getDashboardSummary: vi.fn() }));

const getSummaryMock = vi.mocked(getDashboardSummary);

function summaryFixture(overrides: Partial<DashboardSummary> = {}): DashboardSummary {
  return {
    as_of: "2026-11-12",
    month: "2026-11",
    safe_to_spend: {
      liquid_cash_minor: 10000000,
      card_liability_minor: 2000000,
      upcoming_obligations_minor: 1500000,
      goal_locks_minor: 500000,
      safe_to_spend_minor: 6000000,
      daily_safe_burn_minor: 400000,
      is_liquidity_deficit: false,
      deficit_minor: 0,
      days_remaining_in_month: 19,
    },
    net_worth_minor: 12345650,
    month_expense_minor: 250050,
    month_income_minor: 900000,
    upcoming_bills: [
      {
        id: "rule-1",
        merchant_id: "m-1",
        merchant_name: "Electricity Board",
        category_id: null,
        expected_amount_minor: 180000,
        frequency: "MONTHLY",
        next_expected_date: "2026-11-15",
        is_mandatory: true,
      },
    ],
    pending_review_count: 3,
    ...overrides,
  };
}

function renderHome() {
  return render(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>,
  );
}

describe("HomePage", () => {
  beforeEach(() => {
    getSummaryMock.mockReset();
  });

  it("shows the safe-to-spend amounts, breakdown legend and stat rows from the summary", async () => {
    getSummaryMock.mockResolvedValue(summaryFixture());

    renderHome();

    expect(await screen.findByText("₹60,000.00", { selector: ".amount" })).toBeTruthy();
    expect(screen.getByText("Safe to spend today: ₹4,000.00")).toBeTruthy();
    expect(screen.getByText("−₹20,000.00")).toBeTruthy();
    expect(screen.getByText("−₹15,000.00")).toBeTruthy();
    expect(screen.getByText("−₹5,000.00")).toBeTruthy();
    expect(screen.getByText("₹1,23,456.50")).toBeTruthy();
    expect(screen.getByText("₹2,500.50")).toBeTruthy();
    expect(screen.getByText("₹9,000.00")).toBeTruthy();
  });

  it("describes the breakdown bar as an image with a text summary", async () => {
    getSummaryMock.mockResolvedValue(summaryFixture());

    renderHome();

    const bar = await screen.findByRole("img", { name: /Breakdown of liquid cash ₹1,00,000\.00/ });
    expect(bar.getAttribute("aria-label")).toContain("card dues ₹20,000.00");
    expect(bar.getAttribute("aria-label")).toContain("remaining ₹60,000.00");
  });

  it("replaces the amount with a worded deficit state when commitments exceed cash", async () => {
    getSummaryMock.mockResolvedValue(
      summaryFixture({
        safe_to_spend: {
          liquid_cash_minor: 1000000,
          card_liability_minor: 1500000,
          upcoming_obligations_minor: 0,
          goal_locks_minor: 0,
          safe_to_spend_minor: 0,
          daily_safe_burn_minor: 0,
          is_liquidity_deficit: true,
          deficit_minor: 500000,
          days_remaining_in_month: 19,
        },
      }),
    );

    renderHome();

    expect(await screen.findByText("Short by ₹5,000.00")).toBeTruthy();
    expect(screen.queryByText(/Safe to spend today:/)).toBeNull();
    expect(screen.getByRole("img", { name: /Short by ₹5,000\.00/ })).toBeTruthy();
  });

  it("shows an empty bills state with a next step when no bills are due", async () => {
    getSummaryMock.mockResolvedValue(summaryFixture({ upcoming_bills: [] }));

    renderHome();

    const section = (await screen.findByRole("heading", { name: "Upcoming Bills" })).closest("section");
    expect(section).not.toBeNull();
    expect(within(section as HTMLElement).getByText(/No bills are due/)).toBeTruthy();
    expect(within(section as HTMLElement).getByRole("link", { name: "Open Transactions" })).toBeTruthy();
  });

  it("links the review row to transactions with the pending count", async () => {
    getSummaryMock.mockResolvedValue(summaryFixture({ pending_review_count: 3 }));

    renderHome();

    const review = await screen.findByRole("link", { name: /3 transactions to review/ });
    expect(review.getAttribute("href")).toBe("/transactions");
  });

  it("shows an error with a Try Again button that reloads the summary", async () => {
    getSummaryMock.mockRejectedValueOnce(new ApiError(0, "NETWORK_ERROR", "offline"));
    getSummaryMock.mockResolvedValueOnce(summaryFixture());
    renderHome();
    const user = userEvent.setup();

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Could not load your summary.");
    await user.click(within(alert).getByRole("button", { name: "Try Again" }));

    expect(await screen.findByText("₹60,000.00", { selector: ".amount" })).toBeTruthy();
    expect(getSummaryMock).toHaveBeenCalledTimes(2);
  });

  it("shows skeleton loading status before the summary arrives", () => {
    getSummaryMock.mockReturnValue(new Promise(() => undefined));

    renderHome();

    expect(screen.getByRole("status").textContent).toBe("Loading your summary");
  });
});
