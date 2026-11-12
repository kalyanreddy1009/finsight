import type { Account, Category, Transaction } from "../../api/types";

export function makeTransaction(overrides: Partial<Transaction> = {}): Transaction {
  return {
    id: "tx-1",
    journal_entry_id: "je-1",
    entry_type: "EXPENSE",
    account_id: "acc-1",
    account_name: "HDFC Savings",
    counterparty_account_id: "cp-1",
    counterparty_account_name: "Swiggy",
    category_id: "cat-food",
    category_name: "Food",
    transaction_date: "2026-11-12",
    description: "SWIGGY ORDER 4431",
    clean_description: "Swiggy",
    amount_minor: 45000,
    user_share_minor: 45000,
    direction: "DEBIT",
    transaction_type: "EXPENSE",
    linked_transaction_id: null,
    tax_section: "NONE",
    is_verified: false,
    review_status: "AUTO_APPROVED",
    notes: null,
    version: 3,
    created_at: "2026-11-12T10:00:00Z",
    updated_at: "2026-11-12T10:00:00Z",
    ...overrides,
  };
}

export function makeAccount(overrides: Partial<Account> = {}): Account {
  return {
    id: "acc-1",
    name: "HDFC Savings",
    account_class: "ASSET",
    account_subtype: "BANK_SAVINGS",
    institution: null,
    currency: "INR",
    opening_balance_minor: null,
    current_balance_minor: 0,
    credit_limit_minor: null,
    billing_day: null,
    due_day: null,
    is_liquid: true,
    is_active: true,
    version: 1,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

export function makeCategory(overrides: Partial<Category> = {}): Category {
  return {
    id: "cat-food",
    name: "Food",
    parent_category_id: null,
    category_type: "EXPENSE",
    default_tax_section: "NONE",
    is_discretionary: true,
    is_sensitive_private: false,
    is_system_category: false,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}
