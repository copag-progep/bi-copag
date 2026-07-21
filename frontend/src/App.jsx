import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import AppLayout from "./components/AppLayout";
import LoadingBlock from "./components/LoadingBlock";
import ProtectedRoute from "./components/ProtectedRoute";

const DocumentacaoPage   = lazy(() => import("./pages/DocumentacaoPage"));
const LoginPage          = lazy(() => import("./pages/LoginPage"));
const ExecutivePage      = lazy(() => import("./pages/ExecutivePage"));
const DashboardPage      = lazy(() => import("./pages/DashboardPage"));
const UploadPage         = lazy(() => import("./pages/UploadPage"));
const FlowPage           = lazy(() => import("./pages/FlowPage"));
const FlowDetailsPage    = lazy(() => import("./pages/FlowDetailsPage"));
const ProductivityPage   = lazy(() => import("./pages/ProductivityPage"));
const MultiSectorPage    = lazy(() => import("./pages/MultiSectorPage"));
const AttributionsPage   = lazy(() => import("./pages/AttributionsPage"));
const ServidoresPage     = lazy(() => import("./pages/ServidoresPage"));
const MonthlyStatsPage   = lazy(() => import("./pages/MonthlyStatsPage"));
const SeiUsersPage       = lazy(() => import("./pages/SeiUsersPage"));
const AdminPage          = lazy(() => import("./pages/AdminPage"));
const AccountPage        = lazy(() => import("./pages/AccountPage"));
const ProcessSearchPage  = lazy(() => import("./pages/ProcessSearchPage"));
const RiscoPage          = lazy(() => import("./pages/RiscoPage"));
const PautaPage          = lazy(() => import("./pages/PautaPage"));
const LogoutPage         = lazy(() => import("./pages/LogoutPage"));


export default function App() {
  return (
    <Suspense fallback={<div className="screen-center"><LoadingBlock label="Carregando..." /></div>}>
      <Routes>
        {/* Rota pública — sem autenticação necessária */}
        <Route path="/documentacao" element={<DocumentacaoPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route path="executivo"          element={<ExecutivePage />} />
          <Route index element={<DashboardPage />} />
          <Route path="enviar-relatorio"    element={<UploadPage />} />
          <Route path="entradas-saidas"     element={<FlowPage />} />
          <Route path="movimentacoes"       element={<FlowDetailsPage />} />
          <Route path="produtividade"       element={<ProductivityPage />} />
          <Route path="multiplos-setores"   element={<MultiSectorPage />} />
          <Route path="atribuicoes"         element={<AttributionsPage />} />
          <Route path="risco"               element={<RiscoPage />} />
          <Route path="pauta"               element={<PautaPage />} />
          <Route path="servidores"          element={<ServidoresPage />} />
          <Route path="indicadores-mensais" element={<MonthlyStatsPage />} />
          <Route path="usuarios-sei"        element={<SeiUsersPage />} />
          <Route path="administracao"       element={<AdminPage />} />
          <Route path="minha-conta"         element={<AccountPage />} />
          <Route path="busca"               element={<ProcessSearchPage />} />
          <Route path="logout"              element={<LogoutPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
