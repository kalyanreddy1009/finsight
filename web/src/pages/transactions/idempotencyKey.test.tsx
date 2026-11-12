import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import * as transactionsApi from "../../api/transactions";
import { AddTransactionForm } from "./AddTransactionForm";
import { ReverseSection } from "./ReverseSection";
import { makeAccount, makeCategory, makeTransaction } from "./testFixtures";

vi.mock("../../api/transactions", () => ({ createTransaction: vi.fn(), reverseTransaction: vi.fn() }));

const createTransaction = vi.mocked(transactionsApi.createTransaction);
const reverseTransaction = vi.mocked(transactionsApi.reverseTransaction);
const networkError = new ApiError(0, "NETWORK_ERROR", "FinSight cannot be reached. Check your connection and try again.");
const accounts = [makeAccount({ id: "acc-1", name: "HDFC Savings" })];
const categories = [makeCategory({ id: "cat-food", name: "Food", category_type: "EXPENSE" })];

function keyOfCall(mock: { mock: { calls: unknown[][] } }, index: number): unknown {
  return mock.mock.calls[index]?.[mock.mock.calls[index].length - 1];
}

describe("idempotency keys on keyed forms", () => {
  beforeEach(() => {
    createTransaction.mockReset();
    reverseTransaction.mockReset();
  });

  async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole("button", { name: "Add Expense" }));
  }

  function renderAdd() {
    return render(<AddTransactionForm accounts={accounts} categories={categories} onCancel={vi.fn()} onAdded={vi.fn()} />);
  }

  it("reuses the key after a failed add and sends a new key for a new form after success", async () => {
    createTransaction.mockRejectedValueOnce(networkError).mockResolvedValue(makeTransaction());
    const user = userEvent.setup();
    const first = renderAdd();
    await user.type(screen.getByLabelText("Amount (₹)"), "100");
    fireEvent.change(screen.getByLabelText("Date"), { target: { value: "2026-11-12" } });
    await user.selectOptions(screen.getByLabelText("Account"), "acc-1");
    await user.selectOptions(screen.getByLabelText("Category"), "cat-food");

    await fillAndSubmit(user);
    await screen.findByText(networkError.message);
    await fillAndSubmit(user);
    await waitFor(() => expect(createTransaction).toHaveBeenCalledTimes(2));

    expect(keyOfCall(createTransaction, 1)).toBe(keyOfCall(createTransaction, 0));
    first.unmount();

    renderAdd();
    await user.type(screen.getByLabelText("Amount (₹)"), "100");
    fireEvent.change(screen.getByLabelText("Date"), { target: { value: "2026-11-12" } });
    await user.selectOptions(screen.getByLabelText("Account"), "acc-1");
    await user.selectOptions(screen.getByLabelText("Category"), "cat-food");
    await fillAndSubmit(user);
    await waitFor(() => expect(createTransaction).toHaveBeenCalledTimes(3));

    expect(keyOfCall(createTransaction, 2)).not.toBe(keyOfCall(createTransaction, 0));
  });

  it("reuses the key for a reversal retried after a failure", async () => {
    reverseTransaction.mockRejectedValueOnce(networkError).mockResolvedValue(makeTransaction());
    const user = userEvent.setup();
    render(<ReverseSection transaction={makeTransaction({ id: "tx-1" })} onReversed={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Reverse Transaction" }));

    await user.click(screen.getByRole("button", { name: "Post Reversal" }));
    await screen.findByText(networkError.message);
    await user.click(screen.getByRole("button", { name: "Post Reversal" }));
    await waitFor(() => expect(reverseTransaction).toHaveBeenCalledTimes(2));

    expect(keyOfCall(reverseTransaction, 1)).toBe(keyOfCall(reverseTransaction, 0));
    expect(typeof keyOfCall(reverseTransaction, 0)).toBe("string");
  });
});
