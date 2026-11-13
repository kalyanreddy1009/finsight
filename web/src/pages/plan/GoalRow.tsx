import type { Goal, GoalStatus } from "../../api/goals";
import { Button } from "../../components/Button";
import { formatMinor } from "../../lib/money";
import { ConfirmDelete } from "./ConfirmDelete";
import { ProgressBar } from "./ProgressBar";
import { formatPlanDate, usedPercent } from "./planFormat";

const STATUS_LABELS: Record<Exclude<GoalStatus, "ACTIVE">, string> = {
  PAUSED: "Paused",
  COMPLETED: "Completed",
};

interface GoalRowProps {
  goal: Goal;
  busy: boolean;
  confirming: boolean;
  onEdit: () => void;
  onAskDelete: () => void;
  onCancelDelete: () => void;
  onDelete: () => void;
}

export function GoalRow({ goal, busy, confirming, onEdit, onAskDelete, onCancelDelete, onDelete }: GoalRowProps) {
  return (
    <li className="row plan-item-row">
      <div className="row-main">
        <span className="row-title">{goal.name}</span>
        <span className="secondary-text">
          {formatMinor(goal.current_locked_amount_minor)} of {formatMinor(goal.target_amount_minor)}
        </span>
        <ProgressBar
          label={`${goal.name} set aside`}
          percent={usedPercent(goal.current_locked_amount_minor, goal.target_amount_minor)}
        />
        <span className="secondary-text">Priority {goal.priority}</span>
        {goal.target_date ? <span className="secondary-text">Target {formatPlanDate(goal.target_date)}</span> : null}
        {goal.status === "ACTIVE" ? null : <span className="plan-tag">{STATUS_LABELS[goal.status]}</span>}
      </div>
      {confirming ? (
        <ConfirmDelete question={`Delete ${goal.name}?`} busy={busy} onConfirm={onDelete} onCancel={onCancelDelete} />
      ) : (
        <div className="plan-row-actions">
          <Button variant="secondary" onClick={onEdit} disabled={busy}>
            Edit
          </Button>
          <Button variant="plain" onClick={onAskDelete} disabled={busy}>
            Delete
          </Button>
        </div>
      )}
    </li>
  );
}
