import { Navigate, Route, Routes } from "react-router-dom";

import AppLayout from "./components/AppLayout";
import ProtectedRoute from "./components/ProtectedRoute";
import AdminPage from "./pages/AdminPage";
import DashboardPage from "./pages/DashboardPage";
import FlowPage from "./pages/FlowPage";
import LoginPage from "./pages/LoginPage";
import LogoutPage from "./pages/LogoutPage";
import MultiSectorPage from "./pages/MultiSectorPage";
import MonthlyStatsPage from "./pages/MonthlyStatsPage";
import ProductivityPage from "./pages/ProductivityPage";
import SeiUsersPage from "./pages/SeiUsersPage";
import StaleProcessesPage from "./pages/StaleProcessesPage";
import UploadPage from "./pages/UploadPage";


export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="enviar-relatorio" element={<UploadPage />} />
        <Route path="entradas-saidas" element={<FlowPage />} />
        <Route path="produtividade" element={<ProductivityPage />} />
        <Route path="processos-parados" element={<StaleProcessesPage />} />
        <Route path="multiplos-setores" element={<MultiSectorPage />} />
        <Route path="indicadores-mensais" element={<MonthlyStatsPage />} />
        <Route path="usuarios-sei" element={<SeiUsersPage />} />
        <Route path="administracao" element={<AdminPage />} />
        <Route path="logout" element={<LogoutPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
