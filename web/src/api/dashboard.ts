import { request } from "./client";
import type { DashboardSummary } from "./types";

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const { data } = await request<DashboardSummary>("GET", "/dashboard/summary");
  return data;
}
