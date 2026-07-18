import { type ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  /** max-width Tailwind class, e.g. "max-w-sm" */
  maxWidth?: string;
  /** Show close button in top-right corner */
  showClose?: boolean;
  /** aria-label for the dialog */
  ariaLabel?: string;
}

const overlayVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
};

const panelVariants = {
  hidden: { opacity: 0, scale: 0.96, y: 8 },
  visible: { opacity: 1, scale: 1, y: 0 },
  exit: { opacity: 0, scale: 0.96, y: 8 },
};

/**
 * Reusable animated modal built on Framer Motion AnimatePresence.
 * Replaces raw <div> overlay patterns across the codebase.
 *
 * Usage:
 *   <Modal open={open} onClose={onClose} maxWidth="max-w-sm" showClose>
 *     <h3>Title</h3>
 *     …
 *   </Modal>
 */
export function Modal({
  open,
  onClose,
  children,
  maxWidth = "max-w-sm",
  showClose = false,
  ariaLabel,
}: ModalProps) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-label={ariaLabel}
          variants={overlayVariants}
          initial="hidden"
          animate="visible"
          exit="hidden"
          transition={{ duration: 0.18 }}
          onClick={(e) => {
            if (e.target === e.currentTarget) onClose();
          }}
        >
          <motion.div
            className={`modal-panel w-full ${maxWidth}`}
            variants={panelVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
          >
            {showClose && (
              <button
                onClick={onClose}
                aria-label="Close modal"
                className="absolute top-4 right-4 flex items-center justify-center rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-primary/40 transition-colors duration-150"
              >
                <X className="h-4 w-4" />
              </button>
            )}
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default Modal;
