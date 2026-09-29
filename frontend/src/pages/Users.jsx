import React from "react";
import { Navigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserPlus, Users as UsersIcon } from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/use-toast";
import { ErrorBlock, ErrorList, LoadingBlock } from "@/components/PageState";
import CatalogImportCard from "@/components/CatalogImportCard";
import PasswordLinkDialog from "@/components/PasswordLinkDialog";
import { useAuth } from "@/lib/AuthContext";

const ROLES = [
  { value: "pharmacist", label: "Pharmacist — prepares and approves" },
  { value: "technician", label: "Technician — prepares drafts" },
  { value: "admin", label: "Administrator — manages users" },
];

// Users on the server default show nothing; the others show their own provider.
const AI_LABELS = { openai: "OpenAI (own key)", anthropic: "Anthropic (own key)", none: "off" };

// Passwords are never typed by the admin: new users get an invitation link and
// forgotten passwords a reset link, where the user chooses their own.
function UserDialog({ open, onOpenChange, editing, onSaved, onLink }) {
  const [form, setForm] = React.useState({});
  const [errors, setErrors] = React.useState(null);
  React.useEffect(() => {
    if (open) {
      setErrors(null);
      setForm(editing
        ? { email: editing.email, full_name: editing.full_name, role: editing.role, licence_number: editing.licence_number || "" }
        : { email: "", full_name: "", role: "technician", licence_number: "" });
    }
  }, [open, editing]);
  const update = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const onError = (err) => setErrors(err.errors?.length ? err.errors : [err.message]);

  const mutation = useMutation({
    mutationFn: () => {
      const body = { ...form, email: (form.email || "").trim() };
      return editing ? api.patch(`/api/users/${editing.id}`, body) : api.post("/api/users", body);
    },
    onSuccess: (saved) => {
      onSaved();
      onOpenChange(false);
      if (saved.password_link) onLink(saved.password_link, saved);
    },
    onError,
  });
  const resetLink = useMutation({
    mutationFn: () => api.post(`/api/users/${editing.id}/password-link`),
    onSuccess: (link) => { onSaved(); onOpenChange(false); onLink(link, editing); },
    onError,
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[92vh] overflow-y-auto">
        <DialogHeader><DialogTitle>{editing ? `Edit ${editing.full_name}` : "Add user"}</DialogTitle></DialogHeader>
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); mutation.mutate(); }}>
          <div className="space-y-2">
            <Label htmlFor="u-email">E-mail</Label>
            <Input id="u-email" type="email" required value={form.email || ""} onChange={(e) => update("email", e.target.value)} className="h-11 text-base" />
            {editing && form.email?.trim().toLowerCase() !== editing.email && (
              <p className="text-xs text-amber-700">The user signs in with the new e-mail from now on. Let them know.</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="u-name">Full name</Label>
            <Input id="u-name" required value={form.full_name || ""} onChange={(e) => update("full_name", e.target.value)} className="h-11 text-base" />
          </div>
          <div className="space-y-2">
            <Label>Role</Label>
            <Select value={form.role} onValueChange={(v) => update("role", v)}>
              <SelectTrigger className="h-11"><SelectValue /></SelectTrigger>
              <SelectContent>{ROLES.map((r) => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="u-licence">Pharmacist licence number</Label>
            <Input id="u-licence" value={form.licence_number || ""} onChange={(e) => update("licence_number", e.target.value)} className="h-11 text-base" />
            <p className="text-xs text-slate-400">Required for pharmacists to approve. Recorded on every approval they make.</p>
          </div>
          {editing ? (
            <div className="rounded-lg border border-slate-200 p-3 space-y-2">
              <p className="text-sm font-medium text-slate-900">Password</p>
              <p className="text-xs text-slate-500">
                {editing.has_password
                  ? "Forgot their password? Create a one-time link where they choose a new one. Their current password and sessions stop working once they use it."
                  : "Has not chosen a password yet. Create a new invitation link if the first one expired or got lost."}
              </p>
              <Button type="button" variant="outline" disabled={resetLink.isPending || !editing.is_active} onClick={() => resetLink.mutate()}>
                {resetLink.isPending ? "Creating…" : editing.has_password ? "Create password reset link" : "Create new invitation link"}
              </Button>
            </div>
          ) : (
            <p className="text-xs text-slate-500">
              After saving you get an invitation link to send to the user. They open it and choose their own password (valid 3 days).
            </p>
          )}
          <ErrorList errors={errors} />
          <DialogFooter className="gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={mutation.isPending} className="bg-teal-600 hover:bg-teal-700">
              {mutation.isPending ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function Users() {
  const { isAdmin, user: me } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [dialog, setDialog] = React.useState({ open: false, editing: null });
  const [shown, setShown] = React.useState(null); // { link, user } just created
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["users"], queryFn: () => api.get("/api/users"), enabled: isAdmin,
  });
  const toggle = useMutation({
    mutationFn: (u) => api.patch(`/api/users/${u.id}`, { is_active: !u.is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
    onError: (err) => toast({ title: "Update failed", description: err.message, variant: "destructive" }),
  });

  if (!isAdmin) return <Navigate to="/" replace />;

  return (
    <div className="p-4 sm:p-6 md:p-10 max-w-4xl mx-auto">
      <div className="flex items-center justify-between gap-3 mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-teal-50 flex items-center justify-center">
            <UsersIcon className="w-5 h-5 text-teal-600" />
          </div>
          <h1 className="text-xl sm:text-2xl font-semibold text-slate-900">Users</h1>
        </div>
        <Button onClick={() => setDialog({ open: true, editing: null })} className="bg-teal-600 hover:bg-teal-700">
          <UserPlus className="w-4 h-4 sm:mr-2" /><span className="hidden sm:inline">Add user</span>
        </Button>
      </div>
      {isLoading ? <LoadingBlock /> : error ? <ErrorBlock error={error} onRetry={refetch} /> : (
        <ul className="rounded-xl border border-slate-200 bg-white divide-y divide-slate-100">
          {data.map((u) => (
            <li key={u.id} className="p-4 flex items-center gap-3">
              <button className="min-w-0 flex-1 text-left" onClick={() => setDialog({ open: true, editing: u })}>
                <p className="font-medium text-slate-900 truncate">{u.full_name}</p>
                <p className="text-sm text-slate-500 truncate">{u.email}</p>
                <p className="text-xs text-slate-400">
                  {u.role}{u.licence_number ? ` · licence ${u.licence_number}` : ""}
                  {u.ai_provider && u.ai_provider !== "default" ? ` · AI: ${AI_LABELS[u.ai_provider] || u.ai_provider}` : ""}
                </p>
                {!u.has_password && <p className="text-xs text-amber-700">Invitation pending — has not set a password yet</p>}
              </button>
              <label className="flex items-center gap-2 text-xs text-slate-500">
                {u.is_active ? "Active" : "Disabled"}
                <Switch checked={u.is_active} disabled={u.id === me.id || toggle.isPending} onCheckedChange={() => toggle.mutate(u)} />
              </label>
            </li>
          ))}
        </ul>
      )}
      <CatalogImportCard />
      <UserDialog open={dialog.open} editing={dialog.editing}
        onOpenChange={(open) => setDialog((d) => ({ ...d, open }))}
        onSaved={() => queryClient.invalidateQueries({ queryKey: ["users"] })}
        onLink={(link, user) => setShown({ link, user })} />
      <PasswordLinkDialog link={shown?.link} user={shown?.user} onClose={() => setShown(null)} />
    </div>
  );
}
