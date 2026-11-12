import type { SelectHTMLAttributes } from "react";

export interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  id: string;
  label: string;
  hint?: string;
  error?: string;
}

// Same markup as the shared Field: visible label, with hint and error linked by aria-describedby.
export function SelectField({ id, label, hint, error, children, ...select }: SelectFieldProps) {
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ");
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select
        {...select}
        id={id}
        className="field-input"
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
      >
        {children}
      </select>
      {hint ? (
        <p id={hintId} className="field-hint">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="field-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
