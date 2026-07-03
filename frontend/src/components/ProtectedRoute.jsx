import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute({ children }) {
  const { status } = useAuth();

  if (status === "loading") {
    return <div style={{ padding: 40, textAlign: "center", color: "var(--ink-muted)" }}>Yuklanmoqda...</div>;
  }

  if (status === "anonymous") {
    return <Navigate to="/login" replace />;
  }

  return children;
}
