import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import * as categoriesApi from "../../api/categories";
import * as transactionsApi from "../../api/transactions";
import { TransactionsPage } from "./TransactionsPage";
import { installDialogStub } from "./testDialog";
import { makeAccount, makeCategory, makeTransaction } from "./testFixtures";

vi.mock("../../api/transactions", () => ({
  listTransactions: vi.fn(),
  listAccountsForPicker: vi.fn(),
  createTransaction: vi.fn(),
  getTransaction: vi.fn(),
  patchTransaction: vi.fn(),
  reverseTransaction: vi.fn(),
}));
vi.mock("../../api/categories", () => ({ listCategories: vi.fn() }));

const listTransactions = vi.mocked(transactionsApi.listTransactions);
const listAccounts = vi.mocked(transactionsApi.listAccountsForPicker);
const listCategories = vi.mocked(categoriesApi.listCategories);

function LocationProbe() {
  const location = useLocation();
  return <p data-testid="location">{location.search}</p>;
}

function renderPage(path = "/transactions") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <TransactionsPage />
      <LocationProbe />
    </MemoryRouter>,
  );
}

function currentSearch(): string {
  return screen.getByTestId("location").textContent ?? "";
}

describe("TransactionsPage", () => {
  beforeEach(() => {
    installDialogStub();
    listTransactions.mockReset();
    listAccounts.mockReset();
    listCategories.mockReset();
    listAccounts.mockResolvedValue([makeAccount({ id: "acc-1", name: "HDFC Savings" })]);
    listCategories.mockResolvedValue([makeCategory({ id: "cat-food", name: "Food" })]);
    listTransactions.mockResolvedValue({ items: [makeTransaction({ clean_description: "Swiggy" })], nextCursor: null });
  });

  it("renders the list from the API under the page heading", async () => {
    renderPage();

    expect(await screen.findByRole("button", { name: /Swiggy/ })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Transactions" })).toBeTruthy();
    expect(listTransactions).toHaveBeenCalledWith(expect.objectContaining({ needsReview: false }));
  });

  it("appends the next page on Load More", async () => {
    const user = userEvent.setup();
    listTransactions
      .mockResolvedValueOnce({ items: [makeTransaction({ id: "t1", clean_description: "First" })], nextCursor: "cursor-2" })
      .mockResolvedValueOnce({ items: [makeTransaction({ id: "t2", clean_description: "Second" })], nextCursor: null });
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Load More" }));

    expect(await screen.findByRole("button", { name: /Second/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /First/ })).toBeTruthy();
    expect(listTransactions).toHaveBeenLastCalledWith(expect.objectContaining({ cursor: "cursor-2" }));
    expect(screen.queryByRole("button", { name: "Load More" })).toBeNull();
  });

  it("writes filters to the URL and refetches from the first page", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("button", { name: /Swiggy/ });

    await user.selectOptions(screen.getByLabelText("Account"), "acc-1");
    await waitFor(() => expect(currentSearch()).toContain("account=acc-1"));
    expect(listTransactions).toHaveBeenLastCalledWith(expect.objectContaining({ accountId: "acc-1" }));

    await user.click(screen.getByLabelText("Needs Review"));
    await waitFor(() => expect(currentSearch()).toContain("review=1"));
    expect(listTransactions).toHaveBeenLastCalledWith(expect.objectContaining({ needsReview: true, accountId: "acc-1" }));

    await user.type(screen.getByLabelText("Search"), "swi");
    await waitFor(() => expect(currentSearch()).toContain("q=swi"), { timeout: 1500 });
    expect(listTransactions).toHaveBeenLastCalledWith(expect.objectContaining({ q: "swi" }));
  });

  it("restores filters from the URL on load", async () => {
    renderPage("/transactions?category=cat-food&review=1");

    await screen.findByRole("button", { name: /Swiggy/ });

    expect(listTransactions).toHaveBeenLastCalledWith(
      expect.objectContaining({ categoryId: "cat-food", needsReview: true }),
    );
  });

  it("shows the empty state when there are no transactions", async () => {
    listTransactions.mockResolvedValue({ items: [], nextCursor: null });
    renderPage();

    expect(await screen.findByText("No transactions yet")).toBeTruthy();
  });

  it("shows an error with Try Again that retries the list", async () => {
    const user = userEvent.setup();
    listTransactions.mockRejectedValueOnce(new ApiError(0, "NETWORK_ERROR", "FinSight cannot be reached."));
    renderPage();

    expect(await screen.findByRole("alert")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Try Again" }));

    expect(await screen.findByRole("button", { name: /Swiggy/ })).toBeTruthy();
  });
});
