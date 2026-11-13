import { beforeEach, describe, expect, it, vi } from "vitest";
import { request } from "./client";
import { getDashboardSummary } from "./dashboard";

vi.mock("./client", () => ({ request: vi.fn() }));

const requestMock = vi.mocked(request);

describe("dashboard API", () => {
  beforeEach(() => {
    requestMock.mockReset();
  });

  it("fetches the summary with a GET to /dashboard/summary and returns its data", async () => {
    const summary = { safe_to_spend_minor: 120050 };
    requestMock.mockResolvedValue({ data: summary, meta: null });

    const result = await getDashboardSummary();

    expect(requestMock).toHaveBeenCalledWith("GET", "/dashboard/summary");
    expect(result).toBe(summary);
  });
});
