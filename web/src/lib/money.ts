// Money is integer paise everywhere. Parsing and formatting use string and BigInt math only.

export const MAX_RUPEES = 10 ** 13;
const MAX_WHOLE_RUPEE_DIGITS = 14;
const RUPEE_SIGN = "₹";
const MINUS_SIGN = "−";
const PAISE_PER_RUPEE = 100n;
const MAX_RUPEES_BIG = BigInt(MAX_RUPEES);

// Optional leading ₹ and spaces, Western or Indian comma grouping, at most 2 decimals. No sign.
const RUPEE_INPUT = /^₹?\s*(\d+|\d{1,3}(?:,\d{2,3})+)(?:\.(\d{1,2}))?$/;

export interface FormatOptions {
  sign?: boolean;
}

export function parseRupeesToMinor(input: string): number | null {
  const match = RUPEE_INPUT.exec(input.trim());
  if (match === null) {
    return null;
  }
  const wholeDigits = (match[1] ?? "").replaceAll(",", "").replace(/^0+(?=\d)/, "");
  if (wholeDigits.length > MAX_WHOLE_RUPEE_DIGITS) {
    return null;
  }
  const rupees = BigInt(wholeDigits);
  if (rupees > MAX_RUPEES_BIG) {
    return null;
  }
  const paise = BigInt((match[2] ?? "").padEnd(2, "0"));
  // The largest accepted value is about 10^15 paise, which is below Number.MAX_SAFE_INTEGER.
  return Number(rupees * PAISE_PER_RUPEE + paise);
}

function groupIndian(digits: string): string {
  if (digits.length <= 3) {
    return digits;
  }
  const head = digits.slice(0, -3);
  const tail = digits.slice(-3);
  return `${head.replace(/\B(?=(\d{2})+$)/g, ",")},${tail}`;
}

export function formatMinor(minor: number, options: FormatOptions = {}): string {
  if (!Number.isSafeInteger(minor)) {
    throw new RangeError("formatMinor expects a safe integer amount in paise");
  }
  const magnitude = BigInt(Math.abs(minor));
  const rupees = groupIndian((magnitude / PAISE_PER_RUPEE).toString());
  const paise = (magnitude % PAISE_PER_RUPEE).toString().padStart(2, "0");
  const amount = `${RUPEE_SIGN}${rupees}.${paise}`;
  if (minor < 0) {
    return `${MINUS_SIGN}${amount}`;
  }
  if (minor > 0 && options.sign === true) {
    return `+${amount}`;
  }
  return amount;
}
