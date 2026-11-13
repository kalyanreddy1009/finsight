import { describe, expect, it } from "vitest";
import { fyForDate, fyLabel, fyOptions } from "./taxForm";
import {
  formatPlanDate,
  frequencyLabel,
  limitStatusFor,
  monthKeyOf,
  monthLabel,
  shiftMonth,
  statusWordsFor,
  usedPercent,
} from "./planFormat";

describe("financial year from a date", () => {
  it("keeps 31 March in the year that started the previous April", () => {
    expect(fyForDate(new Date(2026, 2, 31))).toBe(2025);
  });

  it("starts a new financial year on 1 April", () => {
    expect(fyForDate(new Date(2026, 3, 1))).toBe(2026);
  });

  it("labels a financial year with a two digit end year", () => {
    expect(fyLabel(2026)).toBe("FY 2026–27");
    expect(fyLabel(2099)).toBe("FY 2099–00");
  });

  it("offers the current year and the two before it", () => {
    expect(fyOptions(2026).map((option) => option.value)).toEqual(["2026", "2025", "2024"]);
  });
});

describe("month keys", () => {
  it("uses the local calendar month as YYYY-MM", () => {
    expect(monthKeyOf(new Date(2026, 10, 13))).toBe("2026-11");
  });

  it("moves across year boundaries in both directions", () => {
    expect(shiftMonth("2026-12", 1)).toBe("2027-01");
    expect(shiftMonth("2027-01", -1)).toBe("2026-12");
  });

  it("names the month in en-IN style", () => {
    expect(monthLabel("2026-12")).toBe("December 2026");
  });
});

describe("dates and labels", () => {
  it("formats a due date without a timezone shift", () => {
    expect(formatPlanDate("2026-12-05")).toBe("5 Dec 2026");
  });

  it("returns a malformed date unchanged", () => {
    expect(formatPlanDate("5/12/2026")).toBe("5/12/2026");
  });

  it("names the frequency in words", () => {
    expect(frequencyLabel("MONTHLY")).toBe("Monthly");
    expect(frequencyLabel("QUARTERLY")).toBe("Quarterly");
  });
});

describe("limit status", () => {
  it("reports near limit at or above the alert threshold", () => {
    expect(limitStatusFor(80, 100, 80)).toBe("near");
    expect(limitStatusFor(79, 100, 80)).toBe("ok");
  });

  it("reports over limit above the limit, even without a threshold", () => {
    expect(limitStatusFor(101, 100, null)).toBe("over");
    expect(limitStatusFor(100, 100, null)).toBe("ok");
  });

  it("gives words for near and over, and none when ok", () => {
    expect(statusWordsFor("near")).toBe("Near limit");
    expect(statusWordsFor("over")).toBe("Over limit");
    expect(statusWordsFor("ok")).toBeNull();
  });
});

describe("progress percent", () => {
  it("rounds the share used and caps the bar at 100", () => {
    expect(usedPercent(4200000, 5000000)).toBe(84);
    expect(usedPercent(7000000, 5000000)).toBe(100);
  });

  it("handles a zero limit without dividing", () => {
    expect(usedPercent(0, 0)).toBe(0);
    expect(usedPercent(100, 0)).toBe(100);
  });
});
