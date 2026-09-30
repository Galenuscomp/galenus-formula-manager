import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleDashed, KeyRound, Loader2, XCircle } from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { ErrorList } from "@/components/PageState";
import PasswordInput from "@/components/PasswordInput";
import SourceLabel from "@/components/SourceLabel";
import { cn, formatDateTime } from "@/lib/utils";

// The user's own login to each formula source; downloads they request run with it.
// The saved password is never shown; leave the field empty to keep it.
function AccountRow({ account }) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = React.useState({ username: account.username || "", password: "" });
  const [errors, setErrors] = React.useState(null);
  React.useEffect(() => setForm({ username: account.username || "", password: "" }), [account.username, account.updated_at]);
  const onError = (err) => setErrors(err.errors?.length ? err.errors : [err.message]);
  const refresh = (data) => {
    setErrors(null);
    queryClient.setQueryData(["source-accounts"], data);
    queryClient.invalidateQueries({ queryKey: ["config"] });
  };
  const save = useMutation({
    mutationFn: () => api.put(`/api/source-accounts/${account.source}`, {
      username: form.username.trim(), password: form.password || null,
    }),
    onSuccess: (data) => { refresh(data); toast({ title: `${account.source} login saved` }); },
    onError,
  });
  const test = useMutation({
    mutationFn: () => api.post(`/api/source-accounts/${account.source}/test`),
    onSuccess: (r) => {
      setErrors(null);
      queryClient.setQueryData(["source-accounts"], r.accounts);
      toast(r.ok ? { title: r.message } : { title: `${account.source} login failed`, description: r.message, variant: "destructive" });
    },
    onError,
  });
  const remove = useMutation({
    mutationFn: () => api.delete(`/api/source-accounts/${account.source}`),
    onSuccess: (data) => { refresh(data); toast({ title: `${account.source} login removed` }); },
    onError,
  });

  return (
    <form className="py-4 space-y-3" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <div className="flex items-center justify-between gap-2">
        <SourceLabel source={account.source} />
        <span className="text-xs text-slate-500">
          {account.configured ? "Login saved" : "No login"}
          {account.source === "MEDISCA" && " · needs a MEDISCA formulation package for formula downloads"}
        </span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor={`${account.source}-user`}>Username</Label>
          <Input id={`${account.source}-user`} autoComplete="off" required value={form.username}
            onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} className="h-11 text-base" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${account.source}-pass`}>Password</Label>
          <PasswordInput id={`${account.source}-pass`} autoComplete="new-password" required={!account.configured}
            placeholder={account.configured ? "Saved — leave empty to keep" : ""} value={form.password}
            onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} className="h-11 text-base" />
        </div>
      </div>
      {account.configured && (
        <div className={cn("flex items-start gap-2 rounded-lg px-3 py-2 text-sm",
          test.isPending ? "bg-slate-50 text-slate-600"
            : account.check_ok === true ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
            : account.check_ok === false ? "bg-rose-50 text-rose-700 border border-rose-200"
            : "bg-slate-50 text-slate-500")}>
          {test.isPending ? <Loader2 className="w-4 h-4 mt-0.5 animate-spin shrink-0" />
            : account.check_ok === true ? <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
            : account.check_ok === false ? <XCircle className="w-4 h-4 mt-0.5 shrink-0" />
            : <CircleDashed className="w-4 h-4 mt-0.5 shrink-0" />}
          <span>
            {test.isPending ? `Signing in to ${account.source}… (up to 30 seconds)`
              : account.check_ok == null ? "Not tested yet. Click Test login to check it."
              : <>{account.check_message} <span className="text-xs opacity-70">· {formatDateTime(account.checked_at)}</span></>}
          </span>
        </div>
      )}
      <ErrorList errors={errors} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={save.isPending} className="bg-teal-600 hover:bg-teal-700">
          {save.isPending ? "Saving…" : "Save"}
        </Button>
        {account.configured && account.downloads_supported && (
          <Button type="button" variant="outline" disabled={test.isPending} onClick={() => test.mutate()}>
            {test.isPending ? "Signing in…" : "Test login"}
          </Button>
        )}
        {account.configured && (
          <Button type="button" variant="ghost" disabled={remove.isPending} className="text-rose-600"
            onClick={() => window.confirm(`Remove the saved ${account.source} login?`) && remove.mutate()}>
            Remove
          </Button>
        )}
      </div>
    </form>
  );
}

export default function SourceAccountsCard() {
  const { data } = useQuery({ queryKey: ["source-accounts"], queryFn: () => api.get("/api/source-accounts") });
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wide flex items-center gap-2">
        <KeyRound className="w-4 h-4" /> Source accounts
      </h2>
      <p className="text-xs text-slate-500 mt-1">
        Your own login to each formula site. PDFs you ask to download are fetched with it. It is stored
        encrypted and the password is never shown again. Test login only signs in — it does not download,
        so it does not use up a daily download limit.
      </p>
      <div className="divide-y divide-slate-100">
        {(data || []).map((a) => <AccountRow key={a.source} account={a} />)}
      </div>
    </section>
  );
}
