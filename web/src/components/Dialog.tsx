import { useEffect, useId, useRef, type ReactNode } from "react";
import { Button } from "./Button";

interface DialogProps {
  open: boolean;
  title: string;
  onClose: () => void;
  // True while a save is in flight: Escape and the Close button do nothing until it finishes.
  busy?: boolean;
  children: ReactNode;
}

// Native modal dialog: showModal() gives focus trapping, Escape and an inert page behind it.
// Escape and the Close button both report through onClose. Focus returns to the element that
// opened the dialog. Below 600px the CSS turns it into a full-width sheet.
export function Dialog({ open, title, onClose, busy = false, children }: DialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog === null) {
      return;
    }
    if (open) {
      if (!dialog.open) {
        openerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
        dialog.showModal();
      }
      return;
    }
    if (dialog.open) {
      dialog.close();
    }
    openerRef.current?.focus();
    openerRef.current = null;
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      className="app-dialog"
      aria-labelledby={titleId}
      onCancel={(event) => {
        // Escape fires cancel before the dialog closes; preventing it keeps a save in flight visible.
        if (busy) {
          event.preventDefault();
        }
      }}
      onClose={onClose}
    >
      <div className="dialog-header">
        <h2 id={titleId} className="dialog-title">
          {title}
        </h2>
        <Button variant="plain" onClick={onClose} disabled={busy}>
          Close
        </Button>
      </div>
      <div className="dialog-body">{children}</div>
    </dialog>
  );
}
