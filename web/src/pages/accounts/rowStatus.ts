import type { ReviewableRowStatus, StatementRowStatus } from "../../api/statements";

export const ROW_STATUS_LABELS: Record<StatementRowStatus, string> = {
  PENDING_REVIEW: "Needs review",
  AUTO_APPROVED: "Auto-approved",
  USER_APPROVED: "Approved",
  REJECTED: "Rejected",
  DUPLICATE: "Duplicate",
  COMMITTED: "Committed",
};

export interface RowAction {
  label: string;
  target: ReviewableRowStatus;
}

export function rowActionsFor(status: StatementRowStatus): RowAction[] {
  switch (status) {
    case "PENDING_REVIEW":
      return [
        { label: "Approve", target: "USER_APPROVED" },
        { label: "Reject", target: "REJECTED" },
      ];
    case "REJECTED":
      return [{ label: "Approve", target: "USER_APPROVED" }];
    case "AUTO_APPROVED":
    case "USER_APPROVED":
      return [{ label: "Reject", target: "REJECTED" }];
    case "DUPLICATE":
      return [{ label: "Not a Duplicate", target: "USER_APPROVED" }];
    case "COMMITTED":
      return [];
  }
}
