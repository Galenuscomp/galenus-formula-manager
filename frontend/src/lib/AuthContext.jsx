import React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, setUnauthorizedHandler } from "@/api/client";

const AuthContext = React.createContext(null);

export function AuthProvider({ children }) {
  const queryClient = useQueryClient();
  const { data: user, isLoading, refetch } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get("/api/auth/me").catch(() => null),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  React.useEffect(() => {
    setUnauthorizedHandler(() => queryClient.setQueryData(["me"], null));
  }, [queryClient]);

  const login = async (email, password) => {
    const me = await api.post("/api/auth/login", { email, password });
    queryClient.setQueryData(["me"], me);
    return me;
  };

  const logout = async () => {
    await api.post("/api/auth/logout").catch(() => {});
    queryClient.clear();
    queryClient.setQueryData(["me"], null);
  };

  const value = {
    user: user || null,
    isLoadingAuth: isLoading,
    isAuthenticated: !!user,
    login,
    logout,
    refresh: refetch,
    canPrepare: user?.role === "pharmacist" || user?.role === "technician",
    isPharmacist: user?.role === "pharmacist",
    isAdmin: user?.role === "admin",
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
