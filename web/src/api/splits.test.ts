import { beforeEach, describe, expect, it, vi } from "vitest";
import { request } from "./client";
import { listSplits, settleSplit, type SettleBody } from "./splits";

vi.mock("./client", () => ({ request: vi.fn() }));

const requestMock = vi.mocked(request);

describe("splits API", () => {
  beforeEach(() => {
    requestMock.mockReset();
  });

  it("lists every split when no status is given", async () => {
    requestMock.mockResolvedValue({ data: [], meta: null });

    await listSplits();

    expect(requestMock).toHaveBeenCalledWith("GET", "/splits");
  });

  it("filters the list by status in the query string", async () => {
    requestMock.mockResolvedValue({ data: [], meta: null });

    await listSplits("PARTIAL");

    expect(requestMock).toHaveBeenCalledWith("GET", "/splits?status=PARTIAL");
  });

  it("settles a split with an encoded id, the body and the caller's idempotency key", async () => {
    const body: SettleBody = { bank_account_id: "acc-1", amount_minor: 50000 };
    const settled = { transaction: { id: "tx-9" }, split: { id: "s/1" } };
    requestMock.mockResolvedValue({ data: settled, meta: null });

    const result = await settleSplit("s/1", body, "key-42");

    expect(requestMock).toHaveBeenCalledWith("POST", "/splits/s%2F1/settle", { body, idempotencyKey: "key-42" });
    expect(result).toBe(settled);
  });
});
