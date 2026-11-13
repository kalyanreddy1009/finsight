import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RouteErrorBoundary } from "./RouteErrorBoundary";

function BrokenPage(): never {
  throw new Error("Failed to fetch dynamically imported module");
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("RouteErrorBoundary", () => {
  it("shows the message and a Try Again button when a child throws", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    render(
      <RouteErrorBoundary>
        <BrokenPage />
      </RouteErrorBoundary>,
    );

    expect(screen.getByText("This page could not load. Check your connection and try again.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try Again" })).toBeTruthy();
  });

  it("reloads the page when Try Again is clicked", async () => {
    const user = userEvent.setup();
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const reload = vi.fn();
    const originalLocation = window.location;
    Object.defineProperty(window, "location", { value: { ...originalLocation, reload }, configurable: true });
    try {
      render(
        <RouteErrorBoundary>
          <BrokenPage />
        </RouteErrorBoundary>,
      );

      await user.click(screen.getByRole("button", { name: "Try Again" }));

      expect(reload).toHaveBeenCalledTimes(1);
    } finally {
      Object.defineProperty(window, "location", { value: originalLocation, configurable: true });
    }
  });

  it("renders the children when nothing throws", () => {
    render(
      <RouteErrorBoundary>
        <p>Page content</p>
      </RouteErrorBoundary>,
    );

    expect(screen.getByText("Page content")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Try Again" })).toBeNull();
  });
});
