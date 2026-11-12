import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
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
});
