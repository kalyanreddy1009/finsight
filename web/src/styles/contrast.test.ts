import { describe, expect, it } from "vitest";
import tokensCss from "./tokens.css?raw";

const DARK_MARKER = "@media (prefers-color-scheme: dark)";
const HEX_DECLARATION = /--([a-z-]+):\s*(#[0-9A-Fa-f]{6})\s*;/g;
const MIN_TEXT_RATIO = 4.5;

const darkStart = tokensCss.indexOf(DARK_MARKER);
const lightBlock = tokensCss.slice(0, darkStart);
const darkBlock = tokensCss.slice(darkStart);

function parseTokens(block: string): Map<string, string> {
  return new Map(Array.from(block.matchAll(HEX_DECLARATION), (match) => [match[1] ?? "", match[2] ?? ""]));
}

function tokenValue(tokens: Map<string, string>, name: string): string {
  const value = tokens.get(name);
  if (value === undefined) {
    throw new Error(`Missing token --${name}`);
  }
  return value;
}

function channelLuminance(channel: number): number {
  const srgb = channel / 255;
  return srgb <= 0.03928 ? srgb / 12.92 : ((srgb + 0.055) / 1.055) ** 2.4;
}

export function relativeLuminance(hex: string): number {
  const red = channelLuminance(parseInt(hex.slice(1, 3), 16));
  const green = channelLuminance(parseInt(hex.slice(3, 5), 16));
  const blue = channelLuminance(parseInt(hex.slice(5, 7), 16));
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

export function contrastRatio(first: string, second: string): number {
  const a = relativeLuminance(first);
  const b = relativeLuminance(second);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

const THEMES = {
  light: parseTokens(lightBlock),
  dark: parseTokens(darkBlock),
} as const;

const TEXT_ROLES = ["text", "text-secondary", "accent", "positive", "negative", "warning"] as const;
const SURFACE_ROLES = ["surface", "surface-grouped"] as const;

describe("design token contrast (WCAG 2.x, computed from token values)", () => {
  for (const [theme, tokens] of Object.entries(THEMES)) {
    for (const surface of SURFACE_ROLES) {
      for (const role of TEXT_ROLES) {
        it(`${theme}: --${role} on --${surface} is at least ${MIN_TEXT_RATIO}:1`, () => {
          const ratio = contrastRatio(tokenValue(tokens, role), tokenValue(tokens, surface));
          expect(ratio).toBeGreaterThanOrEqual(MIN_TEXT_RATIO);
        });
      }
    }
    it(`${theme}: --on-accent on --accent is at least ${MIN_TEXT_RATIO}:1`, () => {
      const ratio = contrastRatio(tokenValue(tokens, "on-accent"), tokenValue(tokens, "accent"));
      expect(ratio).toBeGreaterThanOrEqual(MIN_TEXT_RATIO);
    });
  }

  it("declares both themes with the same token names", () => {
    expect([...THEMES.dark.keys()].sort()).toEqual([...THEMES.light.keys()].sort());
  });
});
