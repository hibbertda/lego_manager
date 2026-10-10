import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import type { ReactNode } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import AppShell from './components/AppShell';
import LoginPage from './pages/LoginPage';
import SetupPage from './pages/SetupPage';
import SetsListPage from './pages/SetsListPage';
import SetDetailPage from './pages/SetDetailPage';
import SearchPage from './pages/SearchPage';
import AdminUsersPage from './pages/AdminUsersPage';
import AdminSsoPage from './pages/AdminSsoPage';
import AdminBricksetPage from './pages/AdminBricksetPage';
import AdminRebrickablePage from './pages/AdminRebrickablePage';
import UtilityLabelsPage from './pages/UtilityLabelsPage';
import UtilityMissingMetadataPage from './pages/UtilityMissingMetadataPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

function Gate({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth();

  if (loading) {
    return (
      <div className="loading-screen">
        <span className="spinner" />
      </div>
    );
  }

  if (session?.needs_setup) return <Navigate to="/setup" replace />;
  if (!session?.authenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function PublicOnly({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth();
  if (loading) return null;
  if (session?.needs_setup) return <Navigate to="/setup" replace />;
  if (session?.authenticated) return <Navigate to="/sets" replace />;
  return <>{children}</>;
}

function RequireAdmin({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  if (!session?.user?.is_admin) return <Navigate to="/sets" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <PublicOnly>
            <LoginPage />
          </PublicOnly>
        }
      />
      <Route
        path="/login/local"
        element={
          <PublicOnly>
            <LoginPage fallback />
          </PublicOnly>
        }
      />
      <Route path="/setup" element={<SetupPage />} />
      <Route
        path="/*"
        element={
          <Gate>
            <AppShell>
              <Routes>
                <Route path="/sets" element={<SetsListPage mode="sets" />} />
                <Route path="/wishlist" element={<SetsListPage mode="wishlist" />} />
                <Route path="/sets/:setId" element={<SetDetailPage />} />
                <Route path="/search" element={<SearchPage />} />
                <Route
                  path="/admin/users"
                  element={
                    <RequireAdmin>
                      <AdminUsersPage />
                    </RequireAdmin>
                  }
                />
                <Route
                  path="/admin/sso"
                  element={
                    <RequireAdmin>
                      <AdminSsoPage />
                    </RequireAdmin>
                  }
                />
                <Route
                  path="/admin/brickset"
                  element={
                    <RequireAdmin>
                      <AdminBricksetPage />
                    </RequireAdmin>
                  }
                />
                <Route
                  path="/admin/rebrickable"
                  element={
                    <RequireAdmin>
                      <AdminRebrickablePage />
                    </RequireAdmin>
                  }
                />
                <Route path="/utility/labels" element={<UtilityLabelsPage />} />
                <Route
                  path="/utility/missing-metadata"
                  element={<UtilityMissingMetadataPage />}
                />
                <Route path="*" element={<Navigate to="/sets" replace />} />
              </Routes>
            </AppShell>
          </Gate>
        }
      />
    </Routes>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <BrowserRouter>
          <AuthProvider>
            <AppRoutes />
          </AuthProvider>
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
