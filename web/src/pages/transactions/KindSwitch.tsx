import type { EntryKind } from "./transactionForm";
import { KIND_LABELS } from "./transactionForm";

const KINDS: readonly EntryKind[] = ["expense", "income", "transfer"];

interface KindSwitchProps {
  value: EntryKind;
  onChange: (kind: EntryKind) => void;
}

// Segmented choice. The pressed state is shown by weight and fill, not color alone.
export function KindSwitch({ value, onChange }: KindSwitchProps) {
  return (
    <div className="tx-segmented" role="group" aria-label="Entry type">
      {KINDS.map((kind) => (
        <button
          key={kind}
          type="button"
          className="tx-segment"
          aria-pressed={value === kind}
          onClick={() => onChange(kind)}
        >
          {KIND_LABELS[kind]}
        </button>
      ))}
    </div>
  );
}
