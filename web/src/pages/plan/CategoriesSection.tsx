import type { Category } from "../../api/types";
import { Button } from "../../components/Button";
import { categoryMetaFor } from "./categoryLabels";

interface CategoriesSectionProps {
  categories: readonly Category[];
  onAdd: () => void;
}

const GROUPS: ReadonlyArray<{ type: Category["category_type"]; title: string; empty: string }> = [
  { type: "EXPENSE", title: "Spending", empty: "No spending categories yet." },
  { type: "INCOME", title: "Income", empty: "No income categories yet." },
];

export function CategoriesSection({ categories, onAdd }: CategoriesSectionProps) {
  return (
    <section className="plan-section" aria-labelledby="categories-heading">
      <div className="plan-section-header">
        <h2 id="categories-heading" className="plan-section-title">
          Categories
        </h2>
        <Button variant="primary" onClick={onAdd}>
          Add Category
        </Button>
      </div>
      {GROUPS.map((group) => {
        const items = categories.filter((category) => category.category_type === group.type);
        return (
          <section className="plan-group" key={group.type} aria-labelledby={`category-group-${group.type}`}>
            <h3 id={`category-group-${group.type}`} className="plan-group-title">
              {group.title}
            </h3>
            {items.length === 0 ? (
              <p className="empty-state">{group.empty}</p>
            ) : (
              <ul className="row-list">
                {items.map((category) => (
                  <CategoryRow key={category.id} category={category} />
                ))}
              </ul>
            )}
          </section>
        );
      })}
    </section>
  );
}

function CategoryRow({ category }: { category: Category }) {
  const meta = categoryMetaFor(category);
  return (
    <li className="row plan-category-row">
      <div className="row-main">
        <span className="row-title">{category.name}</span>
        {meta.length > 0 ? <span className="secondary-text">{meta.join(" · ")}</span> : null}
      </div>
    </li>
  );
}
