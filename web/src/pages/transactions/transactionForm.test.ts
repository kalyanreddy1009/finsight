import { describe, expect, it } from "vitest";
import { groupByDate, formatDateHeading } from "./groupByDate";
import { emptyDraft, validateDraft, yourShareMinor, AMOUNT_ERROR, type EntryDraft } from "./transactionForm";
import { makeTransaction } from "./testFixtures";

function expenseDraft(overrides: Partial<EntryDraft> = {}): EntryDraft {
  return {
    ...emptyDraft("2026-11-12"),
    kind: "expense",
    amount: "450",
    accountId: "acc-1",
    categoryId: "cat-food",
    ...overrides,
  };
}

describe("validateDraft", () => {
  it("rejects an amount that is not rupees", () => {
    const result = validateDraft(expenseDraft({ amount: "abc" }));

    expect(result.body).toBeNull();
    expect(result.errors.amount).toBe(AMOUNT_ERROR);
  });

  it("builds an expense body with integer paise and no empty description", () => {
    const result = validateDraft(expenseDraft({ amount: "1,250.50", description: "   " }));

    expect(result.errors).toEqual({});
    expect(result.body).toEqual({
      kind: "expense",
      amount_minor: 125050,
      transaction_date: "2026-11-12",
      account_id: "acc-1",
      category_id: "cat-food",
      splits: [],
    });
  });

  it("blocks a split whose friends owe more than the total", () => {
    const result = validateDraft(
      expenseDraft({
        amount: "1000",
        splits: [
          { id: "a", name: "Asha", owed: "600" },
          { id: "b", name: "Ravi", owed: "500" },
        ],
      }),
    );

    expect(result.body).toBeNull();
    expect(result.errors.splits).toBe(
      "Friends' shares add up to more than the total. Reduce them by ₹100.00.",
    );
  });

  it("sends split amounts as integer paise", () => {
    const result = validateDraft(expenseDraft({ splits: [{ id: "a", name: "Asha", owed: "300" }] }));

    expect(result.body).toMatchObject({
      kind: "expense",
      splits: [{ counterparty_name: "Asha", owed_amount_minor: 30000 }],
    });
  });

  it("requires two different accounts for a transfer", () => {
    const result = validateDraft({
      ...expenseDraft({ kind: "transfer", accountId: "acc-1", toAccountId: "acc-1", categoryId: "" }),
    });

    expect(result.body).toBeNull();
    expect(result.errors.toAccountId).toBe("Choose two different accounts.");
  });

  it("builds a transfer body with from and to account ids", () => {
    const result = validateDraft({
      ...expenseDraft({ kind: "transfer", accountId: "acc-1", toAccountId: "acc-2", categoryId: "", description: "Card bill" }),
    });

    expect(result.body).toEqual({
      kind: "transfer",
      amount_minor: 45000,
      transaction_date: "2026-11-12",
      from_account_id: "acc-1",
      to_account_id: "acc-2",
      description: "Card bill",
    });
  });
});

describe("yourShareMinor", () => {
  it("subtracts the friends' amounts from the total", () => {
    expect(yourShareMinor(100000, [{ id: "a", name: "Asha", owed: "250.25" }])).toBe(74975);
  });
});

describe("groupByDate", () => {
  it("groups rows under one heading per date in API order", () => {
    const groups = groupByDate([
      makeTransaction({ id: "t1", transaction_date: "2026-11-12" }),
      makeTransaction({ id: "t2", transaction_date: "2026-11-12" }),
      makeTransaction({ id: "t3", transaction_date: "2026-11-10" }),
    ]);

    expect(groups.map((group) => group.label)).toEqual(["12 November 2026", "10 November 2026"]);
    expect(groups[0]?.items.map((item) => item.id)).toEqual(["t1", "t2"]);
  });

  it("formats ISO dates as day, month name and year", () => {
    expect(formatDateHeading("2026-01-05")).toBe("5 January 2026");
  });
});
