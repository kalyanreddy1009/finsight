import type { CategoryInsight, InsightsSummary, TrendPoint } from "../../api/types";
import { formatMinor } from "../../lib/money";

export const TOP_CATEGORY_COUNT = 6;
const BP_PER_PERCENT = 100;
const PERCENT_SCALE = 100;
const MONTH_FORMAT = new Intl.DateTimeFormat("en-IN", { month: "short", timeZone: "UTC" });

export const NO_HIGHLIGHTS_MESSAGE = "Nothing stands out yet. Highlights appear once there is a month of spending to look at.";

// Largest spend first. The server order is not relied on.
export function topCategories(categories: readonly CategoryInsight[], limit: number = TOP_CATEGORY_COUNT): CategoryInsight[] {
  return [...categories].sort((a, b) => b.spent_minor - a.spent_minor).slice(0, limit);
}

// 3600 bp -> "36%", 1250 bp -> "12.5%".
export function percentText(shareBp: number): string {
  return `${Number((shareBp / BP_PER_PERCENT).toFixed(1))}%`;
}

export function categoryTakeaway(categories: readonly CategoryInsight[]): string {
  const [largest] = topCategories(categories, 1);
  if (largest === undefined || largest.spent_minor <= 0) {
    return "No spending has been recorded this month yet.";
  }
  return `${largest.name} is your largest category this month.`;
}

export function trendTakeaway(summary: Pick<InsightsSummary, "expense_minor" | "previous_expense_minor">): string {
  const { expense_minor: current, previous_expense_minor: previous } = summary;
  if (previous <= 0) {
    return "There is no spending from last month to compare with yet.";
  }
  const amounts = `${formatMinor(current)} against ${formatMinor(previous)}`;
  if (current === previous) {
    return `Spending so far this month matches last month (${amounts}).`;
  }
  // Integer maths on paise, rounding half up, so the percent never depends on float error.
  const percent = Math.floor((Math.abs(current - previous) * PERCENT_SCALE + Math.floor(previous / 2)) / previous);
  const direction = current < previous ? "lower" : "higher";
  return `Spending so far this month is ${percent}% ${direction} than last month (${amounts}).`;
}

// "2026-06" -> "Jun".
export function shortMonth(yearMonth: string): string {
  const [year, month] = yearMonth.split("-").map(Number);
  if (year === undefined || month === undefined || Number.isNaN(year) || Number.isNaN(month)) {
    return yearMonth;
  }
  return MONTH_FORMAT.format(new Date(Date.UTC(year, month - 1, 1)));
}

export function describeTrend(trend: readonly TrendPoint[]): string {
  const parts = trend.map(
    (point) => `${shortMonth(point.year_month)} income ${formatMinor(point.income_minor)}, spending ${formatMinor(point.expense_minor)}`,
  );
  return `Income and spending for the last ${trend.length} months. ${parts.join("; ")}.`;
}
