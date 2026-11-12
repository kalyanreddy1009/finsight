import type { SafeToSpend } from "../../api/types";
import { formatMinor } from "../../lib/money";
import { buildBreakdown, describeBreakdown } from "./breakdown";

// Signature element. The bar is a graphic; the legend beneath carries the same numbers as text.
export function BreakdownBar({ safe }: { safe: SafeToSpend }) {
  const segments = buildBreakdown(safe);
  return (
    <div className="breakdown">
      <div className="breakdown-bar" role="img" aria-label={describeBreakdown(safe)}>
        {segments.map((segment) => (
          <span
            key={segment.key}
            className={`breakdown-segment seg-${segment.key}`}
            style={{ width: `${segment.widthPercent}%` }}
            aria-hidden="true"
          />
        ))}
      </div>
      <ul className="breakdown-legend">
        <li className="legend-row">
          <span className="legend-label">Liquid cash</span>
          <span className="legend-amount">{formatMinor(safe.liquid_cash_minor)}</span>
        </li>
        {segments.map((segment) => (
          <li key={segment.key} className="legend-row">
            <span className={`legend-swatch seg-${segment.key}`} aria-hidden="true" />
            <span className="legend-label">{segment.label}</span>
            <span className="legend-amount">
              {segment.key === "remaining"
                ? formatMinor(segment.amountMinor)
                : formatMinor(-segment.amountMinor)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
