import { describe, expect, it } from "vitest";
import { makeCategory } from "../pages/transactions/testFixtures";
import { categoryOptionsFor } from "./categoryOptions";

describe("categoryOptionsFor", () => {
  it("suffixes the type only on names shared by both types", () => {
    const options = categoryOptionsFor([
      makeCategory({ id: "a", name: "Other", category_type: "EXPENSE" }),
      makeCategory({ id: "b", name: "Other", category_type: "INCOME" }),
      makeCategory({ id: "c", name: "Rent", category_type: "EXPENSE" }),
    ]);

    expect(options).toEqual([
      { value: "a", label: "Other (Spending)" },
      { value: "b", label: "Other (Income)" },
      { value: "c", label: "Rent" },
    ]);
  });
});
