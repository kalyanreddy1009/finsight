import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TransactionList } from "./TransactionList";
import type { TransactionListView } from "./useTransactionList";
import { makeTransaction } from "./testFixtures";

function view(overrides: Partial<TransactionListView> = {}): TransactionListView {
  return {
    status: "ready",
    items: [],
    nextCursor: null,
    isLoadingMore: false,
    loadMoreFailed: false,
    loadMore: vi.fn(),
    reload: vi.fn(),
    ...overrides,
  };
}

function renderList(listView: TransactionListView, filtersActive = false) {
  const onSelect = vi.fn();
  const onAdd = vi.fn();
  render(<TransactionList view={listView} filtersActive={filtersActive} onSelect={onSelect} onAdd={onAdd} />);
  return { onSelect, onAdd };
}

describe("TransactionList", () => {
  it("groups rows under date headings and marks money out and in with a sign and hidden text", () => {
    renderList(
      view({
        items: [
          makeTransaction({ id: "t1", transaction_date: "2026-11-12", clean_description: "Swiggy", amount_minor: 45000, direction: "DEBIT" }),
          makeTransaction({ id: "t2", transaction_date: "2026-11-12", clean_description: null, description: "SALARY NOV", amount_minor: 1000000, direction: "CREDIT", category_name: null }),
          makeTransaction({ id: "t3", transaction_date: "2026-11-10", clean_description: "Metro", amount_minor: 2500, direction: "DEBIT" }),
        ],
      }),
    );

    expect(screen.getByRole("heading", { name: "12 November 2026" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "10 November 2026" })).toBeTruthy();

    const out = screen.getByRole("button", { name: /Swiggy/ });
    expect(out.textContent).toContain("−₹450.00");
    expect(within(out).getByText("out")).toBeTruthy();

    const incoming = screen.getByRole("button", { name: /SALARY NOV/ });
    expect(incoming.textContent).toContain("+₹10,000.00");
    expect(within(incoming).getByText("in")).toBeTruthy();
    expect(incoming.textContent).toContain("No category");
  });

  it("labels a reversed row and strikes it through", () => {
    renderList(view({ items: [makeTransaction({ id: "t9", review_status: "SUPERSEDED", clean_description: "Rent" })] }));

    const row = screen.getByRole("button", { name: /Rent/ });

    expect(within(row).getByText("Reversed")).toBeTruthy();
    expect(row.className).toContain("tx-row--reversed");
  });

  it("shows Provisional and Needs Review text badges", () => {
    renderList(
      view({
        items: [
          makeTransaction({ id: "p1", review_status: "PROVISIONAL", clean_description: "Hotel" }),
          makeTransaction({ id: "p2", review_status: "PENDING_REVIEW", clean_description: "Cab" }),
        ],
      }),
    );

    expect(within(screen.getByRole("button", { name: /Hotel/ })).getByText("Provisional")).toBeTruthy();
    expect(within(screen.getByRole("button", { name: /Cab/ })).getByText("Needs Review")).toBeTruthy();
  });

  it("calls onSelect with the row's transaction", async () => {
    const user = userEvent.setup();
    const transaction = makeTransaction({ clean_description: "Swiggy" });
    const { onSelect } = renderList(view({ items: [transaction] }));

    await user.click(screen.getByRole("button", { name: /Swiggy/ }));

    expect(onSelect).toHaveBeenCalledWith(transaction);
  });

  it("shows Load More only while a next cursor exists and calls loadMore", async () => {
    const user = userEvent.setup();
    const loadMore = vi.fn();
    renderList(view({ items: [makeTransaction()], nextCursor: "abc", loadMore }));

    await user.click(screen.getByRole("button", { name: "Load More" }));

    expect(loadMore).toHaveBeenCalledTimes(1);
  });

  it("hides Load More when there is no next cursor", () => {
    renderList(view({ items: [makeTransaction()], nextCursor: null }));

    expect(screen.queryByRole("button", { name: "Load More" })).toBeNull();
  });

  it("shows the empty state with an Add Expense button", async () => {
    const user = userEvent.setup();
    const { onAdd } = renderList(view({ items: [] }));

    expect(screen.getByText("No transactions yet")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Add Expense" }));

    expect(onAdd).toHaveBeenCalledTimes(1);
  });

  it("shows a filtered empty message without the add button", () => {
    renderList(view({ items: [] }), true);

    expect(screen.queryByRole("button", { name: "Add Expense" })).toBeNull();
    expect(screen.getByText(/No transactions match these filters/)).toBeTruthy();
  });

  it("shows an inline error with Try Again that reloads", async () => {
    const user = userEvent.setup();
    const reload = vi.fn();
    renderList(view({ status: "error", reload }));

    expect(screen.getByRole("alert").textContent).toContain("Could not load transactions");
    await user.click(screen.getByRole("button", { name: "Try Again" }));

    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("shows a loading skeleton while loading", () => {
    renderList(view({ status: "loading" }));

    expect(screen.getByRole("status").textContent).toBe("Loading transactions");
  });
});
