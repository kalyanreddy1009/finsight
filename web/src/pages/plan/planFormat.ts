import { ApiError } from "../../api/client";
import type { RecurringFrequency } from "../../api/recurring";
import type { SelectOption } from "../../components/SelectField";
import { isIsoDate } from "../accounts/format";

const DUE_DATE_FORMAT = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" });
const MONTH_FORMAT = new Intl.DateTimeFormat("en-IN", { month: "long", year: "numeric" });
const NEAR_LIMIT_WORDS = "Near limit";
const OVER_LIMIT_WORDS = "Over limit";
const PERCENT_MAX = 100;

export const FREQUENCY_OPTIONS: readonly SelectOption[] = [
  { value: "WEEKLY", label: "Weekly" },
  { value: "MONTHLY", label: "Monthly" },
  { value: "QUARTERLY", label: "Quarterly" },
  { value: "YEARLY", label: "Yearly" },
];

export function frequencyLabel(frequency: RecurringFrequency): string {
  return FREQUENCY_OPTIONS.find((option) => option.value === frequency)?.label ?? frequency;
}

// "2026-12-05" becomes "5 Dec 2026". The string is split, never parsed, so no timezone shift.
export function formatPlanDate(iso: string): string {
  if (!isIsoDate(iso)) {
    return iso;
  }
  const [year = 0, month = 1, day = 1] = iso.split("-").map(Number);
  return DUE_DATE_FORMAT.format(new Date(year, month - 1, day));
}

function parseMonthKey(key: string): [number, number] {
  const [year = 0, month = 1] = key.split("-").map(Number);
  return [year, month];
}

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

// Local calendar month of a date, as YYYY-MM (the path key the budget API uses).
export function monthKeyOf(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}`;
}

export function shiftMonth(key: string, delta: number): string {
  const [year, month] = parseMonthKey(key);
  const index = year * 12 + (month - 1) + delta;
  const nextYear = Math.floor(index / 12);
  return `${nextYear}-${pad2(index - nextYear * 12 + 1)}`;
}

export function monthLabel(key: string): string {
  const [year, month] = parseMonthKey(key);
  return MONTH_FORMAT.format(new Date(year, month - 1, 1));
}

// Share of a limit used, capped at 100 for the bar. This is a percentage, never money.
export function usedPercent(spent: number, limit: number): number {
  if (limit <= 0) {
    return spent > 0 ? PERCENT_MAX : 0;
  }
  return Math.min(PERCENT_MAX, Math.round((spent * PERCENT_MAX) / limit));
}

export type LimitStatus = "over" | "near" | "ok";

// Integer comparisons only. A null threshold means no near-limit warning.
export function limitStatusFor(spent: number, limit: number, alertThresholdPct: number | null): LimitStatus {
  if (spent > limit) {
    return "over";
  }
  if (alertThresholdPct !== null && spent * PERCENT_MAX >= limit * alertThresholdPct) {
    return "near";
  }
  return "ok";
}

// The words shown next to a limit. Status is never carried by color alone.
export function statusWordsFor(status: LimitStatus): string | null {
  if (status === "over") {
    return OVER_LIMIT_WORDS;
  }
  return status === "near" ? NEAR_LIMIT_WORDS : null;
}

// Shows the API message for an ApiError; anything else gets the screen's own fallback.
export function errorText(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}
