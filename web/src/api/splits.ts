import { request } from "./client";
import type { Transaction } from "./types";

// Split endpoints (backend/app/api/v1/splits.py). Money is integer paise.

export type SplitStatus = "OPEN" | "PARTIAL" | "SETTLED" | "WRITTEN_OFF";

// GET /splits (items). outstanding_minor is owed minus settled.
export interface Split {
  id: string;
  transaction_id: string;
  counterparty_name: string;
  counterparty_vpa: string | null;
  owed_amount_minor: number;
  settled_amount_minor: number;
  outstanding_minor: number;
  status: SplitStatus;
  settlement_transaction_id: string | null;
  created_at: string;
  transaction_date: string;
  description: string | null;
}

// POST /splits/{id}/settle body
export interface SettleBody {
  bank_account_id: string;
  amount_minor: number;
  transaction_date?: string;
  description?: string;
}

export interface SettleResult {
  transaction: Transaction;
  split: Split;
}

export async function listSplits(status?: SplitStatus): Promise<Split[]> {
  const path = status === undefined ? "/splits" : `/splits?status=${status}`;
  const { data } = await request<Split[]>("GET", path);
  return data;
}

export async function settleSplit(splitId: string, body: SettleBody, idempotencyKey: string): Promise<SettleResult> {
  const path = `/splits/${encodeURIComponent(splitId)}/settle`;
  const { data } = await request<SettleResult>("POST", path, { body, idempotencyKey });
  return data;
}
