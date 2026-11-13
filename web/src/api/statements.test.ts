import { beforeEach, describe, expect, it, vi } from "vitest";
import { request } from "./client";
import {
  commitStatement,
  getStatementReview,
  listStatements,
  patchStatementRow,
  uploadStatement,
} from "./statements";

vi.mock("./client", () => ({ request: vi.fn() }));

const requestMock = vi.mocked(request);

describe("statements API", () => {
  beforeEach(() => {
    requestMock.mockReset();
    requestMock.mockResolvedValue({ data: {}, meta: null });
  });

  it("lists all statements, or only one account's when an account id is given", async () => {
    await listStatements();
    await listStatements("acc 1");

    expect(requestMock).toHaveBeenNthCalledWith(1, "GET", "/statements");
    expect(requestMock).toHaveBeenNthCalledWith(2, "GET", "/statements?account_id=acc%201");
  });

  it("uploads a CSV as multipart form data with the account and kind fields", async () => {
    const file = new File(["date,amount"], "may.csv", { type: "text/csv" });

    await uploadStatement(file, "acc-1", "CSV");

    const [method, path, options] = requestMock.mock.calls[0] ?? [];
    expect(method).toBe("POST");
    expect(path).toBe("/statements/upload");
    const form = options?.body as FormData;
    expect(form).toBeInstanceOf(FormData);
    expect(form.get("account_id")).toBe("acc-1");
    expect(form.get("statement_kind")).toBe("CSV");
    expect((form.get("file") as File).name).toBe("may.csv");
  });

  it("gets the review for an encoded statement id", async () => {
    await getStatementReview("st/1");

    expect(requestMock).toHaveBeenCalledWith("GET", "/statements/st%2F1/review");
  });

  it("patches a row with the given body", async () => {
    await patchStatementRow("row-3", { suggested_category_id: "cat-food" });

    expect(requestMock).toHaveBeenCalledWith("PATCH", "/statements/rows/row-3", {
      body: { suggested_category_id: "cat-food" },
    });
  });

  it("commits a statement as an idempotent POST", async () => {
    await commitStatement("st-1");

    expect(requestMock).toHaveBeenCalledWith("POST", "/statements/st-1/commit", { idempotent: true });
  });
});
