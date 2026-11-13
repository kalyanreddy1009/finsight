import { request } from "./client";

// Recurring bill endpoints (/api/v1/recurring). Money is integer paise (*_minor).

export type RecurringFrequency = "WEEKLY" | "MONTHLY" | "QUARTERLY" | "YEARLY";

export interface RecurringRule {
  id: string;
  merchant_id: string;
  merchant_name: string;
  category_id: string;
  category_name: string;
  account_id: string | null;
  expected_amount_minor: number;
  frequency: RecurringFrequency;
  next_expected_date: string;
  is_mandatory: boolean;
  is_active: boolean;
}

// POST /recurring body. account_id is omitted when not chosen.
export interface RecurringBody {
  merchant_name: string;
  category_id: string;
  account_id?: string;
  expected_amount_minor: number;
  frequency: RecurringFrequency;
  next_expected_date: string;
  is_mandatory: boolean;
}

export interface RecurringPatch {
  expected_amount_minor?: number;
  frequency?: RecurringFrequency;
  next_expected_date?: string;
  is_mandatory?: boolean;
  is_active?: boolean;
  category_id?: string;
}

export async function listRecurring(): Promise<RecurringRule[]> {
  const { data } = await request<RecurringRule[]>("GET", "/recurring");
  return data;
}

export async function createRecurring(body: RecurringBody): Promise<RecurringRule> {
  const { data } = await request<RecurringRule>("POST", "/recurring", { body });
  return data;
}

export async function updateRecurring(id: string, patch: RecurringPatch): Promise<RecurringRule> {
  const { data } = await request<RecurringRule>("PATCH", `/recurring/${id}`, { body: patch });
  return data;
}

// Moves the next expected date one period forward and returns the updated rule.
export async function advanceRecurring(id: string): Promise<RecurringRule> {
  const { data } = await request<RecurringRule>("POST", `/recurring/${id}/advance`);
  return data;
}

export async function deleteRecurring(id: string): Promise<void> {
  await request<unknown>("DELETE", `/recurring/${id}`);
}
