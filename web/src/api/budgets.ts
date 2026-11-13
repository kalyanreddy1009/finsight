import { request } from "./client";

// Budget endpoints (/api/v1/budgets/{YYYY-MM}). Money is integer paise (*_minor).

export interface BudgetCategory {
  category_id: string;
  category_name: string;
  limit_minor: number;
  // Always an integer percentage (default 80).
  alert_threshold_pct: number;
  spent_minor: number;
}

export interface Budget {
  id: string;
  name: string;
  period_month: string;
  total_limit_minor: number;
  spent_minor: number;
  categories: BudgetCategory[];
}

export interface BudgetResponse {
  month: string;
  budget: Budget | null;
}

export interface BudgetCategoryBody {
  category_id: string;
  limit_minor: number;
  alert_threshold_pct?: number;
}

// PUT /budgets/{YYYY-MM} body. Blank category limits are left out, never sent as null.
export interface BudgetBody {
  name?: string;
  total_limit_minor: number;
  categories: BudgetCategoryBody[];
}

export async function getBudget(month: string): Promise<BudgetResponse> {
  const { data } = await request<BudgetResponse>("GET", `/budgets/${month}`);
  return data;
}

export async function saveBudget(month: string, body: BudgetBody): Promise<BudgetResponse> {
  const { data } = await request<BudgetResponse>("PUT", `/budgets/${month}`, { body });
  return data;
}

export async function deleteBudget(month: string): Promise<void> {
  await request<{ deleted: boolean }>("DELETE", `/budgets/${month}`);
}
