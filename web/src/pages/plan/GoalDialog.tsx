import { useState, type FormEvent } from "react";
import { createGoal, updateGoal, type Goal, type GoalStatus } from "../../api/goals";
import { Button } from "../../components/Button";
import { Dialog } from "../../components/Dialog";
import { Field } from "../../components/Field";
import { SelectField } from "../../components/SelectField";
import { errorText } from "./planFormat";
import {
  goalCreateBody,
  goalFormFor,
  goalPatchBody,
  validateGoalForm,
  type GoalFormErrors,
  type GoalFormValues,
} from "./goalForm";

const STATUS_OPTIONS = [
  { value: "ACTIVE", label: "Active" },
  { value: "PAUSED", label: "Paused" },
  { value: "COMPLETED", label: "Completed" },
];

interface GoalDialogProps {
  open: boolean;
  goal: Goal | null;
  onClose: () => void;
  onSaved: (goal: Goal) => void;
}

export function GoalDialog({ open, goal, onClose, onSaved }: GoalDialogProps) {
  const title = goal === null ? "Add Goal" : "Edit Goal";
  return (
    <Dialog open={open} title={title} onClose={onClose}>
      {open ? <GoalForm goal={goal} onCancel={onClose} onSaved={onSaved} /> : null}
    </Dialog>
  );
}

interface GoalFormProps {
  goal: Goal | null;
  onCancel: () => void;
  onSaved: (goal: Goal) => void;
}

// Mounted only while the dialog is open, so every opening starts from the saved goal or a blank form.
function GoalForm({ goal, onCancel, onSaved }: GoalFormProps) {
  const [values, setValues] = useState<GoalFormValues>(() => goalFormFor(goal));
  const [errors, setErrors] = useState<GoalFormErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function update(patch: Partial<GoalFormValues>) {
    setValues((previous) => ({ ...previous, ...patch }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = validateGoalForm(values);
    setErrors(result.errors);
    setServerError(null);
    if (result.fields === null) {
      return;
    }
    const fields = result.fields;
    setSaving(true);
    try {
      const saved = goal === null ? await createGoal(goalCreateBody(fields)) : await updateGoal(goal.id, goalPatchBody(fields));
      onSaved(saved);
    } catch (error) {
      setServerError(errorText(error, "Could not save. Try again."));
      setSaving(false);
    }
  }

  return (
    <form className="form-stack" onSubmit={(event) => void handleSubmit(event)} noValidate>
      <Field
        id="goal-name"
        label="Name"
        autoComplete="off"
        value={values.name}
        disabled={saving}
        error={errors.name}
        onChange={(event) => update({ name: event.target.value })}
      />
      <Field
        id="goal-target"
        label="Target amount (₹)"
        inputMode="decimal"
        autoComplete="off"
        value={values.target}
        disabled={saving}
        error={errors.target}
        onChange={(event) => update({ target: event.target.value })}
      />
      <Field
        id="goal-locked"
        label="Amount set aside (₹)"
        inputMode="decimal"
        autoComplete="off"
        value={values.locked}
        disabled={saving}
        error={errors.locked}
        onChange={(event) => update({ locked: event.target.value })}
      />
      <Field
        id="goal-monthly"
        label="Monthly contribution (₹)"
        inputMode="decimal"
        autoComplete="off"
        value={values.monthly}
        disabled={saving}
        error={errors.monthly}
        onChange={(event) => update({ monthly: event.target.value })}
      />
      <Field
        id="goal-target-date"
        label="Target date"
        type="date"
        value={values.targetDate}
        disabled={saving}
        error={errors.targetDate}
        onChange={(event) => update({ targetDate: event.target.value })}
      />
      <Field
        id="goal-priority"
        label="Priority (1 to 99)"
        inputMode="numeric"
        autoComplete="off"
        value={values.priority}
        disabled={saving}
        error={errors.priority}
        onChange={(event) => update({ priority: event.target.value })}
      />
      {goal === null ? null : (
        <SelectField
          id="goal-status"
          label="Status"
          value={values.status}
          options={STATUS_OPTIONS}
          disabled={saving}
          onChange={(event) => update({ status: event.target.value as GoalStatus })}
        />
      )}
      {serverError ? (
        <p className="field-error" role="alert">
          {serverError}
        </p>
      ) : null}
      <div className="dialog-actions">
        <Button variant="plain" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" disabled={saving}>
          {saving ? "Saving…" : goal === null ? "Add Goal" : "Save Goal"}
        </Button>
      </div>
    </form>
  );
}
