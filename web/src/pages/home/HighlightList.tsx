import type { InsightHighlight } from "../../api/types";

// Rule-based highlights. Severity is carried by a text label and a dot, never colour alone.
export function HighlightList({ highlights }: { highlights: readonly InsightHighlight[] }) {
  return (
    <ul className="highlight-list">
      {highlights.map((item, index) => {
        const warning = item.severity === "warning";
        return (
          <li key={`${index}-${item.kind}-${item.title}`} className="highlight-item">
            <span className={warning ? "dot dot-warning" : "dot dot-info"} aria-hidden="true" />
            <div className="highlight-body">
              {warning ? <span className="highlight-flag">Heads up</span> : null}
              <p className="headline">{item.title}</p>
              <p className="footnote">{item.detail}</p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
