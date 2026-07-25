import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import ChatPage from "@/pages/ChatPage";
import AuthCallback from "@/pages/AuthCallback";
import LoginPage from "@/pages/LoginPage";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { RunProvider } from "@/contexts/RunContext";
import { AuthProvider } from "@/contexts/AuthContext";
import { WorkbenchProvider } from "@/contexts/WorkbenchContext";
import { useTheme } from "@/components/ThemeProvider";

function App() {
  const { resolvedTheme } = useTheme();
  return (
    <>
      <AuthProvider>
      <RunProvider>
      <WorkbenchProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/auth/callback" element={<AuthCallback />} />
          
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<ChatPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
      </WorkbenchProvider>
      </RunProvider>
      </AuthProvider>
      <ToastContainer position="bottom-right" theme={resolvedTheme} />
    </>
  );
}

export default App;



