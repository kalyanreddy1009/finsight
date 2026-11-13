import type { StatementRow } from "../../api/statements";
import type { Category } from "../../api/types";
import { Button } from "../../components/Button";
import { formatMinor } from "../../lib/money";
import { formatIsoDate } from "./format";
import { SelectField } from "../../components/SelectField";
import { ROW_STATUS_LABELS, rowActionsFor } from "./rowStatus";
import type { RowActions } from "./useRowActions";

interface StatementRowItemProps {
  row: StatementRow;
  categories: readonly Category[];
  readOnly: boolean;
  actions: RowActions;
}

export function StatementRowItem({ row, categories, readOnly, actions }: StatementRowItemProps) {
  const directionLabel = row.direction === "CREDIT" ? "In" : "Out";
  const committed = row.row_status === "COMMITTED";
  const buttons = readOnly || committed ? [] : rowActionsFor(row.row_status);
  // DEBIT is money out, so only spending categories fit; CREDIT is money in, so only income.
  const categoryType = row.direction === "CREDIT" ? "INCOME" : "EXPENSE";
  const fittingCategories = categories.filter((category) => category.category_type === categoryType);
  // A suggested category of the other type is not a fitting option, but the select must still show it.
  const currentCategory = categories.find((category) => category.id === row.suggested_category_id);
  const selectableCategories =
    currentCategory !== undefined && !fittingCategories.includes(currentCategory)
      ? [...fittingCategories, currentCategory]
      : fittingCategories;
  return (
    <li className="stmt-row">
      <div className="stmt-main">
        <span className="row-title">{row.clean_description}</span>
        <span className="secondary-text">{formatIsoDate(row.tx_date)}</span>
      </div>
      <span className="row-amount">{`${directionLabel} ${formatMinor(row.amount_minor)}`}</span>
      <div className="stmt-meta">
        <span className="status-text">{ROW_STATUS_LABELS[row.row_status]}</span>
        {/* A suggested id missing from the loaded categories shows the placeholder, not a wrong option. */}
        <SelectField
          id={`row-category-${row.id}`}
          label="Category"
          value={currentCategory?.id ?? ""}
          disabled={readOnly || committed}
          onChange={(event) => {
            const categoryId = event.target.value;
            if (categoryId !== "") {
              void actions.setCategory(row, categoryId);
            }
          }}
        >
          <option value="">Choose a category</option>
          {selectableCategories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </SelectField>
      </div>
      {buttons.length > 0 ? (
        <div className="row-actions">
          {buttons.map((action) => (
            <Button key={action.label} variant="secondary" onClick={() => void actions.setStatus(row, action.target)}>
              {action.label}
            </Button>
          ))}
        </div>
      ) : null}
    </li>
  );
}
