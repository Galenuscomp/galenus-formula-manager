import React from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { FlaskConical, Home, PlusCircle, ListChecks, LogOut, Library, Users, UserCircle } from "lucide-react";
import { useAuth } from "@/lib/AuthContext";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const ROLE_LABELS = { admin: "Administrator", pharmacist: "Pharmacist", technician: "Technician" };

export default function Layout() {
  const location = useLocation();
  const { user, logout, canPrepare, isAdmin } = useAuth();

  const navItems = [
    { label: "Dashboard", short: "Home", path: "/", icon: Home },
    canPrepare && { label: "New Formula Search", short: "Search", path: "/new-search", icon: PlusCircle },
    { label: "Search Requests", short: "Requests", path: "/requests", icon: ListChecks },
    { label: "Approved Library", short: "Library", path: "/approved-library", icon: Library },
    isAdmin && { label: "Users", short: "Users", path: "/users", icon: Users },
  ].filter(Boolean);

  const isActive = (path) =>
    path === "/" ? location.pathname === "/" : location.pathname.startsWith(path);

  return (
    <div className="min-h-screen bg-slate-50 flex">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-64 shrink-0 flex-col border-r border-slate-200 bg-white sticky top-0 h-screen">
        <div className="flex items-center gap-2.5 px-6 h-16 border-b border-slate-200">
          <div className="w-9 h-9 rounded-lg bg-teal-600 flex items-center justify-center shadow-sm">
            <FlaskConical className="w-5 h-5 text-white" />
          </div>
          <div className="leading-tight">
            <p className="text-sm font-semibold text-slate-900">Master Formula</p>
            <p className="text-[11px] text-slate-500">Manager</p>
          </div>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                  isActive(item.path)
                    ? "bg-teal-50 text-teal-700"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                )}
              >
                <Icon className="w-[18px] h-[18px] shrink-0" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="px-3 py-4 border-t border-slate-200 space-y-1">
          <Link to="/account" className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-100">
            <UserCircle className="w-5 h-5 text-slate-400" />
            <div className="min-w-0 leading-tight">
              <p className="text-sm font-medium text-slate-900 truncate">{user?.full_name}</p>
              <p className="text-[11px] text-slate-500">{ROLE_LABELS[user?.role]}</p>
            </div>
          </Link>
          <Button
            variant="ghost"
            size="sm"
            onClick={logout}
            className="w-full justify-start text-slate-500 hover:text-slate-900"
          >
            <LogOut className="w-4 h-4 mr-2" />
            Sign out
          </Button>
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="md:hidden fixed top-0 inset-x-0 z-30 bg-white/95 backdrop-blur border-b border-slate-200 pt-[env(safe-area-inset-top)]">
        <div className="h-14 flex items-center justify-between px-4">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-teal-600 flex items-center justify-center">
              <FlaskConical className="w-4 h-4 text-white" />
            </div>
            <span className="font-semibold text-slate-900 text-sm">Master Formula</span>
          </Link>
          <div className="flex items-center">
            <Link to="/account" aria-label="Account" className="p-2 text-slate-500">
              <UserCircle className="w-5 h-5" />
            </Link>
            <Button variant="ghost" size="sm" onClick={logout} aria-label="Sign out">
              <LogOut className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </header>

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-30 bg-white/95 backdrop-blur border-t border-slate-200 flex pb-[env(safe-area-inset-bottom)]">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={cn(
                "flex-1 flex flex-col items-center gap-1 py-2.5 text-[11px] font-medium min-h-[56px]",
                isActive(item.path) ? "text-teal-700" : "text-slate-500"
              )}
            >
              <Icon className="w-5 h-5" />
              {item.short}
            </Link>
          );
        })}
      </nav>

      <main className="flex-1 min-w-0 pt-[calc(3.5rem+env(safe-area-inset-top))] md:pt-0 pb-[calc(4.5rem+env(safe-area-inset-bottom))] md:pb-0">
        <Outlet />
      </main>
    </div>
  );
}
