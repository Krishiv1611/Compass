import { Modal } from "@/components/ui/modal";
import AuthSurface from "./AuthSurface";

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  hideCloseButton?: boolean;
}

export default function LoginModal({
  isOpen,
  onClose,
  onSuccess,
  hideCloseButton,
}: LoginModalProps) {
  return (
    <Modal open={isOpen} onClose={onClose} showClose={!hideCloseButton} maxWidth="max-w-md">
      {/* We apply a negative margin to counter Modal padding if necessary, or just let AuthSurface fill it.
          Actually Modal has no padding in panelVariants. */}
      <AuthSurface onSuccess={onSuccess} className="border-0 shadow-none p-0 bg-transparent" />
    </Modal>
  );
}
