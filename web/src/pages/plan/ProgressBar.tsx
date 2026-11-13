interface ProgressBarProps {
  label: string;
  percent: number;
}

// The bar is decoration for sighted users; the text beside it carries the amounts.
export function ProgressBar({ label, percent }: ProgressBarProps) {
  return (
    <div className="plan-progress" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
      <div className="plan-progress-fill" style={{ width: `${percent}%` }} />
    </div>
  );
}
