import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createAccount, listAccounts } from "../../api/accounts";
import { ApiError } from "../../api/client";
import { listSplits, settleSplit, type Split } from "../../api/splits";
import { listStatements, uploadStatement } from "../../api/statements";
import type { Account } from "../../api/types";
import { AccountsPage } from "./AccountsPage";

vi.mock("../../api/accounts", () => ({ listAccounts: vi.fn(), createAccount: vi.fn() }));
vi.mock("../../api/splits", () => ({ listSplits: vi.fn(), settleSplit: vi.fn() }));
vi.mock("../../api/statements", () => ({
  listStatements: vi.fn(),
  uploadStatement: vi.fn(),
  listCategories: vi.fn(),
  getStatementReview: vi.fn(),
  patchStatementRow: vi.fn(),
  commitStatement: vi.fn(),
}));

// jsdom may not implement the native dialog methods; these stand-ins toggle the open attribute.
beforeAll(() => {
  if (typeof HTMLDialogElement.prototype.showModal !== "function") {
    HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
      this.setAttribute("open", "");
    };
  }
  if (typeof HTMLDialogElement.prototype.close !== "function") {
    HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
      this.removeAttribute("open");
      this.dispatchEvent(new Event("close"));
    };
  }
});

function account(
  overrides: Partial<Account> &
    Pick<Account, "id" | "name" | "account_subtype" | "account_class" | "current_balance_minor">,
): Account {
  return {
    institution: null,
    currency: "INR",
    opening_balance_minor: null,
    credit_limit_minor: null,
    billing_day: null,
    due_day: null,
    is_liquid: false,
    is_active: true,
    version: 1,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

const bankAccount = account({
  id: "a1",
  name: "HDFC Savings",
  account_subtype: "BANK_SAVINGS",
  account_class: "ASSET",
  current_balance_minor: 2500005,
  institution: "HDFC Bank",
});
const cardAccount = account({
  id: "c1",
  name: "Amex Gold",
  account_subtype: "CREDIT_CARD",
  account_class: "LIABILITY",
  current_balance_minor: -1600000,
  credit_limit_minor: 5000000,
});
const loanAccount = account({
  id: "l1",
  name: "Home Loan",
  account_subtype: "LOAN_HOME",
  account_class: "LIABILITY",
  current_balance_minor: -1200000,
});

function splitFixture(overrides: Partial<Split> = {}): Split {
  return {
    id: "s1",
    transaction_id: "t1",
    counterparty_name: "Ravi",
    counterparty_vpa: null,
    owed_amount_minor: 50000,
    settled_amount_minor: 0,
    outstanding_minor: 50000,
    status: "OPEN",
    settlement_transaction_id: null,
    created_at: "2026-11-01T00:00:00Z",
    transaction_date: "2026-11-01",
    description: "Dinner",
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/accounts"]}>
      <AccountsPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(listAccounts).mockResolvedValue([bankAccount, cardAccount, loanAccount]);
  vi.mocked(listSplits).mockResolvedValue([]);
  vi.mocked(listStatements).mockResolvedValue([]);
});

describe("account list", () => {
  it("groups accounts by subtype and shows liabilities as owed", async () => {
    renderPage();

    expect(await screen.findByRole("heading", { name: "Bank & Cash" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Cards" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Loans" })).toBeTruthy();
    expect(screen.getByText("₹12,000.00 owed")).toBeTruthy();
    expect(screen.getByText("₹16,000.00 owed")).toBeTruthy();
    expect(screen.getByText("32% of ₹50,000.00 limit")).toBeTruthy();
    expect(screen.queryByText(/−/)).toBeNull();
  });

  it("shows the empty state with an Add Account button", async () => {
    vi.mocked(listAccounts).mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText("No accounts yet")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Add Account" }).length).toBe(2);
  });
});

describe("add account", () => {
  it("posts integer paise and requires an opening date when a balance is entered", async () => {
    vi.mocked(createAccount).mockResolvedValue(bankAccount);
    const user = userEvent.setup();
    renderPage();

    await screen.findByRole("heading", { name: "Bank & Cash" });
    await user.click(screen.getByRole("button", { name: "Add Account" }));
    const dialog = screen.getByRole("dialog");
    await user.type(within(dialog).getByLabelText("Account name"), "Goa Trip Cash");
    await user.selectOptions(within(dialog).getByLabelText("Account type"), "CASH");
    await user.type(within(dialog).getByLabelText("Opening balance"), "5000.50");
    await user.click(within(dialog).getByRole("button", { name: "Add Account" }));

    expect(within(dialog).getByText("Enter the date this balance is as of.")).toBeTruthy();
    expect(createAccount).not.toHaveBeenCalled();

    fireEvent.change(within(dialog).getByLabelText("Opening date"), { target: { value: "2026-04-01" } });
    await user.click(within(dialog).getByRole("button", { name: "Add Account" }));

    await waitFor(() => expect(createAccount).toHaveBeenCalledTimes(1));
    expect(createAccount).toHaveBeenCalledWith({
      name: "Goa Trip Cash",
      account_subtype: "CASH",
      opening_balance_minor: 500050,
      opening_date: "2026-04-01",
    });
  });
});

describe("owed to you", () => {
  it("lists open splits and shows the empty state when there are none", async () => {
    vi.mocked(listSplits).mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText("Nobody owes you anything.")).toBeTruthy();
    expect(listSplits).toHaveBeenCalledWith("OPEN");
    expect(listSplits).toHaveBeenCalledWith("PARTIAL");
  });

  it("cannot take more than the outstanding amount and posts the right body", async () => {
    vi.mocked(listSplits).mockImplementation(async (status) => (status === "OPEN" ? [splitFixture()] : []));
    vi.mocked(settleSplit).mockResolvedValue({ transaction: {} as never, split: splitFixture() });
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Record Repayment" }));
    const dialog = screen.getByRole("dialog");
    const amount = within(dialog).getByLabelText("Amount (₹)") as HTMLInputElement;
    expect(amount.value).toBe("500.00");
    expect(within(dialog).queryByRole("option", { name: "Amex Gold" })).toBeNull();

    await user.clear(amount);
    await user.type(amount, "600");
    await user.click(within(dialog).getByRole("button", { name: "Record Repayment" }));
    expect(within(dialog).getByText("The amount cannot be more than ₹500.00.")).toBeTruthy();
    expect(settleSplit).not.toHaveBeenCalled();

    await user.clear(amount);
    await user.type(amount, "200");
    await user.click(within(dialog).getByRole("button", { name: "Record Repayment" }));

    await waitFor(() => expect(settleSplit).toHaveBeenCalledTimes(1));
    expect(settleSplit).toHaveBeenCalledWith(
      "s1",
      expect.objectContaining({ bank_account_id: "a1", amount_minor: 20000 }),
      expect.any(String),
    );
  });
});

describe("statement upload", () => {
  async function chooseFile(user: ReturnType<typeof userEvent.setup>, name: string) {
    await user.click(await screen.findByRole("button", { name: "Upload Statement" }));
    const dialog = screen.getByRole("dialog");
    const input = within(dialog).getByLabelText(/Statement file/);
    await user.upload(input, new File(["date,amount"], name, { type: "text/csv" }));
    return dialog;
  }

  it("maps DUPLICATE_STATEMENT to a message with a link to the existing review", async () => {
    vi.mocked(uploadStatement).mockRejectedValue(
      new ApiError(409, "DUPLICATE_STATEMENT", "This statement was already imported.", { statement_id: "st-9" }),
    );
    const user = userEvent.setup();
    renderPage();
    const dialog = await chooseFile(user, "may.csv");

    await user.click(within(dialog).getByRole("button", { name: "Upload" }));

    expect(await within(dialog).findByText("This file was already uploaded.")).toBeTruthy();
    const link = within(dialog).getByRole("link", { name: "View its review" });
    expect(link.getAttribute("href") ?? "").toContain("statement=st-9");
  });

  it("maps LAYOUT_DRIFT to the layout message", async () => {
    vi.mocked(uploadStatement).mockRejectedValue(new ApiError(422, "LAYOUT_DRIFT", "drift"));
    const user = userEvent.setup();
    renderPage();
    const dialog = await chooseFile(user, "may.csv");

    await user.click(within(dialog).getByRole("button", { name: "Upload" }));

    expect(
      await within(dialog).findByText(
        "This statement's layout differs from the last one for this account, so it was not imported.",
      ),
    ).toBeTruthy();
  });

  it("offers only CSV and marks PDF kinds as disabled", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Upload Statement" }));
    const dialog = screen.getByRole("dialog");
    const kind = within(dialog).getByLabelText("Statement type") as HTMLSelectElement;
    const pdf = within(kind).getByRole("option", { name: "Bank statement (PDF)" }) as HTMLOptionElement;
    expect(pdf.disabled).toBe(true);
    expect(within(dialog).getByText("PDF statements are not supported yet.")).toBeTruthy();
  });
});
