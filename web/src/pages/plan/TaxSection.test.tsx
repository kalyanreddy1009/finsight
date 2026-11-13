import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getTaxSummary, type TaxSummary } from "../../api/tax";
import { TaxSection } from "./TaxSection";

vi.mock("../../api/tax", () => ({ getTaxSummary: vi.fn() }));

const summary: TaxSummary = {
  fy: 2026,
  start_date: "2026-04-01",
  end_date: "2027-03-31",
  total_minor: 4000000,
  sections: [
    { tax_section: "80C", total_minor: 1500000, transaction_count: 3, limit_minor: 1500000 },
    { tax_section: "80D", total_minor: 2500000, transaction_count: 1, limit_minor: null },
    { tax_section: "NONE", total_minor: 0, transaction_count: 0, limit_minor: null },
  ],
};

beforeEach(() => {
  vi.resetAllMocks();
  // 13 November 2026 is in FY 2026. Only Date is faked, so user events still run on real timers.
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 10, 13));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("TaxSection", () => {
  it("lists tagged sections with totals, counts and the old regime limit", async () => {
    vi.mocked(getTaxSummary).mockResolvedValue(summary);
    render(<TaxSection />);

    expect(await screen.findByText("80C")).toBeTruthy();
    expect(screen.getByText(/3 transactions · of ₹15,000.00 limit \(old regime\)/)).toBeTruthy();
    expect(screen.getByText("₹15,000.00")).toBeTruthy();
    expect(screen.getByText(/1 transaction$/)).toBeTruthy();
    expect(screen.queryByText("None")).toBeNull();
    expect(getTaxSummary).toHaveBeenCalledWith(2026);
  });

  it("explains the empty state when nothing is tagged", async () => {
    vi.mocked(getTaxSummary).mockResolvedValue({ ...summary, sections: [], total_minor: 0 });
    render(<TaxSection />);

    expect(await screen.findByText("No tax-tagged transactions in this year. Set a tax section on a transaction to see it here.")).toBeTruthy();
  });

  it("shows an error with a retry", async () => {
    const user = userEvent.setup();
    vi.mocked(getTaxSummary).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(summary);
    render(<TaxSection />);

    expect(await screen.findByText("Could not load your tax summary. Check your connection and try again.")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Try Again" }));
    expect(await screen.findByText("80C")).toBeTruthy();
  });

  it("refetches with the chosen financial year when the selector changes", async () => {
    const user = userEvent.setup();
    vi.mocked(getTaxSummary).mockResolvedValue(summary);
    render(<TaxSection />);
    await screen.findByText("80C");

    const selector = screen.getByLabelText("Financial year");
    expect(screen.getByRole("option", { name: "FY 2026–27" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "FY 2024–25" })).toBeTruthy();
    await user.selectOptions(selector, "2025");

    expect(getTaxSummary).toHaveBeenLastCalledWith(2025);
  });
});
