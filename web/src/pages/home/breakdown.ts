import type { SafeToSpend } from "../../api/types";
import { formatMinor } from "../../lib/money";

export type BreakdownKey = "cards" | "bills" | "goals" | "remaining";

export interface BreakdownSegment {
  key: BreakdownKey;
  label: string;
  amountMinor: number;
  widthPercent: number;
}

// Segments are proportional to liquid cash. When commitments exceed cash (a deficit),
// the bar scales to the commitments instead, so it never overflows.
export function buildBreakdown(safe: SafeToSpend): BreakdownSegment[] {
  const parts: { key: BreakdownKey; label: string; amountMinor: number }[] = [
    { key: "cards", label: "Card dues", amountMinor: safe.card_liability_minor },
    { key: "bills", label: "Upcoming bills", amountMinor: safe.upcoming_obligations_minor },
    { key: "goals", label: "Goal locks", amountMinor: safe.goal_locks_minor },
    { key: "remaining", label: "Remaining", amountMinor: safe.safe_to_spend_minor },
  ];
  const committed = parts.reduce((sum, part) => sum + part.amountMinor, 0);
  const total = Math.max(safe.liquid_cash_minor, committed);
  return parts.map((part) => ({
    ...part,
    widthPercent: total > 0 ? (part.amountMinor / total) * 100 : 0,
  }));
}

// The text alternative for the bar. It is the only description screen readers get.
export function describeBreakdown(safe: SafeToSpend): string {
  const parts = [
    `liquid cash ${formatMinor(safe.liquid_cash_minor)}`,
    `card dues ${formatMinor(safe.card_liability_minor)}`,
    `upcoming bills ${formatMinor(safe.upcoming_obligations_minor)}`,
    `goal locks ${formatMinor(safe.goal_locks_minor)}`,
    `remaining ${formatMinor(safe.safe_to_spend_minor)}`,
  ];
  const deficit = safe.is_liquidity_deficit ? ` Short by ${formatMinor(safe.deficit_minor)}.` : "";
  return `Breakdown of ${parts.join(", ")}.${deficit}`;
}
