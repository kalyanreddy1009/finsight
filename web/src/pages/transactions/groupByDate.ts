import type { Transaction } from "../../api/types";

export interface DateGroup {
  date: string;
  label: string;
  items: Transaction[];
}

const HEADING_FORMAT = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

// "2026-11-12" to "12 November 2026". Parsed as UTC so the day never shifts.
export function formatDateHeading(isoDate: string): string {
  const [year = 1970, month = 1, day = 1] = isoDate.split("-").map(Number);
  return HEADING_FORMAT.format(new Date(Date.UTC(year, month - 1, day)));
}

// Keeps the order the API returns; rows for one date stay together under one heading.
export function groupByDate(items: Transaction[]): DateGroup[] {
  const byDate = new Map<string, Transaction[]>();
  for (const item of items) {
    byDate.set(item.transaction_date, [...(byDate.get(item.transaction_date) ?? []), item]);
  }
  return Array.from(byDate, ([date, rows]) => ({ date, label: formatDateHeading(date), items: rows }));
}
