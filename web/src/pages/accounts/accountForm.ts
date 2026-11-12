import type { AccountCreateBody } from "../../api/accounts";
import type { UserAccountSubtype } from "../../api/types";
import { parseRupeesToMinor } from "../../lib/money";
import { isCardSubtype } from "./accountOptions";
import { isIsoDate } from "./format";

export interface AccountFormValues {
  name: string;
  subtype: UserAccountSubtype;
  institution: string;
  creditLimit: string;
  billingDay: string;
  dueDay: string;
  openingBalance: string;
  openingDate: string;
}

export type AccountTextField = Exclude<keyof AccountFormValues, "subtype">;
export type AccountFormErrors = Partial<Record<keyof AccountFormValues, string>>;

export interface AccountFormResult {
  errors: AccountFormErrors;
  body: AccountCreateBody | null;
}

export const EMPTY_ACCOUNT_FORM: AccountFormValues = {
  name: "",
  subtype: "BANK_SAVINGS",
  institution: "",
  creditLimit: "",
  billingDay: "",
  dueDay: "",
  openingBalance: "",
  openingDate: "",
};

const TEXT_MAX = 100;
const DAY_PATTERN = /^\d{1,2}$/;
const DAY_ERROR = "Enter a day from 1 to 31.";
const FIRST_DAY = 1;
const LAST_DAY = 31;

function dayOf(text: string): number | null {
  if (!DAY_PATTERN.test(text)) {
    return null;
  }
  const day = Number(text);
  return day >= FIRST_DAY && day <= LAST_DAY ? day : null;
}

// Rupees typed by the user, converted to paise. Zero and blanks are not amounts.
function amountOf(text: string): number | null {
  const minor = parseRupeesToMinor(text);
  return minor !== null && minor > 0 ? minor : null;
}

function cardFieldErrors(values: AccountFormValues, errors: AccountFormErrors): void {
  const limitText = values.creditLimit.trim();
  const billingText = values.billingDay.trim();
  const dueText = values.dueDay.trim();
  if (limitText !== "" && amountOf(limitText) === null) {
    errors.creditLimit = "Enter the limit in rupees, such as 50000.";
  }
  if (billingText !== "" && dayOf(billingText) === null) {
    errors.billingDay = DAY_ERROR;
  }
  if (dueText !== "" && dayOf(dueText) === null) {
    errors.dueDay = DAY_ERROR;
  }
}

// Validates the add-account form and builds the POST /accounts body (integer paise).
export function validateAccountForm(values: AccountFormValues): AccountFormResult {
  const errors: AccountFormErrors = {};
  const name = values.name.trim();
  const institution = values.institution.trim();
  const isCard = isCardSubtype(values.subtype);
  const openingText = values.openingBalance.trim();
  const openingDate = values.openingDate.trim();

  if (name === "") {
    errors.name = "Enter a name for this account.";
  } else if (name.length > TEXT_MAX) {
    errors.name = `Use ${TEXT_MAX} characters or fewer.`;
  }
  if (institution.length > TEXT_MAX) {
    errors.institution = `Use ${TEXT_MAX} characters or fewer.`;
  }
  if (isCard) {
    cardFieldErrors(values, errors);
  }

  const openingMinor = openingText === "" ? null : amountOf(openingText);
  if (openingText !== "" && openingMinor === null) {
    errors.openingBalance = "Enter an amount above zero in rupees, or leave this blank.";
  }
  if (openingMinor !== null && !isIsoDate(openingDate)) {
    errors.openingDate = "Enter the date this balance is as of.";
  }
  if (Object.keys(errors).length > 0) {
    return { errors, body: null };
  }

  const creditLimit = isCard && values.creditLimit.trim() !== "" ? amountOf(values.creditLimit.trim()) : null;
  const billingDay = isCard && values.billingDay.trim() !== "" ? dayOf(values.billingDay.trim()) : null;
  const dueDay = isCard && values.dueDay.trim() !== "" ? dayOf(values.dueDay.trim()) : null;
  const body: AccountCreateBody = {
    name,
    account_subtype: values.subtype,
    ...(institution === "" ? {} : { institution }),
    ...(creditLimit === null ? {} : { credit_limit_minor: creditLimit }),
    ...(billingDay === null ? {} : { billing_day: billingDay }),
    ...(dueDay === null ? {} : { due_day: dueDay }),
    ...(openingMinor === null ? {} : { opening_balance_minor: openingMinor, opening_date: openingDate }),
  };
  return { errors, body };
}
