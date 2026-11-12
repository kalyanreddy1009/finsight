import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import * as transactionsApi from "../../api/transactions";
import { TransactionDetailDialog } from "./TransactionDetailDialog";
import { installDialogStub } from "./testDialog";
import { makeCategory, makeTransaction } from "./testFixtures";

vi.mock("../../api/transactions", () => ({
  getTransaction: vi.fn(),
  patchTransaction: vi.fn(),
  reverseTransaction: vi.fn(),
}));

const patchTransaction = vi.mocked(transactionsApi.patchTransaction);
const getTransaction = vi.mocked(transactionsApi.getTransaction);
const reverseTransaction = vi.mocked(transactionsApi.reverseTransaction);
const categories = [makeCategory({ id: "cat-food", name: "Food" }), makeCategory({ id: "cat-fuel", name: "Fuel" })];
const CONFLICT_TEXT = "This transaction changed elsewhere. Reload to see the latest.";

function renderDetail(transaction = makeTransaction()) {
  const handlers = { onClose: vi.fn(), onSaved: vi.fn(), onReversed: vi.fn() };
  render(<TransactionDetailDialog transaction={transaction} categories={categories} {...handlers} />);
  return handlers;
}

describe("TransactionDetailDialog", () => {
  beforeAll(() => {
    installDialogStub();
  });

  beforeEach(() => {
    patchTransaction.mockReset();
    getTransaction.mockReset();
    reverseTransaction.mockReset();
  });

  it("saves changed notes with the row's version and reports the updated row", async () => {
    const user = userEvent.setup();
    const updated = makeTransaction({ version: 4, notes: "Team lunch" });
    patchTransaction.mockResolvedValue(updated);
    const { onSaved } = renderDetail();

    await user.type(screen.getByLabelText("Notes"), "Team lunch");
    await user.click(screen.getByRole("button", { name: "Save Changes" }));

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(updated));
    expect(patchTransaction).toHaveBeenCalledWith("tx-1", 3, { notes: "Team lunch" });
  });

  it("keeps Save Changes disabled until something changes", () => {
    renderDetail();

    expect((screen.getByRole("button", { name: "Save Changes" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("shows the conflict message on 409 and Reload refetches the row", async () => {
    const user = userEvent.setup();
    patchTransaction.mockRejectedValue(new ApiError(409, "VERSION_CONFLICT", "The transaction was changed by someone else."));
    const fresh = makeTransaction({ version: 5 });
    getTransaction.mockResolvedValue(fresh);
    const { onSaved } = renderDetail();

    await user.selectOptions(screen.getByLabelText("Category"), "cat-fuel");
    await user.click(screen.getByRole("button", { name: "Save Changes" }));

    expect(await screen.findByText(CONFLICT_TEXT)).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Reload" }));

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(fresh));
    expect(getTransaction).toHaveBeenCalledWith("tx-1");
  });

  it("asks for confirmation before reversing", async () => {
    const user = userEvent.setup();
    reverseTransaction.mockResolvedValue(makeTransaction({ id: "rev-1" }));
    const { onReversed } = renderDetail();

    await user.click(screen.getByRole("button", { name: "Reverse Transaction" }));

    expect(screen.getByText("Reverse this transaction? This posts an opposite entry and cannot be undone.")).toBeTruthy();
    expect(reverseTransaction).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Post Reversal" }));

    await waitFor(() => expect(onReversed).toHaveBeenCalledTimes(1));
    expect(reverseTransaction).toHaveBeenCalledWith("tx-1", expect.any(String));
  });

  it("does not reverse when the user keeps the transaction", async () => {
    const user = userEvent.setup();
    renderDetail();

    await user.click(screen.getByRole("button", { name: "Reverse Transaction" }));
    await user.click(screen.getByRole("button", { name: "Keep Transaction" }));

    expect(reverseTransaction).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Reverse Transaction" })).toBeTruthy();
  });

  it("hides edit and reverse for a reversed row", () => {
    renderDetail(makeTransaction({ review_status: "SUPERSEDED" }));

    expect(screen.queryByRole("button", { name: "Save Changes" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Reverse Transaction" })).toBeNull();
    expect(screen.getByText("This transaction was reversed, so it can no longer be changed.")).toBeTruthy();
  });
});
