import { useEffect, useId, useRef, type ReactNode } from "react";
import { Button } from "./Button";

interface DialogProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}

// Native modal dialog: showModal() gives focus trapping, Escape and an inert page behind it.
// Escape and the Close button both report through onClose. Focus returns to the element that
// opened the dialog. Below 600px the CSS turns it into a full-width sheet.
export function Dialog({ open, title, onClose, children }: DialogProps) {
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
    <dialog ref={dialogRef} className="app-dialog" aria-labelledby={titleId} onClose={onClose}>
      <div className="dialog-header">
        <h2 id={titleId} className="dialog-title">
          {title}
        </h2>
        <Button variant="plain" onClick={onClose}>
          Close
        </Button>
      </div>
      <div className="dialog-body">{children}</div>
    </dialog>
  );
}
