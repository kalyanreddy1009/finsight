import type { CategoryBody } from "../../api/categories";
import type { Category, TaxSection } from "../../api/types";
import type { SelectOption } from "../../components/SelectField";
import { TAX_SECTIONS, taxSectionLabel } from "../transactions/transactionLabels";

export type CategoryType = Category["category_type"];

export const CATEGORY_TYPE_OPTIONS: readonly SelectOption[] = [
  { value: "EXPENSE", label: "Spending" },
  { value: "INCOME", label: "Income" },
];

export const TAX_SECTION_OPTIONS: readonly SelectOption[] = TAX_SECTIONS.map((section) => ({
  value: section,
  label: taxSectionLabel(section),
}));

export const NAME_MAX_LENGTH = 100;

export interface CategoryFormValues {
  name: string;
  type: CategoryType;
  taxSection: TaxSection;
  essential: boolean;
  privateToAi: boolean;
}

export const EMPTY_CATEGORY_FORM: CategoryFormValues = {
  name: "",
  type: "EXPENSE",
  taxSection: "NONE",
  essential: false,
  privateToAi: false,
};

export interface CategoryFormResult {
  nameError: string | null;
  body: CategoryBody | null;
}

// "Essential spending" only applies to spending categories; it maps to is_discretionary = false.
export function validateCategoryForm(values: CategoryFormValues): CategoryFormResult {
  const name = values.name.trim();
  if (name === "") {
    return { nameError: "Enter a name for the category.", body: null };
  }
  if (name.length > NAME_MAX_LENGTH) {
    return { nameError: `Keep the name to ${NAME_MAX_LENGTH} characters or fewer.`, body: null };
  }
  const essential = values.type === "EXPENSE" && values.essential;
  return {
    nameError: null,
    body: {
      name,
      category_type: values.type,
      default_tax_section: values.taxSection,
      is_discretionary: !essential,
      is_sensitive_private: values.privateToAi,
    },
  };
}
