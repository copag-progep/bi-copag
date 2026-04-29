import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import AppLayout from "./components/AppLayout";
import LoadingBlock from "./components/LoadingBlock";
import ProtectedRoute from "./components/ProtectedRoute";

const LoginPage = lazy(() => import("./pages/LoginPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const UploadPage = lazy(() => import("./pages/UploadPage"));
const FlowPage = lazy(() => import("./pages/FlowPage"));
const ProductivityPage = lazy(() => import("./pages/ProductivityPage"));
const StaleProcessesPage = lazy(() => import("./pages/StaleProcessesPage"));
const MultiSectorPage = lazy(() => import("./pages/MultiSectorPage"));
const AttributionsPage = lazy(() => import("./pages/AttributionsPage"));
const MonthlyStatsPage = lazy(() => import("./pages/MonthlyStatsPage"));
const SeiUsersPage = lazy(() => import("./pages/SeiUsersPage"));
const AdminPage = lazy(() => import("./pages/AdminPage"));
const LogoutPage = lazy(() => import("./pages/LogoutPage"));


export default function App() {
  return (
    <Suspense fallback={<div className="screen-center"><LoadingBlock label="Carregando..." /></div>}>
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
          <Route path="atribuicoes" element={<AttributionsPage />} />
          <Route path="indicadores-mensais" element={<MonthlyStatsPage />} />
          <Route path="usuarios-sei" element={<SeiUsersPage />} />
          <Route path="administracao" element={<AdminPage />} />
          <Route path="logout" element={<LogoutPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
