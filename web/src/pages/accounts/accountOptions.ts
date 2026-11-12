import type { Account, UserAccountSubtype } from "../../api/types";
import { formatMinor } from "../../lib/money";

export const SUBTYPE_LABELS: Record<UserAccountSubtype, string> = {
  BANK_SAVINGS: "Savings account",
  BANK_CURRENT: "Current account",
  CASH: "Cash",
  WALLET: "Wallet",
  CREDIT_CARD: "Credit card",
  LOAN_HOME: "Home loan",
  LOAN_VEHICLE: "Vehicle loan",
  LOAN_PERSONAL: "Personal loan",
  INVESTMENT_DEMAT: "Demat account",
  INVESTMENT_MF: "Mutual funds",
  FIXED_DEPOSIT: "Fixed deposit",
  PF_EPF_PPF: "PF, EPF or PPF",
  PHYSICAL_ASSET: "Physical asset",
};

interface SubtypeGroup {
  title: string;
  subtypes: readonly UserAccountSubtype[];
}

const SUBTYPE_GROUPS: readonly SubtypeGroup[] = [
  { title: "Bank & Cash", subtypes: ["BANK_SAVINGS", "BANK_CURRENT", "CASH", "WALLET"] },
  { title: "Cards", subtypes: ["CREDIT_CARD"] },
  { title: "Loans", subtypes: ["LOAN_HOME", "LOAN_VEHICLE", "LOAN_PERSONAL"] },
  {
    title: "Investments & Other",
    subtypes: ["INVESTMENT_DEMAT", "INVESTMENT_MF", "FIXED_DEPOSIT", "PF_EPF_PPF", "PHYSICAL_ASSET"],
  },
];

// Subtypes in display order (the add-account select uses this order).
export const ACCOUNT_SUBTYPES: readonly UserAccountSubtype[] = SUBTYPE_GROUPS.flatMap((group) => group.subtypes);

const LIABILITY_SUBTYPES: readonly UserAccountSubtype[] = ["CREDIT_CARD", "LOAN_HOME", "LOAN_VEHICLE", "LOAN_PERSONAL"];

export function isUserAccountSubtype(value: string): value is UserAccountSubtype {
  return (ACCOUNT_SUBTYPES as readonly string[]).includes(value);
}

export function isLiabilitySubtype(subtype: UserAccountSubtype): boolean {
  return LIABILITY_SUBTYPES.includes(subtype);
}

export function isCardSubtype(subtype: UserAccountSubtype): boolean {
  return subtype === "CREDIT_CARD";
}

// Liabilities come back with negative balances; the screen shows them as the amount owed.
export function isOwed(account: Account): boolean {
  return account.account_class === "LIABILITY";
}

export function balanceText(account: Account): string {
  if (isOwed(account)) {
    return `${formatMinor(Math.abs(account.current_balance_minor))} owed`;
  }
  return formatMinor(account.current_balance_minor);
}

export function institutionOrType(account: Account): string {
  const typeLabel = SUBTYPE_LABELS[account.account_subtype];
  return account.institution ? `${account.institution} · ${typeLabel}` : typeLabel;
}

export interface AccountGroup {
  title: string;
  accounts: Account[];
}

export function groupAccounts(accounts: readonly Account[]): AccountGroup[] {
  return SUBTYPE_GROUPS.map((group) => ({
    title: group.title,
    accounts: accounts.filter((account) => group.subtypes.includes(account.account_subtype)),
  })).filter((group) => group.accounts.length > 0);
}

export function assetAccounts(accounts: readonly Account[]): Account[] {
  return accounts.filter((account) => account.account_class === "ASSET");
}

export interface Utilisation {
  barPercent: number;
  text: string;
}

// Card utilisation: owed as a share of the credit limit. The text carries the number; the bar is decoration.
export function utilisationFor(account: Account): Utilisation | null {
  const limit = account.credit_limit_minor;
  if (!isCardSubtype(account.account_subtype) || limit === null || limit <= 0) {
    return null;
  }
  const owed = Math.abs(account.current_balance_minor);
  const percent = Math.round((owed * 100) / limit);
  return {
    barPercent: Math.min(Math.max(percent, 0), 100),
    text: `${percent}% of ${formatMinor(limit)} limit`,
  };
}
