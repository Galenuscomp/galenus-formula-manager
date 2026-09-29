import React, { Suspense } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter as Router, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/toaster";
import { queryClientInstance } from "@/lib/query-client";
import { AuthProvider, useAuth } from "@/lib/AuthContext";
import ScrollToTop from "@/components/ScrollToTop";
import ProtectedRoute, { Spinner } from "@/components/ProtectedRoute";
import Layout from "@/components/Layout";
import PageNotFound from "@/lib/PageNotFound";
import Login from "@/pages/Login";
import Home from "@/pages/Home";

// Heavier screens load on demand so the first paint on a phone stays small.
const NewFormulaSearch = React.lazy(() => import("@/pages/NewFormulaSearch"));
const SearchRequests = React.lazy(() => import("@/pages/SearchRequests"));
const SearchRequestDetail = React.lazy(() => import("@/pages/SearchRequestDetail"));
const LocalFormulaDraftDetail = React.lazy(() => import("@/pages/LocalFormulaDraftDetail"));
const ApprovedLibrary = React.lazy(() => import("@/pages/ApprovedLibrary"));
const Users = React.lazy(() => import("@/pages/Users"));
const Account = React.lazy(() => import("@/pages/Account"));
const SetPassword = React.lazy(() => import("@/pages/SetPassword"));

function LoginRoute() {
  const { isAuthenticated, isLoadingAuth } = useAuth();
  if (isLoadingAuth) return <Spinner />;
  return isAuthenticated ? <Navigate to="/" replace /> : <Login />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClientInstance}>
      <AuthProvider>
        <Router>
          <ScrollToTop />
          <Suspense fallback={<Spinner />}>
            <Routes>
              <Route path="/login" element={<LoginRoute />} />
              <Route path="/set-password" element={<SetPassword />} />
              <Route element={<ProtectedRoute />}>
                <Route element={<Layout />}>
                  <Route path="/" element={<Home />} />
                  <Route path="/new-search" element={<NewFormulaSearch />} />
                  <Route path="/requests" element={<SearchRequests />} />
                  <Route path="/requests/:id" element={<SearchRequestDetail />} />
                  <Route path="/drafts/:id" element={<LocalFormulaDraftDetail />} />
                  <Route path="/approved-library" element={<ApprovedLibrary />} />
                  <Route path="/users" element={<Users />} />
                  <Route path="/account" element={<Account />} />
                </Route>
              </Route>
              <Route path="*" element={<PageNotFound />} />
            </Routes>
          </Suspense>
        </Router>
        <Toaster />
      </AuthProvider>
    </QueryClientProvider>
  );
}
