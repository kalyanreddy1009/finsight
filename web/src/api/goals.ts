import { request } from "./client";

// Goal endpoints (/api/v1/goals). Money is integer paise (*_minor).

export type GoalStatus = "ACTIVE" | "PAUSED" | "COMPLETED";

export interface Goal {
  id: string;
  name: string;
  linked_account_id: string | null;
  target_amount_minor: number;
  current_locked_amount_minor: number;
  monthly_contribution_minor: number;
  target_date: string | null;
  priority: number;
  status: GoalStatus;
  created_at: string;
}

// POST /goals body. Optional keys are omitted, never sent as null.
export interface GoalBody {
  name: string;
  target_amount_minor: number;
  current_locked_amount_minor?: number;
  monthly_contribution_minor?: number;
  target_date?: string;
  priority?: number;
}

// PATCH /goals/{id} body. target_date is sent as null to clear it.
export interface GoalPatch extends Partial<Omit<GoalBody, "target_date">> {
  target_date?: string | null;
  status?: GoalStatus;
}

export async function listGoals(): Promise<Goal[]> {
  const { data } = await request<Goal[]>("GET", "/goals");
  return data;
}

export async function createGoal(body: GoalBody): Promise<Goal> {
  const { data } = await request<Goal>("POST", "/goals", { body });
  return data;
}

export async function updateGoal(id: string, patch: GoalPatch): Promise<Goal> {
  const { data } = await request<Goal>("PATCH", `/goals/${id}`, { body: patch });
  return data;
}

export async function deleteGoal(id: string): Promise<void> {
  await request<unknown>("DELETE", `/goals/${id}`);
}
