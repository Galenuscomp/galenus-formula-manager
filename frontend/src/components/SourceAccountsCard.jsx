import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound } from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { ErrorList } from "@/components/PageState";
import PasswordInput from "@/components/PasswordInput";
import SourceLabel from "@/components/SourceLabel";

// Admin: the pharmacy's login to each formula source, used to download PDFs.
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
    onSuccess: () => { setErrors(null); toast({ title: `Signed in to ${account.source} successfully` }); },
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
          {!account.downloads_supported && " · automatic download coming soon"}
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
    <section className="mt-8 rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wide flex items-center gap-2">
        <KeyRound className="w-4 h-4" /> Source accounts
      </h2>
      <p className="text-xs text-slate-500 mt-1">
        The pharmacy's login to each formula site. The server uses it to download formula PDFs;
        it is stored encrypted and the password is never shown again.
      </p>
      <div className="divide-y divide-slate-100">
        {(data || []).map((a) => <AccountRow key={a.source} account={a} />)}
      </div>
    </section>
  );
}
