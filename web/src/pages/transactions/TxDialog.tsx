import { useEffect, useId, useRef, type ReactNode } from "react";
import { Button } from "../../components/Button";

interface TxDialogProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}

// Native modal dialog. Escape and the Close button both report through onClose.
// Focus returns to the element that opened the dialog.
export function TxDialog({ open, title, onClose, children }: TxDialogProps) {
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
    <dialog ref={dialogRef} className="tx-dialog" aria-labelledby={titleId} onClose={onClose}>
      <div className="tx-dialog-header">
        <h2 id={titleId} className="tx-dialog-title">
          {title}
        </h2>
        <Button variant="plain" onClick={onClose}>
          Close
        </Button>
      </div>
      {children}
    </dialog>
  );
}
