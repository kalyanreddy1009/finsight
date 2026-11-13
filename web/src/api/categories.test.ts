import { beforeEach, describe, expect, it, vi } from "vitest";
import { request } from "./client";
import { createCategory, listCategories, type CategoryBody } from "./categories";

vi.mock("./client", () => ({ request: vi.fn() }));

const requestMock = vi.mocked(request);

describe("categories API", () => {
  beforeEach(() => {
    requestMock.mockReset();
  });

  it("lists categories with a GET to /categories", async () => {
    requestMock.mockResolvedValue({ data: [{ id: "c1", name: "Food" }], meta: null });

    const categories = await listCategories();

    expect(requestMock).toHaveBeenCalledWith("GET", "/categories");
    expect(categories).toEqual([{ id: "c1", name: "Food" }]);
  });

  it("creates a category with a POST to /categories and sends the body unchanged", async () => {
    const body: CategoryBody = {
      name: "Rent",
      category_type: "EXPENSE",
      default_tax_section: "NONE",
      is_discretionary: false,
      is_sensitive_private: false,
    };
    requestMock.mockResolvedValue({ data: { id: "c2", ...body }, meta: null });

    const created = await createCategory(body);

    expect(requestMock).toHaveBeenCalledWith("POST", "/categories", { body });
    expect(created.id).toBe("c2");
  });
});
