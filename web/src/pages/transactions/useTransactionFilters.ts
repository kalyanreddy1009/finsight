import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

export interface TransactionFilterValues {
  q: string;
  accountId: string;
  categoryId: string;
  needsReview: boolean;
}

export type FilterPatch = Partial<TransactionFilterValues>;

// Filters live in the URL so reload and back/forward keep them.
const PARAM_NAMES = {
  q: "q",
  accountId: "account",
  categoryId: "category",
  needsReview: "review",
} as const;

export function readFilters(params: URLSearchParams): TransactionFilterValues {
  return {
    q: params.get(PARAM_NAMES.q) ?? "",
    accountId: params.get(PARAM_NAMES.accountId) ?? "",
    categoryId: params.get(PARAM_NAMES.categoryId) ?? "",
    needsReview: params.get(PARAM_NAMES.needsReview) === "1",
  };
}

function setOrDelete(params: URLSearchParams, name: string, value: string): void {
  if (value === "") {
    params.delete(name);
  } else {
    params.set(name, value);
  }
}

function applyPatch(params: URLSearchParams, patch: FilterPatch): void {
  if (patch.q !== undefined) {
    setOrDelete(params, PARAM_NAMES.q, patch.q);
  }
  if (patch.accountId !== undefined) {
    setOrDelete(params, PARAM_NAMES.accountId, patch.accountId);
  }
  if (patch.categoryId !== undefined) {
    setOrDelete(params, PARAM_NAMES.categoryId, patch.categoryId);
  }
  if (patch.needsReview !== undefined) {
    setOrDelete(params, PARAM_NAMES.needsReview, patch.needsReview ? "1" : "");
  }
}

export function useTransactionFilters(): {
  filters: TransactionFilterValues;
  setFilters: (patch: FilterPatch, replace?: boolean) => void;
} {
  const [params, setParams] = useSearchParams();
  const filters = useMemo(() => readFilters(params), [params]);
  const setFilters = useCallback(
    (patch: FilterPatch, replace = false) => {
      setParams(
        (current) => {
          const next = new URLSearchParams(current);
          applyPatch(next, patch);
          return next;
        },
        { replace },
      );
    },
    [setParams],
  );
  return { filters, setFilters };
}
