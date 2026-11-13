import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createGoal, deleteGoal, listGoals, updateGoal, type Goal } from "../../api/goals";
import { installDialogStub } from "../transactions/testDialog";
import { GoalsSection } from "./GoalsSection";

vi.mock("../../api/goals", () => ({
  listGoals: vi.fn(),
  createGoal: vi.fn(),
  updateGoal: vi.fn(),
  deleteGoal: vi.fn(),
}));

function goalFixture(overrides: Partial<Goal> & Pick<Goal, "id" | "name">): Goal {
  return {
    linked_account_id: null,
    target_amount_minor: 30000000,
    current_locked_amount_minor: 1500000,
    monthly_contribution_minor: 200000,
    target_date: null,
    priority: 1,
    status: "ACTIVE",
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

const goals: Goal[] = [
  goalFixture({ id: "g1", name: "Emergency fund", target_date: "2027-03-31" }),
  goalFixture({ id: "g2", name: "Holiday", status: "PAUSED", target_amount_minor: 10000000, current_locked_amount_minor: 0 }),
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

describe("GoalsSection", () => {
  it("shows set-aside money against the target, a progress bar, target date and status words", async () => {
    vi.mocked(listGoals).mockResolvedValue(goals);
    render(<GoalsSection />);

    expect(await screen.findByText("Emergency fund")).toBeTruthy();
    expect(screen.getByText("Money set aside for active goals is held back from Safe to Spend.")).toBeTruthy();
    expect(within(rowOf("Emergency fund")).getByText("₹15,000.00 of ₹3,00,000.00")).toBeTruthy();
    expect(within(rowOf("Emergency fund")).getByText("Target 31 Mar 2027")).toBeTruthy();
    expect(within(rowOf("Emergency fund")).getByRole("progressbar", { name: "Emergency fund set aside" })).toBeTruthy();
    expect(within(rowOf("Holiday")).getByText("Paused")).toBeTruthy();
  });

  it("shows each goal's priority as text", async () => {
    vi.mocked(listGoals).mockResolvedValue([goalFixture({ id: "g9", name: "Bike", priority: 3 })]);
    render(<GoalsSection />);

    await screen.findByText("Bike");

    expect(within(rowOf("Bike")).getByText("Priority 3")).toBeTruthy();
  });

  it("sends the chosen priority when adding and editing, and rejects values outside 1 to 99", async () => {
    const user = userEvent.setup();
    vi.mocked(listGoals).mockResolvedValue(goals);
    vi.mocked(updateGoal).mockResolvedValue(goalFixture({ id: "g1", name: "Emergency fund", priority: 7 }));
    render(<GoalsSection />);
    await screen.findByText("Emergency fund");

    await user.click(within(rowOf("Emergency fund")).getByRole("button", { name: "Edit" }));
    const dialog = screen.getByRole("dialog", { name: "Edit Goal" });
    const priority = within(dialog).getByLabelText("Priority (1 to 99)") as HTMLInputElement;
    expect(priority.value).toBe("1");
    await user.clear(priority);
    await user.type(priority, "100");
    await user.click(within(dialog).getByRole("button", { name: "Save Goal" }));
    expect(await within(dialog).findByText("Enter a whole number from 1 to 99.")).toBeTruthy();
    expect(updateGoal).not.toHaveBeenCalled();

    await user.clear(priority);
    await user.type(priority, "7");
    await user.click(within(dialog).getByRole("button", { name: "Save Goal" }));

    await waitFor(() => expect(updateGoal).toHaveBeenCalledWith("g1", expect.objectContaining({ priority: 7 })));
    expect(await screen.findByText("Priority 7")).toBeTruthy();
  });

  it("offers to add a goal when there are none", async () => {
    vi.mocked(listGoals).mockResolvedValue([]);
    render(<GoalsSection />);

    expect(await screen.findByText("No goals yet. Add a goal to start setting money aside for it.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Add Goal" })).toBeTruthy();
  });

  it("shows an error with a retry", async () => {
    const user = userEvent.setup();
    vi.mocked(listGoals).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(goals);
    render(<GoalsSection />);

    expect(await screen.findByText("Could not load your goals. Check your connection and try again.")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Try Again" }));
    expect(await screen.findByText("Holiday")).toBeTruthy();
  });

  it("adds a goal with paise amounts, blank amounts as zero and no target date", async () => {
    const user = userEvent.setup();
    vi.mocked(listGoals).mockResolvedValue([]);
    vi.mocked(createGoal).mockResolvedValue(goalFixture({ id: "g3", name: "Car" }));
    render(<GoalsSection />);
    await user.click(await screen.findByRole("button", { name: "Add Goal" }));

    const dialog = screen.getByRole("dialog", { name: "Add Goal" });
    await user.type(within(dialog).getByLabelText("Name"), "Car");
    await user.type(within(dialog).getByLabelText("Target amount (₹)"), "500000");
    await user.type(within(dialog).getByLabelText("Monthly contribution (₹)"), "10000");
    await user.click(within(dialog).getByRole("button", { name: "Add Goal" }));

    await waitFor(() =>
      expect(createGoal).toHaveBeenCalledWith({
        name: "Car",
        target_amount_minor: 50000000,
        current_locked_amount_minor: 0,
        monthly_contribution_minor: 1000000,
        priority: 1,
      }),
    );
    expect(await screen.findByText("Car")).toBeTruthy();
  });

  it("blocks saving when the amount set aside is more than the target", async () => {
    const user = userEvent.setup();
    vi.mocked(listGoals).mockResolvedValue([]);
    render(<GoalsSection />);
    await user.click(await screen.findByRole("button", { name: "Add Goal" }));

    const dialog = screen.getByRole("dialog", { name: "Add Goal" });
    await user.type(within(dialog).getByLabelText("Name"), "Car");
    await user.type(within(dialog).getByLabelText("Target amount (₹)"), "3000");
    await user.type(within(dialog).getByLabelText("Amount set aside (₹)"), "4000");
    await user.click(within(dialog).getByRole("button", { name: "Add Goal" }));

    expect(await within(dialog).findByText(/Amount set aside cannot be more than the target/)).toBeTruthy();
    expect(createGoal).not.toHaveBeenCalled();
  });

  it("edits a goal and sends the new status and cleared date in the PATCH body", async () => {
    const user = userEvent.setup();
    vi.mocked(listGoals).mockResolvedValue(goals);
    vi.mocked(updateGoal).mockResolvedValue(goalFixture({ id: "g1", name: "Emergency fund", status: "PAUSED" }));
    render(<GoalsSection />);
    await screen.findByText("Emergency fund");

    await user.click(within(rowOf("Emergency fund")).getByRole("button", { name: "Edit" }));
    const dialog = screen.getByRole("dialog", { name: "Edit Goal" });
    expect((within(dialog).getByLabelText("Target amount (₹)") as HTMLInputElement).value).toBe("300000.00");
    fireEvent.change(within(dialog).getByLabelText("Target date"), { target: { value: "" } });
    await user.selectOptions(within(dialog).getByLabelText("Status"), "PAUSED");
    await user.click(within(dialog).getByRole("button", { name: "Save Goal" }));

    await waitFor(() =>
      expect(updateGoal).toHaveBeenCalledWith("g1", {
        name: "Emergency fund",
        target_amount_minor: 30000000,
        current_locked_amount_minor: 1500000,
        monthly_contribution_minor: 200000,
        target_date: null,
        priority: 1,
        status: "PAUSED",
      }),
    );
  });

  it("Delete asks for a second click in place before removing the goal", async () => {
    const user = userEvent.setup();
    vi.mocked(listGoals).mockResolvedValue(goals);
    vi.mocked(deleteGoal).mockResolvedValue();
    render(<GoalsSection />);
    await screen.findByText("Holiday");

    await user.click(within(rowOf("Holiday")).getByRole("button", { name: "Delete" }));
    expect(deleteGoal).not.toHaveBeenCalled();
    await user.click(within(rowOf("Holiday")).getByRole("button", { name: "Confirm Delete" }));

    await waitFor(() => expect(deleteGoal).toHaveBeenCalledWith("g2"));
    await waitFor(() => expect(screen.queryByText("Holiday")).toBeNull());
  });
});
