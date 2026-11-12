import type { SafeToSpend as SafeToSpendData } from "../../api/types";
import { WarningIcon } from "../../components/icons";
import { formatMinor } from "../../lib/money";
import { BreakdownBar } from "./BreakdownBar";

export function SafeToSpend({ safe }: { safe: SafeToSpendData }) {
  return (
    <section className="card safe-to-spend" aria-labelledby="safe-to-spend-heading">
      <h2 id="safe-to-spend-heading" className="subhead">
        Safe to Spend
      </h2>
      {safe.is_liquidity_deficit ? (
        <div className="deficit">
          <WarningIcon className="deficit-icon" />
          <div className="deficit-text">
            <p className="title2 deficit-title">Short by {formatMinor(safe.deficit_minor)}</p>
            <p className="footnote">
              Card dues, upcoming bills and goal locks are more than your liquid cash, so nothing is safe to
              spend today.
            </p>
          </div>
        </div>
      ) : (
        <>
          <p className="large-title amount">{formatMinor(safe.safe_to_spend_minor)}</p>
          <p className="footnote">Safe to spend today: {formatMinor(safe.daily_safe_burn_minor)}</p>
        </>
      )}
      <BreakdownBar safe={safe} />
    </section>
  );
}
