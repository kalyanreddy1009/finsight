import { useEffect, useState } from "react";
import type { Account, Category } from "../../api/types";
import { SelectField } from "../../components/SelectField";
import { categoryOptionsFor } from "../../lib/categoryOptions";
import type { FilterPatch, TransactionFilterValues } from "./useTransactionFilters";

const SEARCH_DEBOUNCE_MS = 300;

interface TransactionFiltersProps {
  filters: TransactionFilterValues;
  accounts: readonly Account[];
  categories: readonly Category[];
  onChange: (patch: FilterPatch, replace?: boolean) => void;
}

export function TransactionFilters({ filters, accounts, categories, onChange }: TransactionFiltersProps) {
  const accountOptions = accounts.map((account) => ({ value: account.id, label: account.name }));
  const categoryOptions = categoryOptionsFor(categories);
  return (
    <form className="tx-filters" role="search" onSubmit={(event) => event.preventDefault()}>
      <SearchField value={filters.q} onChange={onChange} />
      <div className="tx-filter-grid">
        <SelectField
          id="tx-filter-account"
          label="Account"
          value={filters.accountId}
          options={accountOptions}
          placeholder="All accounts"
          onChange={(event) => onChange({ accountId: event.target.value })}
        />
        <SelectField
          id="tx-filter-category"
          label="Category"
          value={filters.categoryId}
          options={categoryOptions}
          placeholder="All categories"
          onChange={(event) => onChange({ categoryId: event.target.value })}
        />
      </div>
      <label className="tx-toggle" htmlFor="tx-filter-review">
        <input
          id="tx-filter-review"
          type="checkbox"
          checked={filters.needsReview}
          onChange={(event) => onChange({ needsReview: event.target.checked })}
        />
        Needs Review
      </label>
    </form>
  );
}

interface SearchFieldProps {
  value: string;
  onChange: (patch: FilterPatch, replace?: boolean) => void;
}

// Typing is debounced into the URL. Back/forward changes the URL, so the draft follows it.
function SearchField({ value, onChange }: SearchFieldProps) {
  const [draft, setDraft] = useState(value);
  const [synced, setSynced] = useState(value);
  if (value !== synced) {
    setSynced(value);
    setDraft(value);
  }

  useEffect(() => {
    if (draft === value) {
      return;
    }
    const timer = window.setTimeout(() => onChange({ q: draft }, true), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [draft, value, onChange]);

  return (
    <div className="field">
      <label htmlFor="tx-search">Search</label>
      <input
        id="tx-search"
        type="search"
        className="field-input"
        autoComplete="off"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
      />
    </div>
  );
}
