import { useCallback, useEffect, useState } from "react";
import { listCategories } from "../../api/categories";
import { listAccountsForPicker } from "../../api/transactions";
import type { Account, Category } from "../../api/types";

export interface ReferenceView {
  status: "loading" | "ready" | "error";
  accounts: Account[];
  categories: Category[];
  reload: () => void;
}

interface ReferenceSnapshot {
  generation: number;
  status: "ready" | "error";
  accounts: Account[];
  categories: Category[];
}

// Accounts and categories for the pickers. Loaded once per reload.
export function useReferenceData(): ReferenceView {
  const [generation, setGeneration] = useState(0);
  const [snapshot, setSnapshot] = useState<ReferenceSnapshot | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([listAccountsForPicker(), listCategories()]).then(
      ([accounts, categories]) => {
        if (active) {
          setSnapshot({ generation, status: "ready", accounts, categories });
        }
      },
      () => {
        if (active) {
          setSnapshot({ generation, status: "error", accounts: [], categories: [] });
        }
      },
    );
    return () => {
      active = false;
    };
  }, [generation]);

  const reload = useCallback(() => setGeneration((value) => value + 1), []);

  if (snapshot === null || snapshot.generation !== generation) {
    return { status: "loading", accounts: [], categories: [], reload };
  }
  return { status: snapshot.status, accounts: snapshot.accounts, categories: snapshot.categories, reload };
}
