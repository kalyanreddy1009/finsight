import { useCallback, useEffect, useMemo, useState } from "react";
import { listTransactions, type TransactionListParams } from "../../api/transactions";
import type { Transaction } from "../../api/types";
import type { TransactionFilterValues } from "./useTransactionFilters";

export interface TransactionListView {
  status: "loading" | "error" | "ready";
  items: Transaction[];
  nextCursor: string | null;
  isLoadingMore: boolean;
  loadMoreFailed: boolean;
  loadMore: () => void;
  reload: () => void;
}

// A snapshot belongs to one query key (filters plus reload count). Other keys show as loading.
interface ListSnapshot {
  key: string;
  status: "ready" | "error";
  items: Transaction[];
  nextCursor: string | null;
  isLoadingMore: boolean;
  loadMoreFailed: boolean;
}

function toListParams(filters: TransactionFilterValues): TransactionListParams {
  return {
    q: filters.q.trim() || undefined,
    accountId: filters.accountId || undefined,
    categoryId: filters.categoryId || undefined,
    needsReview: filters.needsReview,
  };
}

export function useTransactionList(filters: TransactionFilterValues): TransactionListView {
  const [generation, setGeneration] = useState(0);
  const [snapshot, setSnapshot] = useState<ListSnapshot | null>(null);
  const params = useMemo(() => toListParams(filters), [filters]);
  const key = `${JSON.stringify(params)}#${generation}`;

  useEffect(() => {
    let active = true;
    listTransactions(params).then(
      (page) => {
        if (active) {
          setSnapshot({
            key,
            status: "ready",
            items: page.items,
            nextCursor: page.nextCursor,
            isLoadingMore: false,
            loadMoreFailed: false,
          });
        }
      },
      () => {
        if (active) {
          setSnapshot({ key, status: "error", items: [], nextCursor: null, isLoadingMore: false, loadMoreFailed: false });
        }
      },
    );
    return () => {
      active = false;
    };
  }, [key, params]);

  const current = snapshot !== null && snapshot.key === key ? snapshot : null;

  const loadMore = useCallback(() => {
    if (current === null || current.nextCursor === null || current.isLoadingMore) {
      return;
    }
    const cursor = current.nextCursor;
    setSnapshot({ ...current, isLoadingMore: true, loadMoreFailed: false });
    listTransactions({ ...params, cursor }).then(
      (page) =>
        setSnapshot((latest) =>
          latest !== null && latest.key === key
            ? { ...latest, items: [...latest.items, ...page.items], nextCursor: page.nextCursor, isLoadingMore: false }
            : latest,
        ),
      () =>
        setSnapshot((latest) =>
          latest !== null && latest.key === key ? { ...latest, isLoadingMore: false, loadMoreFailed: true } : latest,
        ),
    );
  }, [current, key, params]);

  const reload = useCallback(() => setGeneration((value) => value + 1), []);

  if (current === null) {
    return { status: "loading", items: [], nextCursor: null, isLoadingMore: false, loadMoreFailed: false, loadMore, reload };
  }
  return {
    status: current.status,
    items: current.items,
    nextCursor: current.nextCursor,
    isLoadingMore: current.isLoadingMore,
    loadMoreFailed: current.loadMoreFailed,
    loadMore,
    reload,
  };
}
