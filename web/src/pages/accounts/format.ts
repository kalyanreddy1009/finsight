import { ApiError } from "../../api/client";

const MONTHS: readonly string[] = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const GENERIC_MESSAGE = "Something went wrong. Try again.";
const PAISE_PER_RUPEE = 100n;

export function isIsoDate(value: string): boolean {
  return ISO_DATE.test(value);
}

// Formats YYYY-MM-DD as "3 Nov 2026" without going through Date (no timezone shift).
export function formatIsoDate(iso: string): string {
  if (!isIsoDate(iso)) {
    return iso;
  }
  const [year = "", month = "", day = ""] = iso.split("-");
  const monthName = MONTHS[Number(month) - 1];
  if (monthName === undefined) {
    return iso;
  }
  return `${Number(day)} ${monthName} ${year}`;
}

export function periodText(start: string, end: string): string {
  return `${formatIsoDate(start)} to ${formatIsoDate(end)}`;
}

export function todayIso(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

// Paise to a rupee string for an input, e.g. 1200050 -> "12000.50", -150 -> "-1.50".
// Works on the absolute value with BigInt, then re-applies the sign. No floats.
export function minorToRupeesText(minor: number): string {
  if (!Number.isSafeInteger(minor)) {
    throw new RangeError("minorToRupeesText expects a safe integer amount in paise");
  }
  const magnitude = BigInt(Math.abs(minor));
  const sign = minor < 0 ? "-" : "";
  const rupees = magnitude / PAISE_PER_RUPEE;
  const paise = (magnitude % PAISE_PER_RUPEE).toString().padStart(2, "0");
  return `${sign}${rupees}.${paise}`;
}

export function messageFor(error: unknown): string {
  return error instanceof ApiError ? error.message : GENERIC_MESSAGE;
}
