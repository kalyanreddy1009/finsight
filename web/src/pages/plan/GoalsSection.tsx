import { useState } from "react";
import { deleteGoal, listGoals, type Goal } from "../../api/goals";
import { Button } from "../../components/Button";
import { LoadError } from "../../components/LoadError";
import { useLoader } from "../../hooks/useLoader";
import { errorText } from "./planFormat";
import { GoalDialog } from "./GoalDialog";
import { GoalRow } from "./GoalRow";

// Open dialog state: { goal: null } adds a goal, { goal } edits that one.
interface GoalDialogState {
  goal: Goal | null;
}

export function GoalsSection() {
  const loader = useLoader(listGoals);
  const [dialog, setDialog] = useState<GoalDialogState | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const state = loader.state;
  const hasGoals = state.status === "ready" && state.data.length > 0;

  function upsertGoal(saved: Goal) {
    loader.update((goals) =>
      goals.some((goal) => goal.id === saved.id) ? goals.map((goal) => (goal.id === saved.id ? saved : goal)) : [...goals, saved],
    );
    setDialog(null);
  }

  async function handleDelete(goal: Goal) {
    setBusyId(goal.id);
    setActionError(null);
    try {
      await deleteGoal(goal.id);
      setConfirmId(null);
      loader.update((goals) => goals.filter((item) => item.id !== goal.id));
    } catch (error) {
      setActionError(errorText(error, "Could not delete this goal. Try again."));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="plan-section" aria-labelledby="goals-heading">
      <div className="plan-section-header">
        <h2 id="goals-heading" className="plan-section-title">
          Goals
        </h2>
        {hasGoals ? <Button onClick={() => setDialog({ goal: null })}>Add Goal</Button> : null}
      </div>
      <p className="secondary-text">Money set aside for active goals is held back from Safe to Spend.</p>
      {state.status === "loading" ? (
        <p className="empty-state" role="status">
          Loading goals…
        </p>
      ) : null}
      {state.status === "error" ? (
        <LoadError message="Could not load your goals. Check your connection and try again." onRetry={loader.reload} />
      ) : null}
      {state.status === "ready" && state.data.length === 0 ? (
        <div className="empty-block">
          <p className="empty-state">No goals yet. Add a goal to start setting money aside for it.</p>
          <Button onClick={() => setDialog({ goal: null })}>Add Goal</Button>
        </div>
      ) : null}
      {state.status === "ready" && state.data.length > 0 ? (
        <ul className="row-list">
          {state.data.map((goal) => (
            <GoalRow
              key={goal.id}
              goal={goal}
              busy={busyId === goal.id}
              confirming={confirmId === goal.id}
              onEdit={() => setDialog({ goal })}
              onAskDelete={() => setConfirmId(goal.id)}
              onCancelDelete={() => setConfirmId(null)}
              onDelete={() => void handleDelete(goal)}
            />
          ))}
        </ul>
      ) : null}
      {actionError ? (
        <p className="field-error" role="alert">
          {actionError}
        </p>
      ) : null}
      <GoalDialog
        open={dialog !== null}
        goal={dialog?.goal ?? null}
        onClose={() => setDialog(null)}
        onSaved={upsertGoal}
      />
    </section>
  );
}
