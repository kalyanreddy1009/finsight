import type { RecurringRule } from "../../api/recurring";
import { Button } from "../../components/Button";
import { ConfirmDelete } from "./ConfirmDelete";
import { formatMinor } from "../../lib/money";
import { frequencyLabel, formatPlanDate } from "./planFormat";
import { groupBills } from "./billForm";

export interface BillListActions {
  onEdit: (rule: RecurringRule) => void;
  onMarkPaid: (rule: RecurringRule) => void;
  onToggleActive: (rule: RecurringRule) => void;
  onAskDelete: (rule: RecurringRule) => void;
  onCancelDelete: () => void;
  onDelete: (rule: RecurringRule) => void;
}

interface BillListProps {
  rules: readonly RecurringRule[];
  busyId: string | null;
  confirmId: string | null;
  actions: BillListActions;
}

export function BillList({ rules, busyId, confirmId, actions }: BillListProps) {
  const { active, paused } = groupBills(rules);
  const rowProps = { busyId, confirmId, actions };
  return (
    <>
      <ul className="row-list">
        {active.map((rule) => (
          <BillRow key={rule.id} rule={rule} {...rowProps} />
        ))}
      </ul>
      {paused.length > 0 ? (
        <section className="plan-group" aria-labelledby="bills-paused-heading">
          <h3 id="bills-paused-heading" className="plan-group-title">
            Paused
          </h3>
          <ul className="row-list">
            {paused.map((rule) => (
              <BillRow key={rule.id} rule={rule} {...rowProps} />
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}

interface BillRowProps {
  rule: RecurringRule;
  busyId: string | null;
  confirmId: string | null;
  actions: BillListActions;
}

function BillRow({ rule, busyId, confirmId, actions }: BillRowProps) {
  const busy = busyId === rule.id;
  return (
    <li className="row plan-item-row">
      <div className="row-main">
        <span className="row-title">{rule.merchant_name}</span>
        <span className="secondary-text">
          {formatMinor(rule.expected_amount_minor)} · {frequencyLabel(rule.frequency)} · Due {formatPlanDate(rule.next_expected_date)}
        </span>
        {rule.is_mandatory ? null : <span className="plan-tag">Optional</span>}
      </div>
      {confirmId === rule.id ? (
        <ConfirmDelete
          question={`Delete ${rule.merchant_name}?`}
          busy={busy}
          onConfirm={() => actions.onDelete(rule)}
          onCancel={actions.onCancelDelete}
        />
      ) : (
        <div className="plan-row-actions">
          <Button variant="secondary" onClick={() => actions.onMarkPaid(rule)} disabled={busy}>
            Mark Paid
          </Button>
          <Button variant="plain" onClick={() => actions.onEdit(rule)} disabled={busy}>
            Edit
          </Button>
          <Button variant="plain" onClick={() => actions.onToggleActive(rule)} disabled={busy}>
            {rule.is_active ? "Pause" : "Resume"}
          </Button>
          <Button variant="plain" onClick={() => actions.onAskDelete(rule)} disabled={busy}>
            Delete
          </Button>
        </div>
      )}
    </li>
  );
}
