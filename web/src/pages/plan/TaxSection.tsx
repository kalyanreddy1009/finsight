import { useState } from "react";
import { getTaxSummary, type TaxSummary, type TaxSummarySection } from "../../api/tax";
import { LoadError } from "../../components/LoadError";
import { SelectField } from "../../components/SelectField";
import { useLoader } from "../../hooks/useLoader";
import { formatMinor } from "../../lib/money";
import { taxSectionLabel } from "../transactions/transactionLabels";
import { formatPlanDate } from "./planFormat";
import { fyForDate, fyOptions } from "./taxForm";

export function TaxSection() {
  const [currentFy] = useState(() => fyForDate(new Date()));
  const [fy, setFy] = useState(currentFy);
  return (
    <section className="plan-section" aria-labelledby="tax-heading">
      <div className="plan-section-header">
        <h2 id="tax-heading" className="plan-section-title">
          Tax
        </h2>
        <div className="plan-fy-select">
          <SelectField
            id="tax-fy"
            label="Financial year"
            value={String(fy)}
            options={fyOptions(currentFy)}
            onChange={(event) => setFy(Number(event.target.value))}
          />
        </div>
      </div>
      <TaxBody key={fy} fy={fy} />
    </section>
  );
}

// Keyed by financial year, so changing the selector loads that year's summary.
function TaxBody({ fy }: { fy: number }) {
  const loader = useLoader(() => getTaxSummary(fy));
  const state = loader.state;
  if (state.status === "loading") {
    return (
      <p className="empty-state" role="status">
        Loading tax summary…
      </p>
    );
  }
  if (state.status === "error") {
    return <LoadError message="Could not load your tax summary. Check your connection and try again." onRetry={loader.reload} />;
  }
  return <TaxSummaryView summary={state.data} />;
}

function TaxSummaryView({ summary }: { summary: TaxSummary }) {
  const sections = summary.sections.filter((section) => section.tax_section !== "NONE");
  if (sections.length === 0) {
    return (
      <p className="empty-state">
        No tax-tagged transactions in this year. Set a tax section on a transaction to see it here.
      </p>
    );
  }
  return (
    <>
      <p className="secondary-text">
        {formatPlanDate(summary.start_date)} to {formatPlanDate(summary.end_date)} · Total {formatMinor(summary.total_minor)}
      </p>
      <ul className="row-list">
        {sections.map((section) => (
          <TaxSectionRow key={section.tax_section} section={section} />
        ))}
      </ul>
    </>
  );
}

function TaxSectionRow({ section }: { section: TaxSummarySection }) {
  const count = section.transaction_count;
  return (
    <li className="row">
      <div className="row-main">
        <span className="row-title">{taxSectionLabel(section.tax_section)}</span>
        <span className="secondary-text">
          {count} {count === 1 ? "transaction" : "transactions"}
          {section.limit_minor === null ? null : ` · of ${formatMinor(section.limit_minor)} limit (old regime)`}
        </span>
      </div>
      <span className="row-amount">{formatMinor(section.total_minor)}</span>
    </li>
  );
}
