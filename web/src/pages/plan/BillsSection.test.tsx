import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  advanceRecurring,
  createRecurring,
  deleteRecurring,
  listRecurring,
  updateRecurring,
  type RecurringRule,
} from "../../api/recurring";
import type { Category } from "../../api/types";
import { installDialogStub } from "../transactions/testDialog";
import { BillsSection } from "./BillsSection";

vi.mock("../../api/recurring", () => ({
  listRecurring: vi.fn(),
  createRecurring: vi.fn(),
  updateRecurring: vi.fn(),
  advanceRecurring: vi.fn(),
  deleteRecurring: vi.fn(),
}));

const categories: Category[] = [
  {
    id: "food",
    name: "Food",
    parent_category_id: null,
    category_type: "EXPENSE",
    default_tax_section: "NONE",
    is_discretionary: true,
    is_sensitive_private: false,
    is_system_category: false,
    created_at: "2026-01-01T00:00:00Z",
  },
];

function ruleFixture(overrides: Partial<RecurringRule> & Pick<RecurringRule, "id" | "merchant_name">): RecurringRule {
  return {
    merchant_id: `m-${overrides.id}`,
    category_id: "food",
    category_name: "Food",
    account_id: null,
    expected_amount_minor: 49900,
    frequency: "MONTHLY",
    next_expected_date: "2026-12-05",
    is_mandatory: true,
    is_active: true,
    ...overrides,
  };
}

const rules: RecurringRule[] = [
  ruleFixture({ id: "netflix", merchant_name: "Netflix", next_expected_date: "2026-12-05" }),
  ruleFixture({ id: "insurance", merchant_name: "Insurance", expected_amount_minor: 1200000, frequency: "YEARLY", next_expected_date: "2026-11-20" }),
  ruleFixture({ id: "gym", merchant_name: "Gym", expected_amount_minor: 150000, next_expected_date: "2026-11-18", is_mandatory: false }),
  ruleFixture({ id: "magazine", merchant_name: "Magazine", next_expected_date: "2026-11-01", is_mandatory: false, is_active: false }),
];

beforeEach(() => {
  installDialogStub();
  vi.resetAllMocks();
});

function rowOf(title: string): HTMLElement {
  const row = screen.getByText(title).closest("li");
  expect(row).not.toBeNull();
  return row as HTMLElement;
}

describe("BillsSection", () => {
  it("lists bills by next due date with amount, frequency, due date and an Optional tag", async () => {
    vi.mocked(listRecurring).mockResolvedValue(rules);
    const { container } = render(<BillsSection categories={categories} />);

    await screen.findByText("Netflix");
    const titles = Array.from(container.querySelectorAll(".row-title")).map((node) => node.textContent);
    expect(titles.slice(0, 3)).toEqual(["Gym", "Insurance", "Netflix"]);
    expect(screen.getByText("₹499.00 · Monthly · Due 5 Dec 2026")).toBeTruthy();
    expect(screen.getByText("₹12,000.00 · Yearly · Due 20 Nov 2026")).toBeTruthy();
    expect(within(rowOf("Gym")).getByText("Optional")).toBeTruthy();
    expect(within(rowOf("Netflix")).queryByText("Optional")).toBeNull();
  });

  it("edits a bill with a prefilled form and sends only the editable fields in the PATCH", async () => {
    const user = userEvent.setup();
    vi.mocked(listRecurring).mockResolvedValue(rules);
    vi.mocked(updateRecurring).mockResolvedValue(
      ruleFixture({ id: "netflix", merchant_name: "Netflix", expected_amount_minor: 64900, next_expected_date: "2026-12-05" }),
    );
    render(<BillsSection categories={categories} />);
    await screen.findByText("Netflix");

    await user.click(within(rowOf("Netflix")).getByRole("button", { name: "Edit" }));
    const dialog = screen.getByRole("dialog", { name: "Edit Bill" });
    const merchant = within(dialog).getByLabelText("Merchant") as HTMLInputElement;
    expect(merchant.value).toBe("Netflix");
    expect(merchant.disabled).toBe(true);
    const amount = within(dialog).getByLabelText("Amount (₹)") as HTMLInputElement;
    expect(amount.value).toBe("499.00");
    await user.clear(amount);
    await user.type(amount, "649");
    await user.click(within(dialog).getByRole("button", { name: "Save Bill" }));

    await waitFor(() =>
      expect(updateRecurring).toHaveBeenCalledWith("netflix", {
        expected_amount_minor: 64900,
        frequency: "MONTHLY",
        next_expected_date: "2026-12-05",
        is_mandatory: true,
        category_id: "food",
      }),
    );
    expect(await screen.findByText("₹649.00 · Monthly · Due 5 Dec 2026")).toBeTruthy();
    expect(screen.queryByRole("dialog", { name: "Edit Bill" })).toBeNull();
  });

  it("keeps the Edit Bill title while the dialog closes", async () => {
    const user = userEvent.setup();
    vi.mocked(listRecurring).mockResolvedValue(rules);
    render(<BillsSection categories={categories} />);
    await screen.findByText("Netflix");

    await user.click(within(rowOf("Netflix")).getByRole("button", { name: "Edit" }));
    const dialog = screen.getByRole("dialog", { name: "Edit Bill" });
    await user.click(within(dialog).getByRole("button", { name: "Close" }));

    expect(dialog.querySelector(".dialog-title")?.textContent).toBe("Edit Bill");
  });

  it("shows the server error and keeps the edit dialog open when saving fails", async () => {
    const user = userEvent.setup();
    vi.mocked(listRecurring).mockResolvedValue(rules);
    vi.mocked(updateRecurring).mockRejectedValue(new Error("offline"));
    render(<BillsSection categories={categories} />);
    await screen.findByText("Netflix");

    await user.click(within(rowOf("Netflix")).getByRole("button", { name: "Edit" }));
    const dialog = screen.getByRole("dialog", { name: "Edit Bill" });
    await user.click(within(dialog).getByRole("button", { name: "Save Bill" }));

    expect(await within(dialog).findByText("Could not save. Try again.")).toBeTruthy();
  });

  it("puts inactive bills under a Paused heading", async () => {
    vi.mocked(listRecurring).mockResolvedValue(rules);
    render(<BillsSection categories={categories} />);

    const pausedHeading = await screen.findByRole("heading", { name: "Paused" });
    const pausedGroup = pausedHeading.closest("section") as HTMLElement;
    expect(within(pausedGroup).getByText("Magazine")).toBeTruthy();
    expect(within(pausedGroup).getByRole("button", { name: "Resume" })).toBeTruthy();
  });

  it("offers to add a bill when there are none", async () => {
    vi.mocked(listRecurring).mockResolvedValue([]);
    render(<BillsSection categories={categories} />);

    expect(await screen.findByText("No recurring bills yet. Add a bill to see what is due next.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Add Bill" })).toBeTruthy();
  });

  it("shows an error with a retry", async () => {
    const user = userEvent.setup();
    vi.mocked(listRecurring).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(rules);
    render(<BillsSection categories={categories} />);

    expect(await screen.findByText("Could not load your bills. Check your connection and try again.")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Try Again" }));
    expect(await screen.findByText("Netflix")).toBeTruthy();
  });

  it("adds a bill with the body converted to paise and shows it in the list", async () => {
    const user = userEvent.setup();
    vi.mocked(listRecurring).mockResolvedValue(rules);
    vi.mocked(createRecurring).mockResolvedValue(ruleFixture({ id: "power", merchant_name: "Electricity", expected_amount_minor: 125050 }));
    render(<BillsSection categories={categories} />);
    await user.click(await screen.findByRole("button", { name: "Add Bill" }));

    const dialog = screen.getByRole("dialog", { name: "Add Bill" });
    await user.type(within(dialog).getByLabelText("Merchant"), "  Electricity ");
    await user.type(within(dialog).getByLabelText("Amount (₹)"), "1,250.50");
    await user.selectOptions(within(dialog).getByLabelText("Category"), "food");
    fireEvent.change(within(dialog).getByLabelText("Next due date"), { target: { value: "2026-12-01" } });
    await user.click(within(dialog).getByLabelText("Mandatory"));
    await user.click(within(dialog).getByRole("button", { name: "Add Bill" }));

    await waitFor(() =>
      expect(createRecurring).toHaveBeenCalledWith({
        merchant_name: "Electricity",
        category_id: "food",
        expected_amount_minor: 125050,
        frequency: "MONTHLY",
        next_expected_date: "2026-12-01",
        is_mandatory: false,
      }),
    );
    expect(await screen.findByText("Electricity")).toBeTruthy();
  });

  it("Mark Paid calls advance and moves the row to its next date", async () => {
    const user = userEvent.setup();
    vi.mocked(listRecurring).mockResolvedValue(rules);
    vi.mocked(advanceRecurring).mockResolvedValue(ruleFixture({ id: "gym", merchant_name: "Gym", expected_amount_minor: 150000, next_expected_date: "2026-12-18", is_mandatory: false }));
    render(<BillsSection categories={categories} />);
    await screen.findByText("Gym");

    await user.click(within(rowOf("Gym")).getByRole("button", { name: "Mark Paid" }));

    expect(advanceRecurring).toHaveBeenCalledWith("gym");
    expect(await within(rowOf("Gym")).findByText(/Due 18 Dec 2026/)).toBeTruthy();
  });

  it("Pause sends is_active false and Resume sends it back", async () => {
    const user = userEvent.setup();
    vi.mocked(listRecurring).mockResolvedValue(rules);
    vi.mocked(updateRecurring)
      .mockResolvedValueOnce(ruleFixture({ id: "gym", merchant_name: "Gym", next_expected_date: "2026-11-18", is_mandatory: false, is_active: false }))
      .mockResolvedValueOnce(ruleFixture({ id: "gym", merchant_name: "Gym", next_expected_date: "2026-11-18", is_mandatory: false, is_active: true }));
    render(<BillsSection categories={categories} />);
    await screen.findByText("Gym");

    await user.click(within(rowOf("Gym")).getByRole("button", { name: "Pause" }));
    expect(updateRecurring).toHaveBeenLastCalledWith("gym", { is_active: false });
    expect(await within(rowOf("Gym")).findByRole("button", { name: "Resume" })).toBeTruthy();

    await user.click(within(rowOf("Gym")).getByRole("button", { name: "Resume" }));
    expect(updateRecurring).toHaveBeenLastCalledWith("gym", { is_active: true });
  });

  it("Delete asks for a second click in place before removing the bill", async () => {
    const user = userEvent.setup();
    vi.mocked(listRecurring).mockResolvedValue(rules);
    vi.mocked(deleteRecurring).mockResolvedValue();
    render(<BillsSection categories={categories} />);
    await screen.findByText("Gym");

    await user.click(within(rowOf("Gym")).getByRole("button", { name: "Delete" }));
    const confirm = within(rowOf("Gym")).getByRole("group", { name: "Delete Gym?" });
    expect(deleteRecurring).not.toHaveBeenCalled();

    await user.click(within(confirm).getByRole("button", { name: "Confirm Delete" }));
    await waitFor(() => expect(deleteRecurring).toHaveBeenCalledWith("gym"));
    await waitFor(() => expect(screen.queryByText("Gym")).toBeNull());
  });
});
