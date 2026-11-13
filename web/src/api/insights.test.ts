import { beforeEach, describe, expect, it, vi } from "vitest";
import { request } from "./client";
import { getInsightsSummary } from "./insights";

vi.mock("./client", () => ({ request: vi.fn() }));

const requestMock = vi.mocked(request);

describe("insights API", () => {
  beforeEach(() => {
    requestMock.mockReset();
  });

  it("fetches six months by default and returns the data", async () => {
    const summary = { month: "2026-11" };
    requestMock.mockResolvedValue({ data: summary, meta: null });

    const result = await getInsightsSummary();

    expect(requestMock).toHaveBeenCalledWith("GET", "/insights/summary?months=6");
    expect(result).toBe(summary);
  });

  it("passes a custom month count", async () => {
    requestMock.mockResolvedValue({ data: {}, meta: null });

    await getInsightsSummary(3);

    expect(requestMock).toHaveBeenCalledWith("GET", "/insights/summary?months=3");
  });
});
