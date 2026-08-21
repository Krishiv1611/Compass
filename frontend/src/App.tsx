import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate, Link } from "react-router-dom";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { RunProvider } from "@/contexts/RunContext";
import { AuthProvider } from "@/contexts/AuthContext";
import { WorkbenchProvider } from "@/contexts/WorkbenchContext";
import { useTheme } from "@/components/ThemeProvider";

const AuthCallback = lazy(() => import("@/pages/AuthCallback"));
const ChatPage = lazy(() => import("@/pages/ChatPage"));
const LoginPage = lazy(() => import("@/pages/LoginPage"));

function App() {
  const { resolvedTheme } = useTheme();
  return (
    <>
      <AuthProvider>
      <RunProvider>
      <WorkbenchProvider>
      <BrowserRouter>
        <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-background text-sm text-muted-foreground">Loading Compass…</div>}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/auth/callback" element={<AuthCallback />} />
          
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="*" element={<div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background text-foreground"><h1 className="text-lg font-semibold">Page not found</h1><Link className="text-sm text-primary underline-offset-4 hover:underline" to="/chat">Return to Compass</Link></div>} />
          </Route>
        </Routes>
        </Suspense>
      </BrowserRouter>
      </WorkbenchProvider>
      </RunProvider>
      </AuthProvider>
      <ToastContainer position="bottom-right" theme={resolvedTheme} />
    </>
  );
}

export default App;



