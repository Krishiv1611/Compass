import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import LoginModal from "@/components/auth/LoginModal";
import { authApi } from "@/api";

export default function LoginPage() {
  const navigate = useNavigate();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const checkAuth = async () => {
      const token = sessionStorage.getItem("compass_access_token");
      if (token) {
        try {
          await authApi.getMe();
          navigate("/chat", { replace: true });
        } catch {
          // Token is invalid, stay on login page
        }
      }
      setChecking(false);
    };
    checkAuth();
  }, [navigate]);

  if (checking) {
    return <div className="h-screen w-full bg-background" />;
  }

  return (
    <div className="relative h-screen w-full overflow-hidden bg-background flex items-center justify-center">
      {/* Dot grid */}
      <div className="login-dot-grid absolute inset-0 opacity-60" />
      {/* Radial vignette */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 70% 60% at 50% 50%, transparent 30%, var(--background) 100%)",
        }}
      />
      {/* Login card */}
      <div className="relative z-10">
        <LoginModal
          isOpen={true}
          onClose={() => {}}
          onSuccess={() => {
            window.dispatchEvent(new Event("auth-changed"));
            navigate("/chat", { replace: true });
          }}
        />
      </div>
    </div>
  );
}
