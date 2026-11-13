import { describe, expect, it } from "vitest";
import { ApiError } from "../../api/client";
import { messageFor, minorToRupeesText } from "./format";

describe("minorToRupeesText", () => {
  it.each([
    [0, "0.00"],
    [7, "0.07"],
    [10, "0.10"],
    [150, "1.50"],
    [1200050, "12000.50"],
    [123456789, "1234567.89"],
  ])("writes %i paise as %j", (minor, expected) => {
    expect(minorToRupeesText(minor)).toBe(expected);
  });

  it("keeps the minus sign in front of negative amounts", () => {
    expect(minorToRupeesText(-150)).toBe("-1.50");
    expect(minorToRupeesText(-5)).toBe("-0.05");
    expect(minorToRupeesText(-1200050)).toBe("-12000.50");
  });

  it("writes the exact value for amounts near the safe-integer limit", () => {
    expect(minorToRupeesText(Number.MAX_SAFE_INTEGER)).toBe("90071992547409.91");
    expect(minorToRupeesText(-Number.MAX_SAFE_INTEGER)).toBe("-90071992547409.91");
  });

  it("rejects values that are not safe integers", () => {
    expect(() => minorToRupeesText(1.5)).toThrow(RangeError);
    expect(() => minorToRupeesText(Number.MAX_SAFE_INTEGER + 1)).toThrow(RangeError);
  });
});

describe("messageFor", () => {
  it("returns the API message for an ApiError", () => {
    expect(messageFor(new ApiError(409, "CONFLICT", "Already committed"))).toBe("Already committed");
  });

  it("returns a generic message for any other error", () => {
    expect(messageFor(new Error("socket hang up"))).toBe("Something went wrong. Try again.");
  });
});
