import React from "react";
import { useMutation } from "@tanstack/react-query";
import { KeyRound, UserCircle } from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import AISettingsCard from "@/components/AISettingsCard";
import { ErrorList } from "@/components/PageState";
import { useAuth } from "@/lib/AuthContext";

export default function Account() {
  const { user, logout } = useAuth();
  const [form, setForm] = React.useState({ current_password: "", new_password: "", confirm: "" });
  const [errors, setErrors] = React.useState(null);
  const change = useMutation({
    mutationFn: () => api.post("/api/auth/password", {
      current_password: form.current_password, new_password: form.new_password,
    }),
    onSuccess: () => logout(),
    onError: (err) => setErrors(err.errors?.length ? err.errors : [err.message]),
  });

  const submit = (e) => {
    e.preventDefault();
    if (form.new_password !== form.confirm) return setErrors(["New passwords do not match."]);
    if (form.new_password.length < 10) return setErrors(["Use at least 10 characters."]);
    setErrors(null);
    change.mutate();
  };

  return (
    <div className="p-4 sm:p-6 md:p-10 max-w-xl mx-auto space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-5 flex items-center gap-4">
        <UserCircle className="w-10 h-10 text-slate-300" />
        <div className="min-w-0">
          <p className="font-medium text-slate-900">{user.full_name}</p>
          <p className="text-sm text-slate-500 truncate">{user.email}</p>
          <p className="text-xs text-slate-400">{user.role}{user.licence_number ? ` · licence ${user.licence_number}` : ""}</p>
        </div>
      </div>
      <form onSubmit={submit} className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
        <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wide flex items-center gap-2">
          <KeyRound className="w-4 h-4" /> Change password
        </h2>
        {[
          ["current_password", "Current password", "current-password"],
          ["new_password", "New password (min. 10 characters)", "new-password"],
          ["confirm", "Repeat new password", "new-password"],
        ].map(([k, label, ac]) => (
          <div key={k} className="space-y-2">
            <Label htmlFor={k}>{label}</Label>
            <Input id={k} type="password" autoComplete={ac} required value={form[k]}
              onChange={(e) => setForm((f) => ({ ...f, [k]: e.target.value }))} className="h-11 text-base" />
          </div>
        ))}
        <ErrorList errors={errors} />
        <p className="text-xs text-slate-400">You will be signed out on all devices after changing your password.</p>
        <Button type="submit" disabled={change.isPending} className="bg-teal-600 hover:bg-teal-700">
          {change.isPending ? "Saving…" : "Change password"}
        </Button>
      </form>
      <AISettingsCard />
    </div>
  );
}
