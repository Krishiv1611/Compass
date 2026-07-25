import { Dialog } from "@base-ui/react/dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  maxWidth?: string;
  showClose?: boolean;
  ariaLabel?: string;
  title?: string;
}

export function Modal({
  open,
  onClose,
  children,
  maxWidth = "max-w-sm",
  showClose = false,
  ariaLabel,
  title,
}: ModalProps) {
  return (
    <Dialog.Root open={open} onOpenChange={(nextOpen) => { if (!nextOpen) onClose(); }}>
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 z-[80] bg-black/45 transition-opacity duration-150 data-ending-style:opacity-0 data-starting-style:opacity-0" />
        <Dialog.Popup
          aria-label={title ? undefined : ariaLabel}
          className={`fixed left-1/2 top-1/2 z-[81] max-h-[calc(100dvh-32px)] w-[calc(100%-32px)] -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-lg border border-border bg-popover text-foreground shadow-[var(--shadow-lg)] transition duration-150 data-ending-style:scale-[0.98] data-ending-style:opacity-0 data-starting-style:scale-[0.98] data-starting-style:opacity-0 ${maxWidth}`}
        >
          {title && (
            <div className="border-b border-border px-5 py-4">
              <Dialog.Title className="text-base font-semibold">{title}</Dialog.Title>
            </div>
          )}
          {showClose && (
            <Dialog.Close
              render={<Button variant="ghost" size="icon-sm" className="absolute right-3 top-3 z-10" aria-label="Close dialog" />}
            >
              <X className="h-4 w-4" />
            </Dialog.Close>
          )}
          {children}
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export default Modal;
