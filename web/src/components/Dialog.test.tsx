import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { installDialogStub } from "../pages/transactions/testDialog";
import { Dialog } from "./Dialog";

function Harness() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Open sample
      </button>
      <Dialog open={open} title="Sample" onClose={() => setOpen(false)}>
        <p>Dialog body</p>
      </Dialog>
    </>
  );
}

describe("Dialog", () => {
  it("is labelled by its heading and returns focus to the opener when closed", async () => {
    installDialogStub();
    const user = userEvent.setup();
    render(<Harness />);
    const opener = screen.getByRole("button", { name: "Open sample" });

    await user.click(opener);
    expect(screen.getByRole("dialog", { name: "Sample" })).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog", { name: "Sample" })).toBeNull();
    expect(document.activeElement).toBe(opener);
  });

  it("ignores Escape and disables Close while busy, then allows both again when the save ends", () => {
    installDialogStub();
    const onClose = vi.fn();
    const { rerender } = render(
      <Dialog open title="Saving" busy onClose={onClose}>
        <p>Form body</p>
      </Dialog>,
    );
    const dialog = screen.getByRole("dialog", { name: "Saving" });

    expect(screen.getByRole("button", { name: "Close" }).hasAttribute("disabled")).toBe(true);
    expect(fireEvent(dialog, new Event("cancel", { cancelable: true }))).toBe(false);

    rerender(
      <Dialog open title="Saving" busy={false} onClose={onClose}>
        <p>Form body</p>
      </Dialog>,
    );
    expect(screen.getByRole("button", { name: "Close" }).hasAttribute("disabled")).toBe(false);
    expect(fireEvent(dialog, new Event("cancel", { cancelable: true }))).toBe(true);
    expect(onClose).not.toHaveBeenCalled();
  });
});
