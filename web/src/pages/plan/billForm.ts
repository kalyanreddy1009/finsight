import type { RecurringBody, RecurringFrequency, RecurringRule } from "../../api/recurring";
import { parseRupeesToMinor } from "../../lib/money";
import { isIsoDate } from "../accounts/format";

export interface BillFormValues {
  merchant: string;
  amount: string;
  categoryId: string;
  frequency: RecurringFrequency;
  nextDate: string;
  mandatory: boolean;
}

export type BillFormField = "merchant" | "amount" | "category" | "nextDate";
export type BillFormErrors = Partial<Record<BillFormField, string>>;

export interface BillFormResult {
  errors: BillFormErrors;
  body: RecurringBody | null;
}

export function emptyBillForm(categoryId: string, today: string): BillFormValues {
  return { merchant: "", amount: "", categoryId, frequency: "MONTHLY", nextDate: today, mandatory: true };
}

export function validateBillForm(values: BillFormValues): BillFormResult {
  const merchant = values.merchant.trim();
  const amount = parseRupeesToMinor(values.amount.trim());
  const errors: BillFormErrors = {};
  if (merchant === "") {
    errors.merchant = "Enter the merchant or payee name.";
  }
  if (amount === null || amount <= 0) {
    errors.amount = "Enter an amount above ₹0.00, such as 499 or 499.50.";
  }
  if (values.categoryId === "") {
    errors.category = "Choose a spending category.";
  }
  if (!isIsoDate(values.nextDate)) {
    errors.nextDate = "Choose the date of the next payment.";
  }
  if (Object.keys(errors).length > 0 || amount === null) {
    return { errors, body: null };
  }
  return {
    errors,
    body: {
      merchant_name: merchant,
      category_id: values.categoryId,
      expected_amount_minor: amount,
      frequency: values.frequency,
      next_expected_date: values.nextDate,
      is_mandatory: values.mandatory,
    },
  };
}

// Active bills first, then paused ones. Each group is ordered by its next due date.
export function groupBills(rules: readonly RecurringRule[]): { active: RecurringRule[]; paused: RecurringRule[] } {
  const sorted = [...rules].sort(
    (a, b) => a.next_expected_date.localeCompare(b.next_expected_date) || a.merchant_name.localeCompare(b.merchant_name),
  );
  return {
    active: sorted.filter((rule) => rule.is_active),
    paused: sorted.filter((rule) => !rule.is_active),
  };
}
