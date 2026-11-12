import type { NewTransactionBody, SplitShareBody } from "../../api/transactions";
import { formatMinor, parseRupeesToMinor } from "../../lib/money";

export type EntryKind = "expense" | "income" | "transfer";

export interface SplitRowDraft {
  id: string;
  name: string;
  owed: string;
}

export interface EntryDraft {
  kind: EntryKind;
  amount: string;
  date: string;
  accountId: string;
  toAccountId: string;
  categoryId: string;
  description: string;
  splits: SplitRowDraft[];
}

export type EntryField = "amount" | "date" | "accountId" | "toAccountId" | "categoryId" | "splits";
export type EntryErrors = Partial<Record<EntryField, string>>;

export interface ValidationResult {
  errors: EntryErrors;
  body: NewTransactionBody | null;
}

export const KIND_LABELS: Record<EntryKind, string> = {
  expense: "Expense",
  income: "Income",
  transfer: "Transfer",
};

export const AMOUNT_ERROR = "Enter the amount in rupees, for example 450 or 1,250.50.";
const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

export function toIsoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

export function emptyDraft(today: string): EntryDraft {
  return {
    kind: "expense",
    amount: "",
    date: today,
    accountId: "",
    toAccountId: "",
    categoryId: "",
    description: "",
    splits: [],
  };
}

export function newSplitRow(): SplitRowDraft {
  return { id: crypto.randomUUID(), name: "", owed: "" };
}

// Rupee text to positive paise, or null when the text is not a positive amount.
function parsePositive(text: string): number | null {
  const minor = parseRupeesToMinor(text);
  return minor === null || minor <= 0 ? null : minor;
}

// A split row counts once it has a name or an amount. Empty rows are ignored.
export function activeSplits(rows: SplitRowDraft[]): SplitRowDraft[] {
  return rows.filter((row) => row.name.trim() !== "" || row.owed.trim() !== "");
}

export function owedTotalMinor(rows: SplitRowDraft[]): number {
  return activeSplits(rows).reduce((sum, row) => sum + (parsePositive(row.owed) ?? 0), 0);
}

export function yourShareMinor(totalMinor: number, rows: SplitRowDraft[]): number {
  return totalMinor - owedTotalMinor(rows);
}

function splitProblem(rows: SplitRowDraft[], totalMinor: number): string | null {
  const inUse = activeSplits(rows);
  if (inUse.some((row) => row.name.trim() === "")) {
    return "Enter a name for each person you split with.";
  }
  if (inUse.some((row) => parsePositive(row.owed) === null)) {
    return "Enter what each person owes, in rupees.";
  }
  const over = owedTotalMinor(inUse) - totalMinor;
  return over > 0 ? `Friends' shares add up to more than the total. Reduce them by ${formatMinor(over)}.` : null;
}

function checkTransferAccounts(draft: EntryDraft, errors: EntryErrors): void {
  if (draft.accountId === "") {
    errors.accountId = "Choose the account the money leaves.";
  }
  if (draft.toAccountId === "") {
    errors.toAccountId = "Choose the account the money goes to.";
  } else if (draft.toAccountId === draft.accountId) {
    errors.toAccountId = "Choose two different accounts.";
  }
}

function descriptionPart(text: string): { description?: string } {
  const trimmed = text.trim();
  return trimmed === "" ? {} : { description: trimmed };
}

function splitBodies(rows: SplitRowDraft[]): SplitShareBody[] {
  return activeSplits(rows).map((row) => ({
    counterparty_name: row.name.trim(),
    owed_amount_minor: parsePositive(row.owed) ?? 0,
  }));
}

function buildBody(draft: EntryDraft, amountMinor: number): NewTransactionBody {
  const common = {
    amount_minor: amountMinor,
    transaction_date: draft.date,
    ...descriptionPart(draft.description),
  };
  if (draft.kind === "transfer") {
    return { ...common, kind: "transfer", from_account_id: draft.accountId, to_account_id: draft.toAccountId };
  }
  if (draft.kind === "income") {
    return { ...common, kind: "income", account_id: draft.accountId, category_id: draft.categoryId };
  }
  return {
    ...common,
    kind: "expense",
    account_id: draft.accountId,
    category_id: draft.categoryId,
    splits: splitBodies(draft.splits),
  };
}

export function validateDraft(draft: EntryDraft): ValidationResult {
  const errors: EntryErrors = {};
  const amountMinor = parsePositive(draft.amount);
  if (amountMinor === null) {
    errors.amount = AMOUNT_ERROR;
  }
  if (!ISO_DATE_PATTERN.test(draft.date)) {
    errors.date = "Choose a date.";
  }
  if (draft.kind === "transfer") {
    checkTransferAccounts(draft, errors);
  } else {
    if (draft.accountId === "") {
      errors.accountId = "Choose an account.";
    }
    if (draft.categoryId === "") {
      errors.categoryId = "Choose a category.";
    }
  }
  if (draft.kind === "expense" && amountMinor !== null) {
    const problem = splitProblem(draft.splits, amountMinor);
    if (problem !== null) {
      errors.splits = problem;
    }
  }
  if (amountMinor === null || Object.keys(errors).length > 0) {
    return { errors, body: null };
  }
  return { errors, body: buildBody(draft, amountMinor) };
}
