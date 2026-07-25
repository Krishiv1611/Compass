import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import AuthSurface from "@/components/auth/AuthSurface";
import { useAuth } from "@/contexts/AuthContext";

export default function LoginPage() {
  const navigate = useNavigate();
  const { status } = useAuth();

  useEffect(() => {
    if (status === "authenticated") navigate("/chat", { replace: true });
  }, [navigate, status]);

  if (status === "loading") {
    return <div className="h-screen w-full bg-background" />;
  }

  return (
    <div className="flex h-screen w-full items-center justify-center bg-background">
      <div className="w-full max-w-md px-4">
        <AuthSurface
          onSuccess={() => {
            navigate("/chat", { replace: true });
          }}
        />
      </div>
    </div>
  );
}
