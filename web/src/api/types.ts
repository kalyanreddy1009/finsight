// Field names mirror the backend responses exactly (backend/app/api/v1 and backend/app/finance/queries.py).

export type ApiMeta = Record<string, unknown> | null;

export interface ApiErrorBody {
  code: string;
  message: string;
}

export interface ApiEnvelope<T> {
  data: T | null;
  error: ApiErrorBody | null;
  meta: ApiMeta;
}

// POST /auth/setup, /auth/login, /auth/refresh
export interface SessionData {
  access_token: string;
  token_type: "Bearer";
  expires_in: number;
  device_id: string;
}

// GET /auth/status
export interface AuthStatusData {
  configured: boolean;
}

export type AccountClass = "ASSET" | "LIABILITY";

export type UserAccountSubtype =
  | "BANK_SAVINGS"
  | "BANK_CURRENT"
  | "CREDIT_CARD"
  | "CASH"
  | "WALLET"
  | "INVESTMENT_DEMAT"
  | "INVESTMENT_MF"
  | "FIXED_DEPOSIT"
  | "PF_EPF_PPF"
  | "PHYSICAL_ASSET"
  | "LOAN_HOME"
  | "LOAN_VEHICLE"
  | "LOAN_PERSONAL";

export type TaxSection = "NONE" | "80C" | "80D" | "80CCD" | "HRA" | "24B" | "LTCG" | "STCG";

export type ReviewStatus = "PROVISIONAL" | "PENDING_REVIEW" | "AUTO_APPROVED" | "USER_APPROVED" | "SUPERSEDED";

// GET /accounts (items)
export interface Account {
  id: string;
  name: string;
  account_class: AccountClass;
  account_subtype: UserAccountSubtype;
  institution: string | null;
  currency: string;
  opening_balance_minor: number | null;
  current_balance_minor: number;
  credit_limit_minor: number | null;
  billing_day: number | null;
  due_day: number | null;
  is_liquid: boolean;
  is_active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

// GET /categories (items)
export interface Category {
  id: string;
  name: string;
  parent_category_id: string | null;
  category_type: "EXPENSE" | "INCOME";
  default_tax_section: TaxSection;
  is_discretionary: boolean;
  is_sensitive_private: boolean;
  is_system_category: boolean;
  created_at: string;
}

// GET /transactions (items) and GET /transactions/{id}
export interface Transaction {
  id: string;
  journal_entry_id: string;
  entry_type: string;
  account_id: string;
  account_name: string;
  counterparty_account_id: string;
  counterparty_account_name: string;
  category_id: string | null;
  category_name: string | null;
  transaction_date: string;
  description: string | null;
  clean_description: string | null;
  amount_minor: number;
  user_share_minor: number;
  direction: string;
  transaction_type: string;
  linked_transaction_id: string | null;
  tax_section: TaxSection;
  is_verified: boolean;
  review_status: ReviewStatus;
  notes: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

// GET /dashboard/summary: safe_to_spend block
export interface SafeToSpend {
  liquid_cash_minor: number;
  card_liability_minor: number;
  upcoming_obligations_minor: number;
  goal_locks_minor: number;
  safe_to_spend_minor: number;
  daily_safe_burn_minor: number;
  is_liquidity_deficit: boolean;
  deficit_minor: number;
  days_remaining_in_month: number;
}

// GET /dashboard/summary: upcoming_bills items
export interface UpcomingBill {
  id: string;
  merchant_id: string;
  merchant_name: string;
  category_id: string | null;
  expected_amount_minor: number;
  frequency: string;
  next_expected_date: string;
  is_mandatory: boolean;
}

// GET /dashboard/summary
export interface DashboardSummary {
  as_of: string;
  month: string;
  safe_to_spend: SafeToSpend;
  net_worth_minor: number;
  month_expense_minor: number;
  month_income_minor: number;
  upcoming_bills: UpcomingBill[];
  pending_review_count: number;
}
