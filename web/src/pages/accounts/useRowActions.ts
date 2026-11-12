import { useCallback, useState } from "react";
import {
  patchStatementRow,
  type ReviewableRowStatus,
  type RowPatch,
  type StatementReview,
  type StatementRow,
} from "../../api/statements";
import { messageFor } from "./format";

export type ReviewUpdate = (next: (current: StatementReview) => StatementReview) => void;

export interface ApproveProgress {
  done: number;
  total: number;
}

export interface RowActions {
  progress: ApproveProgress | null;
  error: string | null;
  setStatus: (row: StatementRow, status: ReviewableRowStatus) => Promise<void>;
  setCategory: (row: StatementRow, categoryId: string) => Promise<void>;
  approveAll: (rows: readonly StatementRow[]) => Promise<void>;
}

// Row PATCHes. Each success is applied to the loaded review in place, so the list does not reload.
export function useRowActions(update: ReviewUpdate): RowActions {
  const [progress, setProgress] = useState<ApproveProgress | null>(null);
  const [error, setError] = useState<string | null>(null);

  const applyPatch = useCallback(
    async (row: StatementRow, patch: RowPatch) => {
      await patchStatementRow(row.id, patch);
      update((current) => ({
        ...current,
        rows: current.rows.map((item) => (item.id === row.id ? { ...item, ...patch } : item)),
      }));
    },
    [update],
  );

  const runAction = useCallback(async (action: () => Promise<void>) => {
    setError(null);
    try {
      await action();
    } catch (failure) {
      setError(messageFor(failure));
    }
  }, []);

  const setStatus = useCallback(
    (row: StatementRow, status: ReviewableRowStatus) => runAction(() => applyPatch(row, { row_status: status })),
    [applyPatch, runAction],
  );

  const setCategory = useCallback(
    (row: StatementRow, categoryId: string) =>
      runAction(() => applyPatch(row, { suggested_category_id: categoryId })),
    [applyPatch, runAction],
  );

  // Sequential, so the progress count and the stop-on-error behaviour are exact.
  const approveAll = useCallback(
    async (rows: readonly StatementRow[]) => {
      const pending = rows.filter((row) => row.row_status === "PENDING_REVIEW");
      setError(null);
      setProgress({ done: 0, total: pending.length });
      try {
        for (const [index, row] of pending.entries()) {
          await applyPatch(row, { row_status: "USER_APPROVED" });
          setProgress({ done: index + 1, total: pending.length });
        }
      } catch (failure) {
        setError(messageFor(failure));
      } finally {
        setProgress(null);
      }
    },
    [applyPatch],
  );

  return { progress, error, setStatus, setCategory, approveAll };
}
