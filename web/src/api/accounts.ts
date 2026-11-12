import { request } from "./client";
import type { Account, UserAccountSubtype } from "./types";

// Account endpoints (backend/app/api/v1/accounts.py). Money is integer paise.

// POST /accounts body. Optional keys are omitted, never sent as null.
export interface AccountCreateBody {
  name: string;
  account_subtype: UserAccountSubtype;
  institution?: string;
  credit_limit_minor?: number;
  billing_day?: number;
  due_day?: number;
  opening_balance_minor?: number;
  opening_date?: string;
}

export async function listAccounts(): Promise<Account[]> {
  const { data } = await request<Account[]>("GET", "/accounts");
  return data;
}

export async function createAccount(body: AccountCreateBody): Promise<Account> {
  const { data } = await request<Account>("POST", "/accounts", { body });
  return data;
}
