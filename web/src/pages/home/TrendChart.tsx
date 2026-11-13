import type { InsightsSummary, TrendPoint } from "../../api/types";
import { formatMinor } from "../../lib/money";
import { describeTrend, shortMonth, trendTakeaway } from "./insightFormat";

const CHART_WIDTH = 600;
const CHART_HEIGHT = 140;
const BAR_GAP_RATIO = 0.12;
const MIN_BAR_HEIGHT = 2;

interface Bar {
  key: string;
  x: number;
  y: number;
  width: number;
  height: number;
  series: "income" | "spending";
}

function buildBars(trend: readonly TrendPoint[]): Bar[] {
  const peak = Math.max(1, ...trend.flatMap((point) => [point.income_minor, point.expense_minor]));
  const slot = CHART_WIDTH / Math.max(1, trend.length);
  const barWidth = (slot * (1 - 2 * BAR_GAP_RATIO)) / 2;
  return trend.flatMap((point, index) => {
    const left = index * slot + slot * BAR_GAP_RATIO;
    const make = (series: Bar["series"], value: number, offset: number): Bar => {
      const height = value <= 0 ? 0 : Math.max(MIN_BAR_HEIGHT, (value / peak) * (CHART_HEIGHT - 4));
      return { key: `${point.year_month}-${series}`, x: left + offset, y: CHART_HEIGHT - height, width: barWidth, height, series };
    };
    return [make("income", point.income_minor, 0), make("spending", point.expense_minor, barWidth)];
  });
}

// Grouped bars: income (left) and spending (right) per month. Month labels are HTML so they stay readable.
export function TrendChart({ summary }: { summary: InsightsSummary }) {
  const { trend } = summary;
  const bars = buildBars(trend);
  return (
    <section className="card" aria-labelledby="trend-heading">
      <h2 id="trend-heading" className="eyebrow">
        Six-Month Trend
      </h2>
      <p className="headline">{trendTakeaway(summary)}</p>
      {trend.length > 0 ? (
        <>
          <svg
            className="trend-chart"
            viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
            preserveAspectRatio="none"
            role="img"
            aria-label={describeTrend(trend)}
          >
            <line className="trend-base" x1="0" y1={CHART_HEIGHT} x2={CHART_WIDTH} y2={CHART_HEIGHT} />
            {bars.map((bar) => (
              <rect key={bar.key} className={`trend-bar trend-${bar.series}`} x={bar.x} y={bar.y} width={bar.width} height={bar.height} />
            ))}
          </svg>
          <ul className="trend-months" style={{ gridTemplateColumns: `repeat(${trend.length}, minmax(0, 1fr))` }} aria-hidden="true">
            {trend.map((point) => (
              <li key={point.year_month}>{shortMonth(point.year_month)}</li>
            ))}
          </ul>
          <ul className="trend-legend">
            <li>
              <span className="trend-swatch trend-income" aria-hidden="true" /> Income
            </li>
            <li>
              <span className="trend-swatch trend-spending" aria-hidden="true" /> Spending
            </li>
          </ul>
          <table className="visually-hidden">
            <caption>Income and spending by month</caption>
            <thead>
              <tr>
                <th scope="col">Month</th>
                <th scope="col">Income</th>
                <th scope="col">Spending</th>
              </tr>
            </thead>
            <tbody>
              {trend.map((point) => (
                <tr key={point.year_month}>
                  <th scope="row">{shortMonth(point.year_month)}</th>
                  <td>{formatMinor(point.income_minor)}</td>
                  <td>{formatMinor(point.expense_minor)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
    </section>
  );
}
