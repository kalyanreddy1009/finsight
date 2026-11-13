import type { CategoryInsight } from "../../api/types";
import { formatMinor } from "../../lib/money";
import { categoryTakeaway, percentText, topCategories } from "./insightFormat";

// Horizontal bars drawn with divs. The bar is decorative: the name, amount and percent are text.
export function CategorySpend({ categories }: { categories: readonly CategoryInsight[] }) {
  const top = topCategories(categories);
  return (
    <section className="card" aria-labelledby="category-spend-heading">
      <h2 id="category-spend-heading" className="eyebrow">
        Spending by Category
      </h2>
      <p className="headline">{categoryTakeaway(categories)}</p>
      {top.length > 0 ? (
        <ul className="cat-list">
          {top.map((category) => (
            <li key={category.category_id ?? category.name} className="cat-row">
              <span className="cat-name">{category.name}</span>
              <span className="cat-amount num">{formatMinor(category.spent_minor)}</span>
              <span className="cat-percent num">{percentText(category.share_bp)}</span>
              <span className="cat-track" aria-hidden="true">
                <span className="cat-fill" style={{ width: `${Math.min(100, category.share_bp / 100)}%` }} />
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
