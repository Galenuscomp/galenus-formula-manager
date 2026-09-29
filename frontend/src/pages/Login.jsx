import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { FlaskConical, Loader2, Lock, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import PasswordInput from "@/components/PasswordInput";
import { useAuth } from "@/lib/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email.trim(), password);
      navigate(location.state?.from || "/", { replace: true });
    } catch (err) {
      setError(err.status === 401 ? "Incorrect e-mail or password." : err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-teal-600 to-teal-700 flex items-center justify-center p-4">
      <div className="w-full max-w-sm rounded-2xl bg-white shadow-xl p-6 sm:p-8">
        <div className="flex items-center gap-2.5 mb-6">
          <div className="w-10 h-10 rounded-lg bg-teal-600 flex items-center justify-center">
            <FlaskConical className="w-5 h-5 text-white" />
          </div>
          <div className="leading-tight">
            <p className="font-semibold text-slate-900">Master Formula Manager</p>
            <p className="text-xs text-slate-500">Sign in to continue</p>
          </div>
        </div>

        {error && <div className="mb-4 p-3 rounded-lg bg-rose-50 text-rose-700 text-sm">{error}</div>}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">E-mail</Label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" aria-hidden="true" />
              <Input id="email" type="email" autoComplete="username" autoFocus value={email}
                onChange={(e) => setEmail(e.target.value)} className="pl-10 h-12 text-base" required />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 z-10" aria-hidden="true" />
              <PasswordInput id="password" autoComplete="current-password" value={password}
                onChange={(e) => setPassword(e.target.value)} className="pl-10 h-12 text-base" required />
            </div>
          </div>
          <Button type="submit" className="w-full h-12 font-medium bg-teal-600 hover:bg-teal-700" disabled={loading}>
            {loading ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Signing in…</> : "Sign in"}
          </Button>
        </form>
        <p className="mt-6 text-xs text-slate-400 text-center">
          Forgot your password? Ask your administrator for a reset link.
          <br />Accounts are created by your administrator.
        </p>
      </div>
    </div>
  );
}
