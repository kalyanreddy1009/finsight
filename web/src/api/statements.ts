import { request } from "./client";

// Statement endpoints (backend/app/api/v1/statements.py) and GET /categories.
// Money is integer paise.

export type StatementKind = "BANK_PDF" | "CARD_PDF" | "CSV" | "CAS_PDF";
export type StatementProcessingStatus = "UPLOADED" | "PARSING" | "REVIEW_REQUIRED" | "APPROVED" | "FAILED";
export type StatementRowStatus =
  | "PENDING_REVIEW"
  | "AUTO_APPROVED"
  | "USER_APPROVED"
  | "REJECTED"
  | "DUPLICATE"
  | "COMMITTED";
export type ReviewableRowStatus = "USER_APPROVED" | "REJECTED" | "PENDING_REVIEW";

// GET /statements (items) and the statement block of GET /statements/{id}/review
export interface Statement {
  id: string;
  account_id: string;
  statement_kind: StatementKind;
  original_filename: string;
  statement_start_date: string;
  statement_end_date: string;
  opening_balance_minor: number;
  closing_balance_minor: number;
  reconciliation_diff_minor: number | null;
  processing_status: StatementProcessingStatus;
  uploaded_at: string;
  approved_at: string | null;
}

// statement_rows (the fields the review screen reads)
export interface StatementRow {
  id: string;
  statement_id: string;
  row_index: number;
  page_number: number;
  tx_date: string;
  raw_description: string;
  clean_description: string;
  direction: "DEBIT" | "CREDIT";
  amount_minor: number;
  stated_balance_minor: number | null;
  suggested_category_id: string | null;
  row_status: StatementRowStatus;
  duplicate_of_transaction_id: string | null;
}

// import_errors
export interface StatementImportError {
  id: string;
  page_number: number | null;
  row_index: number | null;
  raw_row_text: string | null;
  error_code: string;
  error_message: string;
  expected_running_balance_minor: number | null;
  actual_running_balance_minor: number | null;
}

// GET /statements/{id}/review
export interface StatementReview {
  statement: Statement;
  rows: StatementRow[];
  import_errors: StatementImportError[];
}

// POST /statements/upload (IngestResult)
export interface UploadResult {
  statement_id: string;
  processing_status: StatementProcessingStatus;
  row_count: number;
  auto_approved_count: number;
  pending_review_count: number;
  duplicate_count: number;
  mismatch_count: number;
  reconciliation_diff_minor: number;
}

// POST /statements/{id}/commit (CommitResult)
export interface CommitResult {
  statement_id: string;
  committed_count: number;
  skipped_count: number;
  already_committed: boolean;
  snapshot_written: boolean;
}

// PATCH /statements/rows/{id} body
export interface RowPatch {
  row_status?: ReviewableRowStatus;
  suggested_category_id?: string;
}

// Multipart upload through request(), so the Bearer token and 401 refresh retry apply.
export async function uploadStatement(file: File, accountId: string, kind: StatementKind): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file, file.name);
  form.append("account_id", accountId);
  form.append("statement_kind", kind);
  const { data } = await request<UploadResult>("POST", "/statements/upload", { body: form });
  return data;
}

export async function listStatements(accountId?: string): Promise<Statement[]> {
  const query = accountId === undefined ? "" : `?account_id=${encodeURIComponent(accountId)}`;
  const { data } = await request<Statement[]>("GET", `/statements${query}`);
  return data;
}

export async function getStatementReview(statementId: string): Promise<StatementReview> {
  const { data } = await request<StatementReview>("GET", `/statements/${encodeURIComponent(statementId)}/review`);
  return data;
}

export async function patchStatementRow(rowId: string, patch: RowPatch): Promise<void> {
  await request("PATCH", `/statements/rows/${encodeURIComponent(rowId)}`, { body: patch });
}

export async function commitStatement(statementId: string): Promise<CommitResult> {
  const path = `/statements/${encodeURIComponent(statementId)}/commit`;
  const { data } = await request<CommitResult>("POST", path, { idempotent: true });
  return data;
}
