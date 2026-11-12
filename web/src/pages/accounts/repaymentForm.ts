import type { SettleBody } from "../../api/splits";
import { formatMinor, parseRupeesToMinor } from "../../lib/money";
import { isIsoDate } from "./format";

export interface RepaymentValues {
  amountText: string;
  bankAccountId: string;
  date: string;
}

export interface RepaymentErrors {
  amount?: string;
  bankAccountId?: string;
  date?: string;
}

export interface RepaymentResult {
  errors: RepaymentErrors;
  body: SettleBody | null;
}

// The amount defaults to the outstanding balance and may not exceed it.
export function validateRepayment(values: RepaymentValues, outstandingMinor: number): RepaymentResult {
  const errors: RepaymentErrors = {};
  const amountMinor = parseRupeesToMinor(values.amountText);
  if (amountMinor === null || amountMinor <= 0) {
    errors.amount = "Enter an amount in rupees, such as 500 or 500.50.";
  } else if (amountMinor > outstandingMinor) {
    errors.amount = `The amount cannot be more than ${formatMinor(outstandingMinor)}.`;
  }
  if (values.bankAccountId === "") {
    errors.bankAccountId = "Choose the bank or cash account that received the money.";
  }
  if (!isIsoDate(values.date)) {
    errors.date = "Enter the date of the repayment.";
  }
  if (Object.keys(errors).length > 0 || amountMinor === null) {
    return { errors, body: null };
  }
  return {
    errors,
    body: { bank_account_id: values.bankAccountId, amount_minor: amountMinor, transaction_date: values.date },
  };
}
