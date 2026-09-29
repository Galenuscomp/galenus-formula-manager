import React from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, FlaskConical, Loader2 } from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { ErrorList } from "@/components/PageState";
import PasswordInput from "@/components/PasswordInput";
import PasswordRules from "@/components/PasswordRules";
import { passwordOk } from "@/lib/passwordRules";

// Opened from an invitation or reset link. The token is in the URL fragment,
// which the browser never sends to the server or to other sites.
const tokenFromHash = () => new URLSearchParams(window.location.hash.slice(1)).get("token") || "";

export default function SetPassword() {
  const [token] = React.useState(tokenFromHash);
  const [form, setForm] = React.useState({ password: "", confirm: "" });
  const [errors, setErrors] = React.useState(null);
  const link = useQuery({
    queryKey: ["password-link", token],
    queryFn: () => api.post("/api/auth/password-link/check", { token }),
    enabled: !!token,
    retry: false,
  });
  const save = useMutation({
    mutationFn: () => api.post("/api/auth/password-link", { token, new_password: form.password }),
    onSuccess: () => window.history.replaceState(null, "", window.location.pathname),
    onError: (err) => setErrors(err.errors?.length ? err.errors : [err.message]),
  });

  const submit = (e) => {
    e.preventDefault();
    if (form.password !== form.confirm) return setErrors(["The two passwords do not match."]);
    setErrors(null);
    save.mutate();
  };

  const info = link.data;
  let body;
  if (!token || link.isError) {
    body = (
      <p className="text-sm text-slate-600">
        {link.error?.message || "This link is incomplete."} Ask your administrator for a new link.
      </p>
    );
  } else if (link.isLoading) {
    body = <Loader2 className="w-5 h-5 animate-spin text-teal-600 mx-auto" />;
  } else if (save.isSuccess) {
    body = (
      <div className="space-y-4 text-center">
        <CheckCircle2 className="w-10 h-10 text-teal-600 mx-auto" />
        <p className="text-sm text-slate-700">Your password is set. Sign in with {info.email}.</p>
        <Button asChild className="w-full h-12 bg-teal-600 hover:bg-teal-700"><Link to="/login">Sign in</Link></Button>
      </div>
    );
  } else {
    body = (
      <form onSubmit={submit} className="space-y-4">
        <p className="text-sm text-slate-600">
          {info.purpose === "invite" ? `Welcome, ${info.full_name}. Choose a password` : "Choose a new password"} for{" "}
          <span className="font-medium text-slate-900">{info.email}</span>.
        </p>
        <input type="email" autoComplete="username" value={info.email} readOnly hidden />
        <div className="space-y-2">
          <Label htmlFor="new-password">New password</Label>
          <PasswordInput id="new-password" autoComplete="new-password" autoFocus required value={form.password}
            onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} className="h-12 text-base" />
          <PasswordRules password={form.password} email={info.email} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="confirm-password">Repeat password</Label>
          <PasswordInput id="confirm-password" autoComplete="new-password" required value={form.confirm}
            onChange={(e) => setForm((f) => ({ ...f, confirm: e.target.value }))} className="h-12 text-base" />
        </div>
        <ErrorList errors={errors} />
        <Button type="submit" className="w-full h-12 bg-teal-600 hover:bg-teal-700"
          disabled={save.isPending || !passwordOk(form.password, info.email) || !form.confirm}>
          {save.isPending ? "Saving…" : "Set password"}
        </Button>
      </form>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-teal-600 to-teal-700 flex items-center justify-center p-4">
      <div className="w-full max-w-sm rounded-2xl bg-white shadow-xl p-6 sm:p-8">
        <div className="flex items-center gap-2.5 mb-6">
          <div className="w-10 h-10 rounded-lg bg-teal-600 flex items-center justify-center">
            <FlaskConical className="w-5 h-5 text-white" />
          </div>
          <div className="leading-tight">
            <p className="font-semibold text-slate-900">Master Formula Manager</p>
            <p className="text-xs text-slate-500">Set your password</p>
          </div>
        </div>
        {body}
      </div>
    </div>
  );
}
