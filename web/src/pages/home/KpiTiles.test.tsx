import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { KpiTiles, savingsContext, spendPercentOfIncome, spendingContext } from "./KpiTiles";

describe("KPI tile helpers", () => {
  it("rounds spending as a percent of income half up, using whole paise", () => {
    expect(spendPercentOfIncome(250050, 900000)).toBe(28);
    expect(spendPercentOfIncome(1, 2)).toBe(50);
    expect(spendPercentOfIncome(2, 3)).toBe(67);
    expect(spendPercentOfIncome(0, 900000)).toBe(0);
    expect(spendPercentOfIncome(-45000, 900000)).toBe(0);
  });

  it("has no percent when no income is recorded", () => {
    expect(spendPercentOfIncome(250050, 0)).toBeNull();
    expect(spendingContext(250050, 0)).toBe("No income recorded this month yet");
  });

  it("says saved or overspent by the difference between income and spending", () => {
    expect(savingsContext(250050, 900000)).toBe("Saved ₹6,499.50");
    expect(savingsContext(900000, 250050)).toBe("Overspent ₹6,499.50");
    expect(savingsContext(500000, 500000)).toBe("Saved ₹0.00");
  });
});

describe("KpiTiles", () => {
  it("renders three labelled tiles with amounts and the context lines", () => {
    const { container } = render(<KpiTiles netWorthMinor={12345650} monthExpenseMinor={250050} monthIncomeMinor={900000} />);

    expect(container.querySelectorAll("dl.kpi-grid > .kpi-tile")).toHaveLength(3);
    expect(screen.getByText("Net Worth")).toBeTruthy();
    expect(screen.getByText("₹1,23,456.50")).toBeTruthy();
    expect(screen.getByText("This Month's Spending")).toBeTruthy();
    expect(screen.getByText("₹2,500.50")).toBeTruthy();
    expect(screen.getByText("28% of this month's income")).toBeTruthy();
    expect(screen.getByText("This Month's Income")).toBeTruthy();
    expect(screen.getByText("₹9,000.00")).toBeTruthy();
    expect(screen.getByText("Saved ₹6,499.50")).toBeTruthy();
  });

  it("shows no context line under net worth", () => {
    const { container } = render(<KpiTiles netWorthMinor={100} monthExpenseMinor={0} monthIncomeMinor={0} />);

    const netWorthTile = container.querySelector(".kpi-tile") as HTMLElement;
    expect(netWorthTile.querySelectorAll(".kpi-context")).toHaveLength(0);
  });
});
