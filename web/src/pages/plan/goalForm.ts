import type { Goal, GoalBody, GoalPatch, GoalStatus } from "../../api/goals";
import { parseRupeesToMinor } from "../../lib/money";
import { isIsoDate, minorToRupeesText } from "../accounts/format";

export interface GoalFormValues {
  name: string;
  target: string;
  locked: string;
  monthly: string;
  targetDate: string;
  status: GoalStatus;
}

export type GoalFormField = "name" | "target" | "locked" | "monthly" | "targetDate";
export type GoalFormErrors = Partial<Record<GoalFormField, string>>;

// Validated values in API units. target_date is null when the goal has no date.
export interface GoalFields {
  name: string;
  target_amount_minor: number;
  current_locked_amount_minor: number;
  monthly_contribution_minor: number;
  target_date: string | null;
  status: GoalStatus;
}

export interface GoalFormResult {
  errors: GoalFormErrors;
  fields: GoalFields | null;
}

export const LOCKED_OVER_TARGET_ERROR = "Amount set aside cannot be more than the target. Lower it or raise the target.";

export function goalFormFor(goal: Goal | null): GoalFormValues {
  if (goal === null) {
    return { name: "", target: "", locked: "", monthly: "", targetDate: "", status: "ACTIVE" };
  }
  return {
    name: goal.name,
    target: minorToRupeesText(goal.target_amount_minor),
    locked: minorToRupeesText(goal.current_locked_amount_minor),
    monthly: minorToRupeesText(goal.monthly_contribution_minor),
    targetDate: goal.target_date ?? "",
    status: goal.status,
  };
}

// A blank optional amount counts as zero. Null means the text is not a rupee amount.
function optionalRupees(text: string): number | null {
  return text.trim() === "" ? 0 : parseRupeesToMinor(text.trim());
}

export function validateGoalForm(values: GoalFormValues): GoalFormResult {
  const name = values.name.trim();
  const target = parseRupeesToMinor(values.target.trim());
  const locked = optionalRupees(values.locked);
  const monthly = optionalRupees(values.monthly);
  const targetDate = values.targetDate.trim();
  const errors: GoalFormErrors = {};
  if (name === "") {
    errors.name = "Enter a name for the goal.";
  }
  if (target === null || target <= 0) {
    errors.target = "Enter a target above ₹0.00, such as 100000.";
  }
  if (locked === null) {
    errors.locked = "Enter the amount set aside in rupees, such as 0 or 25000.";
  }
  if (monthly === null) {
    errors.monthly = "Enter the monthly contribution in rupees, such as 5000.";
  }
  if (targetDate !== "" && !isIsoDate(targetDate)) {
    errors.targetDate = "Enter a valid target date.";
  }
  if (target !== null && locked !== null && locked > target) {
    errors.locked = LOCKED_OVER_TARGET_ERROR;
  }
  if (Object.keys(errors).length > 0 || target === null || locked === null || monthly === null) {
    return { errors, fields: null };
  }
  return {
    errors,
    fields: {
      name,
      target_amount_minor: target,
      current_locked_amount_minor: locked,
      monthly_contribution_minor: monthly,
      target_date: targetDate === "" ? null : targetDate,
      status: values.status,
    },
  };
}

// POST body. target_date is left out when the goal has none.
export function goalCreateBody(fields: GoalFields): GoalBody {
  const body: GoalBody = {
    name: fields.name,
    target_amount_minor: fields.target_amount_minor,
    current_locked_amount_minor: fields.current_locked_amount_minor,
    monthly_contribution_minor: fields.monthly_contribution_minor,
  };
  return fields.target_date === null ? body : { ...body, target_date: fields.target_date };
}

// PATCH body. A cleared target date is sent as null.
export function goalPatchBody(fields: GoalFields): GoalPatch {
  return { ...goalCreateBody(fields), target_date: fields.target_date, status: fields.status };
}
