import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { AuthContext, type AuthContextValue } from "./AuthProvider";
import { SetupScreen } from "./SetupScreen";

function renderSetup(setUp: AuthContextValue["setUp"]) {
  const value: AuthContextValue = {
    status: "setup",
    setUp,
    signIn: vi.fn(),
    signOut: vi.fn(),
    retry: vi.fn(),
  };
  return render(
    <AuthContext.Provider value={value}>
      <SetupScreen />
    </AuthContext.Provider>,
  );
}

describe("SetupScreen", () => {
  it("sends the setup code and shows 'That setup code is not correct.' beside the field for INVALID_SETUP_TOKEN", async () => {
    const setUp = vi.fn(() => Promise.reject(new ApiError(403, "INVALID_SETUP_TOKEN", "Invalid setup token.")));
    renderSetup(setUp);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Password"), "correct-horse-battery");
    await user.type(screen.getByLabelText("Confirm password"), "correct-horse-battery");
    await user.type(screen.getByLabelText("Setup Code"), "wrong-code");
    await user.click(screen.getByRole("button", { name: "Finish Setup" }));

    expect(setUp).toHaveBeenCalledWith("correct-horse-battery", "Web browser", "wrong-code");
    const codeField = screen.getByLabelText("Setup Code");
    expect(codeField.getAttribute("aria-invalid")).toBe("true");
    expect(codeField.getAttribute("autocomplete")).toBe("off");
    expect((await screen.findByRole("alert")).textContent).toBe("That setup code is not correct.");
  });
});
