import { useEffect, useId, useRef, type ReactNode } from "react";

interface AppDialogProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}

// Native modal dialog: showModal() gives focus trapping, Escape and an inert page behind it.
// Below 600px the CSS turns it into a full-width bottom sheet.
export function AppDialog({ open, title, onClose, children }: AppDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const closeRef = useRef(onClose);
  const titleId = useId();

  useEffect(() => {
    closeRef.current = onClose;
  });

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog === null) {
      return;
    }
    if (open && !dialog.open) {
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog === null) {
      return undefined;
    }
    const handleClose = () => closeRef.current();
    dialog.addEventListener("close", handleClose);
    return () => dialog.removeEventListener("close", handleClose);
  }, []);

  return (
    <dialog ref={dialogRef} className="app-dialog" aria-labelledby={titleId}>
      <div className="dialog-body">
        <h2 id={titleId} className="dialog-title">
          {title}
        </h2>
        {children}
      </div>
    </dialog>
  );
}
