import type { Category } from "../api/types";
import type { SelectOption } from "../components/SelectField";

const TYPE_NAMES: Record<Category["category_type"], string> = {
  EXPENSE: "Spending",
  INCOME: "Income",
};

// Option labels for a select that can hold categories of both types. A name is suffixed with
// its type only when another category shares that name, so unique names stay as they are.
export function categoryOptionsFor(categories: readonly Category[]): SelectOption[] {
  const counts = new Map<string, number>();
  for (const category of categories) {
    counts.set(category.name, (counts.get(category.name) ?? 0) + 1);
  }
  return categories.map((category) => ({
    value: category.id,
    label: (counts.get(category.name) ?? 0) > 1 ? `${category.name} (${TYPE_NAMES[category.category_type]})` : category.name,
  }));
}
