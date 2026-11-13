import { beforeEach, describe, expect, it, vi } from "vitest";
import { request } from "../../api/client";
import { deleteBudget, getBudget, saveBudget } from "../../api/budgets";
import { createGoal, deleteGoal, listGoals, updateGoal } from "../../api/goals";
import { advanceRecurring, createRecurring, deleteRecurring, listRecurring, updateRecurring } from "../../api/recurring";
import { getTaxSummary } from "../../api/tax";

vi.mock("../../api/client", () => ({ request: vi.fn() }));

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(request).mockResolvedValue({ data: null, meta: null });
});

describe("budgets api", () => {
  it("reads one month", async () => {
    await getBudget("2026-11");
    expect(request).toHaveBeenCalledWith("GET", "/budgets/2026-11");
  });

  it("saves a month with PUT and passes the body through", async () => {
    const body = { total_limit_minor: 5000000, categories: [{ category_id: "food", limit_minor: 100000 }] };
    await saveBudget("2026-11", body);
    expect(request).toHaveBeenCalledWith("PUT", "/budgets/2026-11", { body });
  });

  it("deletes a month", async () => {
    await deleteBudget("2026-11");
    expect(request).toHaveBeenCalledWith("DELETE", "/budgets/2026-11");
  });
});

describe("goals api", () => {
  it("lists, creates, updates and deletes goals", async () => {
    await listGoals();
    await createGoal({ name: "Car", target_amount_minor: 100 });
    await updateGoal("g1", { status: "PAUSED", target_date: null });
    await deleteGoal("g1");
    expect(request).toHaveBeenNthCalledWith(1, "GET", "/goals");
    expect(request).toHaveBeenNthCalledWith(2, "POST", "/goals", { body: { name: "Car", target_amount_minor: 100 } });
    expect(request).toHaveBeenNthCalledWith(3, "PATCH", "/goals/g1", { body: { status: "PAUSED", target_date: null } });
    expect(request).toHaveBeenNthCalledWith(4, "DELETE", "/goals/g1");
  });
});

describe("recurring api", () => {
  it("lists, creates, updates, advances and deletes bills", async () => {
    const body = {
      merchant_name: "Netflix",
      category_id: "sub",
      expected_amount_minor: 49900,
      frequency: "MONTHLY" as const,
      next_expected_date: "2026-12-05",
      is_mandatory: false,
    };
    await listRecurring();
    await createRecurring(body);
    await updateRecurring("r1", { is_active: false });
    await advanceRecurring("r1");
    await deleteRecurring("r1");
    expect(request).toHaveBeenNthCalledWith(1, "GET", "/recurring");
    expect(request).toHaveBeenNthCalledWith(2, "POST", "/recurring", { body });
    expect(request).toHaveBeenNthCalledWith(3, "PATCH", "/recurring/r1", { body: { is_active: false } });
    expect(request).toHaveBeenNthCalledWith(4, "POST", "/recurring/r1/advance");
    expect(request).toHaveBeenNthCalledWith(5, "DELETE", "/recurring/r1");
  });
});

describe("tax api", () => {
  it("passes the financial year as a query parameter", async () => {
    await getTaxSummary(2026);
    expect(request).toHaveBeenCalledWith("GET", "/tax/summary?fy=2026");
  });

  it("omits the query when no year is given", async () => {
    await getTaxSummary();
    expect(request).toHaveBeenCalledWith("GET", "/tax/summary");
  });
});
