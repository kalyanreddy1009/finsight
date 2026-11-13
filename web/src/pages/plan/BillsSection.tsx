import { useState } from "react";
import { advanceRecurring, deleteRecurring, listRecurring, updateRecurring, type RecurringRule } from "../../api/recurring";
import type { Category } from "../../api/types";
import { Button } from "../../components/Button";
import { LoadError } from "../../components/LoadError";
import { useLoader } from "../../hooks/useLoader";
import { BillDialog } from "./BillDialog";
import { BillList, type BillListActions } from "./BillList";
import { errorText } from "./planFormat";

interface BillsSectionProps {
  // null while the categories are still loading.
  categories: readonly Category[] | null;
}

export function BillsSection({ categories }: BillsSectionProps) {
  const loader = useLoader(listRecurring);
  // Open dialog: { rule: null } adds a bill, { rule } edits that one.
  const [dialog, setDialog] = useState<{ rule: RecurringRule | null } | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const state = loader.state;
  const hasBills = state.status === "ready" && state.data.length > 0;

  function replaceBill(updated: RecurringRule) {
    loader.update((rules) => rules.map((rule) => (rule.id === updated.id ? updated : rule)));
  }

  // Runs one row action. Only one action per row is in flight at a time.
  async function perform(id: string, run: () => Promise<void>, fallback: string) {
    setBusyId(id);
    setActionError(null);
    try {
      await run();
    } catch (error) {
      setActionError(errorText(error, fallback));
    } finally {
      setBusyId(null);
    }
  }

  const actions: BillListActions = {
    onEdit: (rule) => setDialog({ rule }),
    onMarkPaid: (rule) =>
      void perform(
        rule.id,
        async () => replaceBill(await advanceRecurring(rule.id)),
        "Could not mark this bill as paid. Try again.",
      ),
    onToggleActive: (rule) =>
      void perform(
        rule.id,
        async () => replaceBill(await updateRecurring(rule.id, { is_active: !rule.is_active })),
        "Could not update this bill. Try again.",
      ),
    onAskDelete: (rule) => setConfirmId(rule.id),
    onCancelDelete: () => setConfirmId(null),
    onDelete: (rule) =>
      void perform(
        rule.id,
        async () => {
          await deleteRecurring(rule.id);
          setConfirmId(null);
          loader.update((rules) => rules.filter((item) => item.id !== rule.id));
        },
        "Could not delete this bill. Try again.",
      ),
  };

  return (
    <section className="plan-section" aria-labelledby="bills-heading">
      <div className="plan-section-header">
        <h2 id="bills-heading" className="plan-section-title">
          Bills
        </h2>
        {hasBills ? <Button onClick={() => setDialog({ rule: null })}>Add Bill</Button> : null}
      </div>
      {state.status === "loading" ? (
        <p className="empty-state" role="status">
          Loading bills…
        </p>
      ) : null}
      {state.status === "error" ? (
        <LoadError message="Could not load your bills. Check your connection and try again." onRetry={loader.reload} />
      ) : null}
      {state.status === "ready" && state.data.length === 0 ? (
        <div className="empty-block">
          <p className="empty-state">No recurring bills yet. Add a bill to see what is due next.</p>
          <Button onClick={() => setDialog({ rule: null })}>Add Bill</Button>
        </div>
      ) : null}
      {state.status === "ready" && state.data.length > 0 ? (
        <BillList rules={state.data} busyId={busyId} confirmId={confirmId} actions={actions} />
      ) : null}
      {actionError ? (
        <p className="field-error" role="alert">
          {actionError}
        </p>
      ) : null}
      <BillDialog
        open={dialog !== null}
        rule={dialog?.rule ?? null}
        categories={categories}
        onClose={() => setDialog(null)}
        onSaved={(saved) => {
          loader.update((rules) =>
            rules.some((rule) => rule.id === saved.id) ? rules.map((rule) => (rule.id === saved.id ? saved : rule)) : [...rules, saved],
          );
          setDialog(null);
        }}
      />
    </section>
  );
}
