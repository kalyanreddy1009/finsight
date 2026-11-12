import type { StatementRow } from "../../api/statements";
import type { Category } from "../../api/types";
import { Button } from "../../components/Button";
import { formatMinor } from "../../lib/money";
import { formatIsoDate } from "./format";
import { SelectField } from "./SelectField";
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
  const buttons = readOnly ? [] : rowActionsFor(row.row_status);
  return (
    <li className="stmt-row">
      <div className="stmt-main">
        <span className="row-title">{row.clean_description}</span>
        <span className="secondary-text">{formatIsoDate(row.tx_date)}</span>
      </div>
      <span className="row-amount">{`${directionLabel} ${formatMinor(row.amount_minor)}`}</span>
      <div className="stmt-meta">
        <span className="status-text">{ROW_STATUS_LABELS[row.row_status]}</span>
        <SelectField
          id={`row-category-${row.id}`}
          label="Category"
          value={row.suggested_category_id ?? ""}
          disabled={readOnly}
          onChange={(event) => {
            const categoryId = event.target.value;
            if (categoryId !== "") {
              void actions.setCategory(row, categoryId);
            }
          }}
        >
          <option value="" disabled>
            Choose a category
          </option>
          {categories.map((category) => (
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
