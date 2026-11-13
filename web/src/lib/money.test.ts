import { describe, expect, it } from "vitest";
import { MAX_RUPEES, formatMinor, parseRupeesToMinor } from "./money";

describe("parseRupeesToMinor", () => {
  it.each([
    ["1234", 123400],
    ["1,234.5", 123450],
    ["1234.50", 123450],
    ["1234.5", 123450],
    ["0.07", 7],
    ["0.1", 10],
    ["1234567.89", 123456789],
    ["0", 0],
    ["₹1,234", 123400],
    ["₹ 1234.00", 123400],
    ["  ₹1,23,456.50  ", 12345650],
    ["12,34,567", 123456700],
    ["00012", 1200],
    ["10000000000000", MAX_RUPEES * 100],
  ])("parses %j to %i paise", (input, expected) => {
    expect(parseRupeesToMinor(input)).toBe(expected);
  });

  it.each([
    ["more than two decimals", "12.345"],
    ["three decimals with zeros", "1.000"],
    ["negative", "-5"],
    ["negative with rupee sign", "₹-5"],
    ["unicode minus", "−5"],
    ["empty", ""],
    ["only spaces", "   "],
    ["only rupee sign", "₹"],
    ["trailing dot", "1234."],
    ["trailing dot on a small amount", "12."],
    ["leading dot with no whole rupees", ".5"],
    ["letters", "12a"],
    ["exponent", "1e3"],
    ["misplaced grouping", "1,2345"],
    ["grouping in the decimals", "1,234.5,6"],
    ["space inside the number", "1 234"],
    ["above 10^13 rupees", "10000000000001"],
    ["far above the limit", "99999999999999999"],
  ])("rejects %s (%j)", (_label, input) => {
    expect(parseRupeesToMinor(input)).toBeNull();
  });
});

describe("formatMinor", () => {
  it.each([
    [12345650, "₹1,23,456.50"],
    [0, "₹0.00"],
    [5, "₹0.05"],
    [100, "₹1.00"],
    [99, "₹0.99"],
    [123400, "₹1,234.00"],
    [1234567 * 100, "₹12,34,567.00"],
    [1_000_000_000, "₹1,00,00,000.00"],
    [100_000_000, "₹10,00,000.00"],
    [-50000, "−₹500.00"],
    [-1, "−₹0.01"],
  ])("formats %i paise as %j", (minor, expected) => {
    expect(formatMinor(minor)).toBe(expected);
  });

  it("adds a plus sign for positive amounts only when asked", () => {
    expect(formatMinor(50000, { sign: true })).toBe("+₹500.00");
    expect(formatMinor(-50000, { sign: true })).toBe("−₹500.00");
    expect(formatMinor(0, { sign: true })).toBe("₹0.00");
  });

  it("rejects values that are not safe integers", () => {
    expect(() => formatMinor(1.5)).toThrow(RangeError);
    expect(() => formatMinor(Number.MAX_SAFE_INTEGER + 1)).toThrow(RangeError);
  });

  it("round-trips with parseRupeesToMinor", () => {
    const minor = 987654321;
    const text = formatMinor(minor).replace("−", "").replace("₹", "");
    expect(parseRupeesToMinor(text)).toBe(minor);
  });
});
