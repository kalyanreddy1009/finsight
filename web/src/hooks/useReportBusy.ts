import { useEffect } from "react";

// Reports a form's saving state up to the dialog that hosts it, so the dialog can refuse to close.
// Unmounting clears the report, so a form that closes mid-save never leaves its dialog stuck busy.
// Callers must pass a stable callback (a useState setter is fine).
export function useReportBusy(busy: boolean, onBusyChange: ((busy: boolean) => void) | undefined): void {
  useEffect(() => {
    onBusyChange?.(busy);
    return () => onBusyChange?.(false);
  }, [busy, onBusyChange]);
}
