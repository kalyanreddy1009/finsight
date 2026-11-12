import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createCategory, listCategories } from "../../api/categories";
import type { Category } from "../../api/types";
import { installDialogStub } from "../transactions/testDialog";
import { PlanPage } from "./PlanPage";

vi.mock("../../api/categories", () => ({ listCategories: vi.fn(), createCategory: vi.fn() }));

function categoryFixture(overrides: Partial<Category> & Pick<Category, "id" | "name">): Category {
  return {
    parent_category_id: null,
    category_type: "EXPENSE",
    default_tax_section: "NONE",
    is_discretionary: true,
    is_sensitive_private: false,
    is_system_category: false,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

const categories: Category[] = [
  categoryFixture({ id: "c1", name: "Groceries", default_tax_section: "80C", is_discretionary: false, is_sensitive_private: true }),
  categoryFixture({ id: "c2", name: "Uncategorized", is_system_category: true }),
  categoryFixture({ id: "c3", name: "Salary", category_type: "INCOME" }),
];

beforeEach(() => {
  installDialogStub();
  vi.resetAllMocks();
});

function groupOf(heading: string): HTMLElement {
  const section = screen.getByRole("heading", { name: heading }).closest("section");
  expect(section).not.toBeNull();
  return section as HTMLElement;
}

describe("PlanPage categories", () => {
  it("lists categories grouped under Spending and Income with their secondary facts", async () => {
    vi.mocked(listCategories).mockResolvedValue(categories);
    render(<PlanPage />);
    await screen.findByText("Groceries");

    const spending = groupOf("Spending");
    expect(within(spending).getByText("Groceries")).toBeTruthy();
    expect(within(spending).getByText("Tax 80C · Essential · Private")).toBeTruthy();
    expect(within(spending).getByText("Built in")).toBeTruthy();
    expect(within(groupOf("Income")).getByText("Salary")).toBeTruthy();
    expect(screen.getByText("Budgets, recurring bills and goals are not available yet.")).toBeTruthy();
  });

  it("submits is_discretionary false when Essential spending is checked", async () => {
    const user = userEvent.setup();
    vi.mocked(listCategories).mockResolvedValue([]);
    vi.mocked(createCategory).mockResolvedValue(categoryFixture({ id: "c9", name: "Gym" }));
    render(<PlanPage />);

    await user.click(await screen.findByRole("button", { name: "Add Category" }));
    const dialog = screen.getByRole("dialog", { name: "Add Category" });
    await user.type(within(dialog).getByLabelText("Name"), "  Gym  ");
    await user.click(within(dialog).getByLabelText("Essential spending"));
    await user.click(within(dialog).getByRole("button", { name: "Add Category" }));

    await waitFor(() =>
      expect(createCategory).toHaveBeenCalledWith({
        name: "Gym",
        category_type: "EXPENSE",
        default_tax_section: "NONE",
        is_discretionary: false,
        is_sensitive_private: false,
      }),
    );
  });

  it("asks for a name before submitting", async () => {
    const user = userEvent.setup();
    vi.mocked(listCategories).mockResolvedValue([]);
    render(<PlanPage />);

    await user.click(await screen.findByRole("button", { name: "Add Category" }));
    const dialog = screen.getByRole("dialog", { name: "Add Category" });
    await user.click(within(dialog).getByRole("button", { name: "Add Category" }));

    expect(within(dialog).getByText("Enter a name for the category.")).toBeTruthy();
    expect(createCategory).not.toHaveBeenCalled();
  });
});
