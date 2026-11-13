interface BrandMarkProps {
  className?: string;
  // Decorative next to the wordmark; pass a title when the mark stands alone.
  title?: string;
}

// The FinSight mark: a lens ring that opens at the top right, with a rising line leaving through
// the opening and ending in a spark. Ring and line take the text color; the spark takes --glint.
export function BrandMark({ className, title }: BrandMarkProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 32 32"
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
      role={title === undefined ? undefined : "img"}
      aria-hidden={title === undefined ? true : undefined}
      aria-label={title}
    >
      <path className="brand-mark-ring" d="M26.63 13.15A11 11 0 1 1 18.85 5.37" stroke="currentColor" strokeWidth="2.6" />
      <path className="brand-mark-line" d="M9.6 20.2 13.8 15.7 17 18.3 22.6 11.4" stroke="currentColor" strokeWidth="2.6" />
      <circle className="brand-mark-spark" cx="25.4" cy="6.6" r="2.3" />
    </svg>
  );
}

// Mark plus wordmark. The name is real text so it scales and is read once.
export function BrandLockup({ className }: { className?: string }) {
  return (
    <span className={className === undefined ? "brand" : `brand ${className}`}>
      <BrandMark className="brand-mark" />
      <span className="brand-word">
        Fin<span className="brand-word-accent">Sight</span>
      </span>
    </span>
  );
}
