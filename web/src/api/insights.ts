import { request } from "./client";
import type { InsightsSummary } from "./types";

export const DEFAULT_INSIGHT_MONTHS = 6;

export async function getInsightsSummary(months: number = DEFAULT_INSIGHT_MONTHS): Promise<InsightsSummary> {
  const { data } = await request<InsightsSummary>("GET", `/insights/summary?months=${months}`);
  return data;
}
