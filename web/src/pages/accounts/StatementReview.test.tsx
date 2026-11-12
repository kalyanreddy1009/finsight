import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import {
  commitStatement,
  getStatementReview,
  patchStatementRow,
  type Statement,
  type StatementImportError,
  type StatementReview,
  type StatementRow,
} from "../../api/statements";
import { listCategories } from "../../api/categories";
import type { Category } from "../../api/types";
import { AccountsPage } from "./AccountsPage";

vi.mock("../../api/accounts", () => ({ listAccounts: vi.fn(), createAccount: vi.fn() }));
vi.mock("../../api/categories", () => ({ listCategories: vi.fn() }));
vi.mock("../../api/splits", () => ({ listSplits: vi.fn(), settleSplit: vi.fn() }));
vi.mock("../../api/statements", () => ({
  listStatements: vi.fn(),
  uploadStatement: vi.fn(),
  getStatementReview: vi.fn(),
  patchStatementRow: vi.fn(),
  commitStatement: vi.fn(),
}));

function statementFixture(overrides: Partial<Statement> = {}): Statement {
  return {
    id: "st-1",
    account_id: "a1",
    statement_kind: "CSV",
    original_filename: "may.csv",
    statement_start_date: "2026-05-01",
    statement_end_date: "2026-05-31",
    opening_balance_minor: 100000,
    closing_balance_minor: 150000,
    reconciliation_diff_minor: 0,
    processing_status: "REVIEW_REQUIRED",
    uploaded_at: "2026-06-01T00:00:00Z",
    approved_at: null,
    ...overrides,
  };
}

function rowFixture(overrides: Partial<StatementRow> & Pick<StatementRow, "id">): StatementRow {
  return {
    statement_id: "st-1",
    row_index: 1,
    page_number: 1,
    tx_date: "2026-05-03",
    raw_description: "UPI/SWIGGY",
    clean_description: "Swiggy",
    direction: "DEBIT",
    amount_minor: 50000,
    stated_balance_minor: null,
    suggested_category_id: null,
    row_status: "PENDING_REVIEW",
    duplicate_of_transaction_id: null,
    ...overrides,
  };
}

const foodCategory: Category = {
  id: "cat-food",
  name: "Food & Dining",
  parent_category_id: null,
  category_type: "EXPENSE",
  default_tax_section: "NONE",
  is_discretionary: true,
  is_sensitive_private: false,
  is_system_category: true,
  created_at: "2026-01-01T00:00:00Z",
};

function importErrorFixture(): StatementImportError {
  return {
    id: "e1",
    page_number: 1,
    row_index: 4,
    raw_row_text: null,
    error_code: "BALANCE_MISMATCH",
    error_message: "Balance mismatch",
    expected_running_balance_minor: 100000,
    actual_running_balance_minor: 101500,
  };
}

function reviewFixture(statement: Statement, rows: StatementRow[], importErrors: StatementImportError[] = []): StatementReview {
  return { statement, rows, import_errors: importErrors };
}

function renderReview() {
  return render(
    <MemoryRouter initialEntries={["/accounts?statement=st-1"]}>
      <AccountsPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(listCategories).mockResolvedValue([foodCategory]);
  vi.mocked(patchStatementRow).mockImplementation(async (rowId, patch) => ({ ...rowFixture({ id: rowId }), ...patch }));
});

describe("statement review", () => {
  it("shows the reconciliation warning with the difference and import errors", async () => {
    vi.mocked(getStatementReview).mockResolvedValue(
      reviewFixture(statementFixture({ reconciliation_diff_minor: 150 }), [rowFixture({ id: "r1", row_status: "USER_APPROVED" })], [
        importErrorFixture(),
      ]),
    );
    renderReview();

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/The difference is ₹1.50/)).toBeTruthy();
    expect(within(alert).getByText(/Row 4: Balance mismatch/)).toBeTruthy();
  });

  it("sends approve, reject and not-a-duplicate as PATCH bodies", async () => {
    vi.mocked(getStatementReview).mockResolvedValue(
      reviewFixture(statementFixture(), [
        rowFixture({ id: "r1", row_status: "PENDING_REVIEW" }),
        rowFixture({ id: "r2", row_index: 2, row_status: "DUPLICATE" }),
      ]),
    );
    const user = userEvent.setup();
    renderReview();

    await user.click(await screen.findByRole("button", { name: "Approve" }));
    expect(patchStatementRow).toHaveBeenLastCalledWith("r1", { row_status: "USER_APPROVED" });

    await user.click(screen.getByRole("button", { name: "Not a Duplicate" }));
    expect(patchStatementRow).toHaveBeenLastCalledWith("r2", { row_status: "USER_APPROVED" });
  });

  it("sends reject as a PATCH body", async () => {
    vi.mocked(getStatementReview).mockResolvedValue(
      reviewFixture(statementFixture(), [rowFixture({ id: "r1", row_status: "PENDING_REVIEW" })]),
    );
    const user = userEvent.setup();
    renderReview();

    await user.click(await screen.findByRole("button", { name: "Reject" }));
    expect(patchStatementRow).toHaveBeenCalledWith("r1", { row_status: "REJECTED" });
  });

  it("shows the row state from the PATCH response, not the sent patch", async () => {
    vi.mocked(getStatementReview).mockResolvedValue(
      reviewFixture(statementFixture(), [rowFixture({ id: "r1", row_status: "PENDING_REVIEW" })]),
    );
    vi.mocked(patchStatementRow).mockResolvedValueOnce(
      rowFixture({ id: "r1", row_status: "REJECTED" }),
    );
    const user = userEvent.setup();
    renderReview();

    await user.click(await screen.findByRole("button", { name: "Approve" }));

    expect(await screen.findByText("Rejected", { selector: ".status-text" })).toBeTruthy();
    expect(screen.queryByText("Approved", { selector: ".status-text" })).toBeNull();
  });

  it("approves every pending row sequentially with Approve All Pending", async () => {
    vi.mocked(getStatementReview).mockResolvedValue(
      reviewFixture(statementFixture(), [
        rowFixture({ id: "r1", row_status: "PENDING_REVIEW" }),
        rowFixture({ id: "r2", row_index: 2, row_status: "PENDING_REVIEW" }),
      ]),
    );
    const user = userEvent.setup();
    renderReview();

    await user.click(await screen.findByRole("button", { name: "Approve All Pending" }));

    await waitFor(() => expect(patchStatementRow).toHaveBeenCalledTimes(2));
    expect(patchStatementRow).toHaveBeenNthCalledWith(1, "r1", { row_status: "USER_APPROVED" });
    expect(patchStatementRow).toHaveBeenNthCalledWith(2, "r2", { row_status: "USER_APPROVED" });
  });

  it("disables commit while rows are pending and enables it after approval", async () => {
    vi.mocked(getStatementReview).mockResolvedValue(
      reviewFixture(statementFixture(), [rowFixture({ id: "r1", row_status: "PENDING_REVIEW" })]),
    );
    const user = userEvent.setup();
    renderReview();

    const commit = (await screen.findByRole("button", { name: "Commit Statement" })) as HTMLButtonElement;
    expect(commit.disabled).toBe(true);
    expect(screen.getByText(/1 row still needs a decision/)).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => {
      const enabled = screen.getByRole("button", { name: "Commit Statement" }) as HTMLButtonElement;
      expect(enabled.disabled).toBe(false);
    });
  });

  it("shows the commit success message and the snapshot warning", async () => {
    vi.mocked(getStatementReview).mockResolvedValue(
      reviewFixture(statementFixture(), [rowFixture({ id: "r1", row_status: "USER_APPROVED" })]),
    );
    vi.mocked(commitStatement).mockResolvedValue({
      statement_id: "st-1",
      committed_count: 3,
      skipped_count: 0,
      already_committed: false,
      snapshot_written: false,
    });
    const user = userEvent.setup();
    renderReview();

    await user.click(await screen.findByRole("button", { name: "Commit Statement" }));

    expect(await screen.findByText("Committed 3 transactions")).toBeTruthy();
    expect(screen.getByText("The ledger balance does not match this statement's closing balance.")).toBeTruthy();
  });

  it("shows the server message when the statement does not reconcile", async () => {
    vi.mocked(getStatementReview).mockResolvedValue(
      reviewFixture(statementFixture({ reconciliation_diff_minor: 0 }), [rowFixture({ id: "r1", row_status: "USER_APPROVED" })]),
    );
    vi.mocked(commitStatement).mockRejectedValue(
      new ApiError(409, "STATEMENT_NOT_RECONCILED", "The statement does not reconcile yet."),
    );
    const user = userEvent.setup();
    renderReview();

    await user.click(await screen.findByRole("button", { name: "Commit Statement" }));

    expect(await screen.findByText("The statement does not reconcile yet.")).toBeTruthy();
  });

  it("opens an approved statement read-only", async () => {
    vi.mocked(getStatementReview).mockResolvedValue(
      reviewFixture(statementFixture({ processing_status: "APPROVED" }), [rowFixture({ id: "r1", row_status: "COMMITTED" })]),
    );
    renderReview();

    expect(await screen.findByText("This statement is already committed.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Commit Statement" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Approve All Pending" })).toBeNull();
  });
});

const salaryCategory: Category = {
  ...foodCategory,
  id: "cat-salary",
  name: "Salary",
  category_type: "INCOME",
  is_discretionary: false,
  is_system_category: false,
};

describe("statement review categories and committed rows", () => {
  it("offers only spending categories for a money-out row", async () => {
    vi.mocked(listCategories).mockResolvedValue([foodCategory, salaryCategory]);
    vi.mocked(getStatementReview).mockResolvedValue(reviewFixture(statementFixture(), [rowFixture({ id: "r1" })]));
    renderReview();

    const select = await screen.findByRole("combobox", { name: "Category" });
    const names = within(select).getAllByRole("option").map((option) => option.textContent);
    expect(names).toContain("Food & Dining");
    expect(names).not.toContain("Salary");
  });

  it("offers only income categories for a money-in row", async () => {
    vi.mocked(listCategories).mockResolvedValue([foodCategory, salaryCategory]);
    vi.mocked(getStatementReview).mockResolvedValue(
      reviewFixture(statementFixture(), [rowFixture({ id: "r2", direction: "CREDIT", clean_description: "Salary credit" })]),
    );
    renderReview();

    const select = await screen.findByRole("combobox", { name: "Category" });
    const names = within(select).getAllByRole("option").map((option) => option.textContent);
    expect(names).toContain("Salary");
    expect(names).not.toContain("Food & Dining");
  });

  it("keeps a suggested category of the other type selected", async () => {
    vi.mocked(listCategories).mockResolvedValue([foodCategory, salaryCategory]);
    vi.mocked(getStatementReview).mockResolvedValue(
      reviewFixture(statementFixture(), [rowFixture({ id: "r5", suggested_category_id: "cat-salary" })]),
    );
    renderReview();

    const select = (await screen.findByRole("combobox", { name: "Category" })) as HTMLSelectElement;
    expect(select.value).toBe("cat-salary");
    const salaryOption = within(select).getByRole("option", { name: "Salary" }) as HTMLOptionElement;
    expect(salaryOption.selected).toBe(true);
  });

  it("shows committed rows as Committed with no action buttons", async () => {
    vi.mocked(getStatementReview).mockResolvedValue(
      reviewFixture(statementFixture(), [rowFixture({ id: "r3", row_status: "COMMITTED", clean_description: "Done row" })]),
    );
    renderReview();

    const rowText = await screen.findByText("Committed");
    const row = rowText.closest("li");
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).queryByRole("button", { name: "Approve" })).toBeNull();
    expect(within(row as HTMLElement).queryByRole("button", { name: "Reject" })).toBeNull();
  });

  it("refetches the review after commit so the rows show Committed", async () => {
    const user = userEvent.setup();
    vi.mocked(getStatementReview)
      .mockResolvedValueOnce(reviewFixture(statementFixture(), [rowFixture({ id: "r4", row_status: "USER_APPROVED" })]))
      .mockResolvedValueOnce(reviewFixture(statementFixture({ processing_status: "APPROVED" }), [rowFixture({ id: "r4", row_status: "COMMITTED" })]));
    vi.mocked(commitStatement).mockResolvedValue({
      statement_id: "st-1",
      committed_count: 1,
      skipped_count: 0,
      already_committed: false,
      snapshot_written: true,
    });
    renderReview();

    await user.click(await screen.findByRole("button", { name: "Commit Statement" }));

    await waitFor(() => expect(getStatementReview).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Committed", { selector: ".status-text" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Reject" })).toBeNull();
  });
});

