import type { ComponentType } from "react";
import { AccountsIcon, AssistantIcon, HomeIcon, PlanIcon, TransactionsIcon } from "../components/icons";

export interface NavItem {
  path: string;
  label: string;
  Icon: ComponentType<{ className?: string }>;
  end?: boolean;
}

// The five tabs from spec section 10.1. Tabs navigate; they never perform actions.
export const PRIMARY_NAV: readonly NavItem[] = [
  { path: "/", label: "Home", Icon: HomeIcon, end: true },
  { path: "/transactions", label: "Transactions", Icon: TransactionsIcon },
  { path: "/accounts", label: "Accounts", Icon: AccountsIcon },
  { path: "/plan", label: "Plan", Icon: PlanIcon },
  { path: "/assistant", label: "Assistant", Icon: AssistantIcon },
];
