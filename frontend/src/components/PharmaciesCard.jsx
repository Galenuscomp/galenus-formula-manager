import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, ImageUp, Plus, Trash2 } from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { ErrorList } from "@/components/PageState";

const EMPTY = { name: "", address: "", phone: "" };

// A pharmacist's pharmacies (branches). The one chosen at approval heads the master formula PDF.
function PharmacyForm({ pharmacy, onDone }) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = React.useState(pharmacy ? { name: pharmacy.name, address: pharmacy.address, phone: pharmacy.phone } : EMPTY);
  const [errors, setErrors] = React.useState(null);
  const onError = (err) => setErrors(err.errors?.length ? err.errors : [err.message]);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["pharmacies"] });
  const save = useMutation({
    mutationFn: () => (pharmacy ? api.patch(`/api/pharmacies/${pharmacy.id}`, form) : api.post("/api/pharmacies", form)),
    onSuccess: () => { setErrors(null); refresh(); toast({ title: "Pharmacy saved" }); if (!pharmacy) setForm(EMPTY); onDone?.(); },
    onError,
  });
  const logo = useMutation({
    mutationFn: (file) => {
      const body = new FormData();
      body.append("file", file);
      return api.upload(`/api/pharmacies/${pharmacy.id}/logo`, body);
    },
    onSuccess: () => { setErrors(null); refresh(); toast({ title: "Logo uploaded" }); },
    onError,
  });
  const remove = useMutation({
    mutationFn: () => api.delete(`/api/pharmacies/${pharmacy.id}`),
    onSuccess: () => { refresh(); toast({ title: "Pharmacy removed" }); },
    onError,
  });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5 sm:col-span-2">
          <Label>Pharmacy name</Label>
          <Input dir="auto" required value={form.name} onChange={set("name")} className="h-11 text-base" placeholder="e.g. בית מרקחת שור" />
        </div>
        <div className="space-y-1.5">
          <Label>Address</Label>
          <Input dir="auto" value={form.address} onChange={set("address")} className="h-11 text-base" />
        </div>
        <div className="space-y-1.5">
          <Label>Phone</Label>
          <Input dir="ltr" value={form.phone} onChange={set("phone")} className="h-11 text-base" />
        </div>
      </div>
      {pharmacy && (
        <div className="flex items-center gap-3">
          {pharmacy.has_logo ? (
            <img src={`/api/pharmacies/${pharmacy.id}/logo?v=${pharmacy.logo_version}`} alt="Logo"
              className="h-12 max-w-[140px] object-contain rounded border border-slate-200 bg-white p-1" />
          ) : <span className="text-xs text-slate-400">No logo</span>}
          <label className="inline-flex items-center gap-1.5 text-sm text-teal-700 cursor-pointer hover:underline">
            <ImageUp className="w-4 h-4" /> {logo.isPending ? "Uploading…" : pharmacy.has_logo ? "Change logo" : "Upload logo"}
            <input type="file" accept="image/png,image/jpeg" className="hidden" disabled={logo.isPending}
              onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) logo.mutate(f); }} />
          </label>
          <span className="text-xs text-slate-400">PNG or JPG, up to 1 MB</span>
        </div>
      )}
      <ErrorList errors={errors} />
      <div className="flex gap-2">
        <Button type="submit" disabled={save.isPending} className="bg-teal-600 hover:bg-teal-700">
          {save.isPending ? "Saving…" : pharmacy ? "Save" : "Add pharmacy"}
        </Button>
        {pharmacy && (
          <Button type="button" variant="ghost" className="text-rose-600" disabled={remove.isPending}
            onClick={() => window.confirm(`Remove ${pharmacy.name}? Approved formulas keep its details.`) && remove.mutate()}>
            <Trash2 className="w-4 h-4 mr-1" /> Remove
          </Button>
        )}
      </div>
    </form>
  );
}

export default function PharmaciesCard() {
  const { data } = useQuery({ queryKey: ["pharmacies"], queryFn: () => api.get("/api/pharmacies") });
  const [adding, setAdding] = React.useState(false);
  if (!data) return null;
  const canAdd = data.items.length < data.max;

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wide flex items-center gap-2">
          <Building2 className="w-4 h-4" /> My pharmacies
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          Name, address and logo printed at the top of master formulas you approve. You can have up to {data.max}
          {data.max === 1 ? " pharmacy" : " pharmacies"} (set by the administrator).
        </p>
      </div>
      <div className="divide-y divide-slate-100">
        {data.items.map((p) => <div key={p.id} className="py-4 first:pt-0"><PharmacyForm pharmacy={p} /></div>)}
      </div>
      {canAdd && (adding || data.items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-300 p-4">
          <PharmacyForm onDone={() => setAdding(false)} />
        </div>
      ) : (
        <Button variant="outline" onClick={() => setAdding(true)}><Plus className="w-4 h-4 mr-1" /> Add a pharmacy</Button>
      ))}
    </section>
  );
}
