import { request } from "./client";
import type { TaxSection } from "./types";

// Tax summary endpoint (/api/v1/tax/summary). FY 2026 means April 2026 to March 2027.

export interface TaxSummarySection {
  tax_section: TaxSection;
  total_minor: number;
  transaction_count: number;
  // Set only for sections with an old-regime limit (for example 80C).
  limit_minor: number | null;
}

export interface TaxSummary {
  fy: number;
  start_date: string;
  end_date: string;
  sections: TaxSummarySection[];
  total_minor: number;
}

// Omitting fy asks the backend for the current financial year.
export async function getTaxSummary(fy?: number): Promise<TaxSummary> {
  const query = fy === undefined ? "" : `?fy=${fy}`;
  const { data } = await request<TaxSummary>("GET", `/tax/summary${query}`);
  return data;
}
