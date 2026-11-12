import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TransactionRow } from "./TransactionRow";
import { makeTransaction } from "./testFixtures";

function renderRow(overrides: Parameters<typeof makeTransaction>[0]) {
  return render(
    <ul>
      <TransactionRow transaction={makeTransaction(overrides)} onSelect={() => undefined} />
    </ul>,
  );
}

describe("TransactionRow split expenses", () => {
  it("shows Your share when the user's share differs from the expense amount", () => {
    renderRow({ transaction_type: "EXPENSE", amount_minor: 100000, user_share_minor: 40000 });

    expect(screen.getByText("Your share ₹400.00")).toBeTruthy();
  });

  it("shows no share line for an expense that is not split", () => {
    renderRow({ transaction_type: "EXPENSE", amount_minor: 100000, user_share_minor: 100000 });

    expect(screen.queryByText(/Your share/)).toBeNull();
  });
});
