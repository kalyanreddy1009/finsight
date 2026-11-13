import type { SelectOption } from "../../components/SelectField";

// Indian financial years start on 1 April. Month indexes are 0-based, so April is 3.
const APRIL_MONTH_INDEX = 3;
const FY_SELECT_COUNT = 3;
const YEAR_SUFFIX_MODULUS = 100;

// FY 2026 means April 2026 to March 2027.
export function fyForDate(date: Date): number {
  return date.getMonth() >= APRIL_MONTH_INDEX ? date.getFullYear() : date.getFullYear() - 1;
}

export function fyLabel(fy: number): string {
  const nextYear = String((fy + 1) % YEAR_SUFFIX_MODULUS).padStart(2, "0");
  return `FY ${fy}–${nextYear}`;
}

// The current financial year and the two before it.
export function fyOptions(currentFy: number): SelectOption[] {
  return Array.from({ length: FY_SELECT_COUNT }, (_, offset) => {
    const fy = currentFy - offset;
    return { value: String(fy), label: fyLabel(fy) };
  });
}
