import { request } from "./client";
import type { Account, TaxSection, Transaction } from "./types";

export interface TransactionListParams {
  q?: string;
  accountId?: string;
  categoryId?: string;
  needsReview?: boolean;
  cursor?: string;
  limit?: number;
}

export interface TransactionPage {
  items: Transaction[];
  nextCursor: string | null;
}

export interface SplitShareBody {
  counterparty_name: string;
  owed_amount_minor: number;
}

interface TransactionBodyBase {
  amount_minor: number;
  transaction_date: string;
  description?: string;
}

// POST /transactions bodies. The backend forbids unknown keys, so only these fields are sent.
export interface ExpenseBody extends TransactionBodyBase {
  kind: "expense";
  account_id: string;
  category_id: string;
  splits: SplitShareBody[];
}

export interface IncomeBody extends TransactionBodyBase {
  kind: "income";
  account_id: string;
  category_id: string;
}

export interface TransferBody extends TransactionBodyBase {
  kind: "transfer";
  from_account_id: string;
  to_account_id: string;
}

export type NewTransactionBody = ExpenseBody | IncomeBody | TransferBody;

// PATCH /transactions/{id} accepts these fields only. null is rejected for category_id and tax_section.
export interface TransactionPatch {
  notes?: string;
  tax_section?: TaxSection;
  category_id?: string;
}

function listPath(params: TransactionListParams): string {
  const query = new URLSearchParams();
  if (params.q) {
    query.set("q", params.q);
  }
  if (params.accountId) {
    query.set("account_id", params.accountId);
  }
  if (params.categoryId) {
    query.set("category_id", params.categoryId);
  }
  if (params.needsReview) {
    query.set("review_status", "PENDING_REVIEW");
  }
  if (params.cursor) {
    query.set("cursor", params.cursor);
  }
  if (params.limit !== undefined) {
    query.set("limit", String(params.limit));
  }
  const text = query.toString();
  return text === "" ? "/transactions" : `/transactions?${text}`;
}

export async function listTransactions(params: TransactionListParams = {}): Promise<TransactionPage> {
  const { data, meta } = await request<Transaction[]>("GET", listPath(params));
  const cursor = meta?.next_cursor;
  return { items: data, nextCursor: typeof cursor === "string" ? cursor : null };
}

export async function getTransaction(id: string): Promise<Transaction> {
  const { data } = await request<Transaction>("GET", `/transactions/${encodeURIComponent(id)}`);
  return data;
}

export async function createTransaction(body: NewTransactionBody): Promise<Transaction> {
  const { data } = await request<Transaction>("POST", "/transactions", { body, idempotent: true });
  return data;
}

export async function patchTransaction(id: string, version: number, patch: TransactionPatch): Promise<Transaction> {
  const { data } = await request<Transaction>("PATCH", `/transactions/${encodeURIComponent(id)}`, {
    body: patch,
    headers: { "If-Match": String(version) },
  });
  return data;
}

export async function reverseTransaction(id: string): Promise<Transaction> {
  const { data } = await request<Transaction>("POST", `/transactions/${encodeURIComponent(id)}/reverse`, {
    idempotent: true,
  });
  return data;
}

// Accounts for the pickers. The Accounts tab owns api/accounts.ts; this is a read-only call.
export async function listAccountsForPicker(): Promise<Account[]> {
  const { data } = await request<Account[]>("GET", "/accounts");
  return data;
}
