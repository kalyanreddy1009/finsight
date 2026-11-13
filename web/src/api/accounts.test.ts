import { beforeEach, describe, expect, it, vi } from "vitest";
import { request } from "./client";
import { createAccount, listAccounts, type AccountCreateBody } from "./accounts";

vi.mock("./client", () => ({ request: vi.fn() }));

const requestMock = vi.mocked(request);

describe("accounts API", () => {
  beforeEach(() => {
    requestMock.mockReset();
  });

  it("lists accounts with a GET to /accounts and returns the data", async () => {
    const accounts = [{ id: "a1", name: "HDFC Savings" }];
    requestMock.mockResolvedValue({ data: accounts, meta: null });

    const result = await listAccounts();

    expect(requestMock).toHaveBeenCalledWith("GET", "/accounts");
    expect(result).toBe(accounts);
  });

  it("creates an account with a POST to /accounts and sends the body unchanged", async () => {
    const body: AccountCreateBody = { name: "Card", account_subtype: "CREDIT_CARD", credit_limit_minor: 5000000 };
    requestMock.mockResolvedValue({ data: { id: "a2", ...body }, meta: null });

    const created = await createAccount(body);

    expect(requestMock).toHaveBeenCalledWith("POST", "/accounts", { body });
    expect(created).toEqual({ id: "a2", ...body });
  });
});
