import { beforeEach, describe, expect, it, vi } from "vitest";
import { request } from "../../api/client";
import {
  createTransaction,
  listTransactions,
  patchTransaction,
  reverseTransaction,
} from "../../api/transactions";
import { makeTransaction } from "./testFixtures";

vi.mock("../../api/client", () => ({ request: vi.fn() }));

const requestMock = vi.mocked(request);

describe("transactions api wrappers", () => {
  beforeEach(() => {
    requestMock.mockReset();
  });

  it("builds the list query and reads next_cursor from meta", async () => {
    requestMock.mockResolvedValue({ data: [makeTransaction()], meta: { next_cursor: "c2" } });

    const page = await listTransactions({ q: "swi", accountId: "acc-1", needsReview: true, cursor: "c1" });

    expect(requestMock).toHaveBeenCalledWith(
      "GET",
      "/transactions?q=swi&account_id=acc-1&review_status=PENDING_REVIEW&cursor=c1",
    );
    expect(page.nextCursor).toBe("c2");
    expect(page.items).toHaveLength(1);
  });

  it("sends If-Match with the row version on PATCH", async () => {
    requestMock.mockResolvedValue({ data: makeTransaction({ version: 4 }), meta: null });

    await patchTransaction("tx-1", 3, { notes: "Team lunch" });

    expect(requestMock).toHaveBeenCalledWith("PATCH", "/transactions/tx-1", {
      body: { notes: "Team lunch" },
      headers: { "If-Match": "3" },
    });
  });

  it("posts creates as idempotent", async () => {
    requestMock.mockResolvedValue({ data: makeTransaction(), meta: null });
    const body = { kind: "income" as const, amount_minor: 100, transaction_date: "2026-11-12", account_id: "a", category_id: "c" };

    await createTransaction(body);

    expect(requestMock).toHaveBeenCalledWith("POST", "/transactions", { body, idempotent: true });
  });

  it("posts reversals as idempotent", async () => {
    requestMock.mockResolvedValue({ data: makeTransaction(), meta: null });

    await reverseTransaction("tx-1");

    expect(requestMock).toHaveBeenCalledWith("POST", "/transactions/tx-1/reverse", { idempotent: true });
  });
});
