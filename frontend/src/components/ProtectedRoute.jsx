import { Navigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";


export default function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="screen-center">
        <div className="loading-card">Validando sessão...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
}
