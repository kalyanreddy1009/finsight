import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import * as transactionsApi from "../../api/transactions";
import { QuickAddDialog } from "./QuickAddDialog";
import { installDialogStub } from "./testDialog";
import { makeAccount, makeCategory, makeTransaction } from "./testFixtures";

vi.mock("../../api/transactions", () => ({ createTransaction: vi.fn() }));

const createTransaction = vi.mocked(transactionsApi.createTransaction);
const accounts = [makeAccount({ id: "acc-1", name: "HDFC Savings" }), makeAccount({ id: "acc-2", name: "ICICI Card" })];
const categories = [
  makeCategory({ id: "cat-food", name: "Food", category_type: "EXPENSE" }),
  makeCategory({ id: "cat-salary", name: "Salary", category_type: "INCOME" }),
];

function renderDialog(onAdded = vi.fn()) {
  const onClose = vi.fn();
  render(
    <QuickAddDialog open accounts={accounts} categories={categories} onClose={onClose} onAdded={onAdded} />,
  );
  return { onClose, onAdded };
}

async function fillAmountAndDate(user: ReturnType<typeof userEvent.setup>, amount: string) {
  await user.type(screen.getByLabelText("Amount (₹)"), amount);
  fireEvent.change(screen.getByLabelText("Date"), { target: { value: "2026-11-12" } });
}

describe("QuickAddDialog", () => {
  beforeAll(() => {
    installDialogStub();
  });

  beforeEach(() => {
    createTransaction.mockReset();
    createTransaction.mockResolvedValue(makeTransaction());
  });

  it("rejects an amount that is not rupees, with the error beside the field", async () => {
    const user = userEvent.setup();
    renderDialog();

    await user.type(screen.getByLabelText("Amount (₹)"), "abc");
    await user.tab();

    expect(screen.getByText("Enter the amount in rupees, for example 450 or 1,250.50.")).toBeTruthy();
    expect(createTransaction).not.toHaveBeenCalled();
  });

  it("computes Your share live and blocks a split that exceeds the total", async () => {
    const user = userEvent.setup();
    renderDialog();
    await fillAmountAndDate(user, "1000");
    await user.selectOptions(screen.getByLabelText("Account"), "acc-1");
    await user.selectOptions(screen.getByLabelText("Category"), "cat-food");

    await user.click(screen.getByRole("button", { name: "Add Person" }));
    await user.type(screen.getByLabelText("Person 1 name"), "Asha");
    await user.type(screen.getByLabelText("Person 1 owes (₹)"), "600");
    expect(screen.getByText("Your share: ₹400.00")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Add Person" }));
    await user.type(screen.getByLabelText("Person 2 name"), "Ravi");
    await user.type(screen.getByLabelText("Person 2 owes (₹)"), "500");
    expect(screen.getByText("Your share: −₹100.00")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Add Expense" }));

    expect(screen.getByText("Friends' shares add up to more than the total. Reduce them by ₹100.00.")).toBeTruthy();
    expect(createTransaction).not.toHaveBeenCalled();
  });

  it("submits an expense with split amounts as integer paise", async () => {
    const user = userEvent.setup();
    const { onAdded, onClose } = renderDialog();
    await fillAmountAndDate(user, "1,000.50");
    await user.selectOptions(screen.getByLabelText("Account"), "acc-1");
    await user.selectOptions(screen.getByLabelText("Category"), "cat-food");
    await user.click(screen.getByRole("button", { name: "Add Person" }));
    await user.type(screen.getByLabelText("Person 1 name"), "Asha");
    await user.type(screen.getByLabelText("Person 1 owes (₹)"), "300");

    await user.click(screen.getByRole("button", { name: "Add Expense" }));

    await waitFor(() => expect(onAdded).toHaveBeenCalledTimes(1));
    expect(createTransaction).toHaveBeenCalledWith({
      kind: "expense",
      amount_minor: 100050,
      transaction_date: "2026-11-12",
      account_id: "acc-1",
      category_id: "cat-food",
      splits: [{ counterparty_name: "Asha", owed_amount_minor: 30000 }],
    });
    expect(onClose).toHaveBeenCalled();
  });

  it("filters categories by kind and submits an income body", async () => {
    const user = userEvent.setup();
    const { onAdded } = renderDialog();
    await user.click(screen.getByRole("button", { name: "Income" }));
    const category = screen.getByLabelText("Category");
    expect(within(category).queryByRole("option", { name: "Food" })).toBeNull();
    await fillAmountAndDate(user, "5000");
    await user.selectOptions(screen.getByLabelText("Account"), "acc-1");
    await user.selectOptions(category, "cat-salary");

    await user.click(screen.getByRole("button", { name: "Add Income" }));

    await waitFor(() => expect(onAdded).toHaveBeenCalledTimes(1));
    expect(createTransaction).toHaveBeenCalledWith({
      kind: "income",
      amount_minor: 500000,
      transaction_date: "2026-11-12",
      account_id: "acc-1",
      category_id: "cat-salary",
    });
  });

  it("submits a transfer with from and to accounts and a description", async () => {
    const user = userEvent.setup();
    const { onAdded } = renderDialog();
    await user.click(screen.getByRole("button", { name: "Transfer" }));
    await fillAmountAndDate(user, "2500");
    await user.selectOptions(screen.getByLabelText("From account"), "acc-1");
    await user.selectOptions(screen.getByLabelText("To account"), "acc-2");
    await user.type(screen.getByLabelText("Description (optional)"), "  Card bill ");

    await user.click(screen.getByRole("button", { name: "Add Transfer" }));

    await waitFor(() => expect(onAdded).toHaveBeenCalledTimes(1));
    expect(createTransaction).toHaveBeenCalledWith({
      kind: "transfer",
      amount_minor: 250000,
      transaction_date: "2026-11-12",
      from_account_id: "acc-1",
      to_account_id: "acc-2",
      description: "Card bill",
    });
  });

  it("shows the network error inside the dialog and re-enables the button", async () => {
    const user = userEvent.setup();
    const { onAdded } = renderDialog();
    createTransaction.mockRejectedValue(
      new ApiError(0, "NETWORK_ERROR", "FinSight cannot be reached. Check your connection and try again."),
    );
    await fillAmountAndDate(user, "100");
    await user.selectOptions(screen.getByLabelText("Account"), "acc-1");
    await user.selectOptions(screen.getByLabelText("Category"), "cat-food");

    await user.click(screen.getByRole("button", { name: "Add Expense" }));

    expect(await screen.findByText("FinSight cannot be reached. Check your connection and try again.")).toBeTruthy();
    expect(onAdded).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Add Expense" })).toBeTruthy();
  });

  it("shows Adding while the request is in flight", async () => {
    const user = userEvent.setup();
    renderDialog();
    createTransaction.mockReturnValue(new Promise(() => undefined));
    await fillAmountAndDate(user, "100");
    await user.selectOptions(screen.getByLabelText("Account"), "acc-1");
    await user.selectOptions(screen.getByLabelText("Category"), "cat-food");

    await user.click(screen.getByRole("button", { name: "Add Expense" }));

    const button = await screen.findByRole("button", { name: "Adding…" });
    expect(button.hasAttribute("disabled")).toBe(true);
  });
});
