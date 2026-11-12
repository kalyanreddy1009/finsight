import type { ReviewStatus, TaxSection, Transaction } from "../../api/types";
import { formatMinor } from "../../lib/money";

export const TAX_SECTIONS: readonly TaxSection[] = ["NONE", "80C", "80D", "80CCD", "HRA", "24B", "LTCG", "STCG"];

export function parseTaxSection(value: string): TaxSection | null {
  return TAX_SECTIONS.find((section) => section === value) ?? null;
}

export function taxSectionLabel(section: TaxSection): string {
  return section === "NONE" ? "None" : section;
}

// `direction` is from the account's statement point of view: DEBIT = money out of the account
// (expenses, transfers out), CREDIT = money into it (income, refunds, repayments).
export function isMoneyIn(transaction: Transaction): boolean {
  return transaction.direction === "CREDIT";
}

export function signedAmountText(transaction: Transaction): string {
  return isMoneyIn(transaction)
    ? formatMinor(transaction.amount_minor, { sign: true })
    : formatMinor(-transaction.amount_minor);
}

export function displayTitle(transaction: Transaction): string {
  return transaction.clean_description || transaction.description || "Untitled transaction";
}

const STATUS_LABELS: Record<ReviewStatus, string> = {
  PROVISIONAL: "Provisional",
  PENDING_REVIEW: "Needs Review",
  AUTO_APPROVED: "Approved",
  USER_APPROVED: "Approved",
  SUPERSEDED: "Reversed",
};

export function statusLabel(status: ReviewStatus): string {
  return STATUS_LABELS[status];
}

// Text badges shown on a row. Status never relies on color alone.
export function badgesFor(transaction: Transaction): string[] {
  switch (transaction.review_status) {
    case "SUPERSEDED":
      return ["Reversed"];
    case "PROVISIONAL":
      return ["Provisional"];
    case "PENDING_REVIEW":
      return ["Needs Review"];
    default:
      return [];
  }
}

// A split expense is one where the user's share differs from the full amount.
export function isSplitExpense(transaction: Transaction): boolean {
  return transaction.transaction_type === "EXPENSE" && transaction.user_share_minor !== transaction.amount_minor;
}

export function yourShareText(transaction: Transaction): string | null {
  return isSplitExpense(transaction) ? `Your share ${formatMinor(transaction.user_share_minor)}` : null;
}
