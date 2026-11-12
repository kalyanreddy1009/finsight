import type { Category } from "../../api/types";
import { taxSectionLabel } from "../transactions/transactionLabels";

// Secondary text under a category name. Only the facts that differ from the default are listed.
export function categoryMetaFor(category: Category): string[] {
  const meta: string[] = [];
  if (category.default_tax_section !== "NONE") {
    meta.push(`Tax ${taxSectionLabel(category.default_tax_section)}`);
  }
  if (!category.is_discretionary) {
    meta.push("Essential");
  }
  if (category.is_sensitive_private) {
    meta.push("Private");
  }
  if (category.is_system_category) {
    meta.push("Built in");
  }
  return meta;
}
