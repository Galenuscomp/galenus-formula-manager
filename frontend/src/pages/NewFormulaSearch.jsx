import React from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Search, Check, Zap, Upload } from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { ErrorList } from "@/components/PageState";
import { FORMULA_SOURCES, DEFAULT_SOURCES } from "@/lib/sources";
import { cn } from "@/lib/utils";

const DOSAGE_FORMS = [
  "Oral suspension", "Oral capsule", "Oral solution", "Topical cream", "Topical gel", "Topical ointment",
  "Topical solution", "Suppository", "Ophthalmic solution", "Nasal solution",
];

export default function NewFormulaSearch() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: config } = useQuery({ queryKey: ["config"], queryFn: () => api.get("/api/config"), staleTime: Infinity });
  const automated = config?.automated_sources || [];
  const [form, setForm] = React.useState({
    active_ingredient: "",
    strength: "",
    dosage_form: "",
    final_quantity: "",
    notes: "",
    exact_match_only: false,
    sources: DEFAULT_SOURCES,
  });
  const update = (key, value) => setForm((f) => ({ ...f, [key]: value }));
  const toggleSource = (source) =>
    update("sources", form.sources.includes(source) ? form.sources.filter((s) => s !== source) : [...form.sources, source]);

  const create = useMutation({
    mutationFn: (body) => api.post("/api/requests", body),
    onSuccess: (req) => {
      queryClient.invalidateQueries({ queryKey: ["requests"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      navigate(`/requests/${req.id}`);
    },
  });

  const willAutoSearch = form.sources.filter((s) => automated.includes(s));

  return (
    <div className="p-4 sm:p-6 md:p-10 max-w-3xl mx-auto">
      <button
        onClick={() => navigate(-1)}
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 mb-4 py-1"
      >
        <ArrowLeft className="w-4 h-4" />
        Back
      </button>

      <div className="flex items-center gap-3 mb-1">
        <div className="w-10 h-10 rounded-lg bg-teal-50 flex items-center justify-center">
          <Search className="w-5 h-5 text-teal-600" />
        </div>
        <h1 className="text-xl sm:text-2xl font-semibold text-slate-900">New Formula Search</h1>
      </div>
      <p className="text-slate-500 mb-6 sm:mb-8 text-sm sm:text-base">
        Submit a request to locate a compounding master formula.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate(form);
        }}
        className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-6 md:p-8 space-y-6"
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div className="space-y-2">
            <Label htmlFor="active_ingredient">
              Active ingredient <span className="text-rose-500">*</span>
            </Label>
            <Input id="active_ingredient" placeholder="e.g. Metronidazole" value={form.active_ingredient}
              onChange={(e) => update("active_ingredient", e.target.value)} required className="h-11 text-base" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="strength">Strength</Label>
            <Input id="strength" placeholder="e.g. 50 mg/mL" value={form.strength}
              onChange={(e) => update("strength", e.target.value)} className="h-11 text-base" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="dosage_form">Dosage form</Label>
            <Input id="dosage_form" list="dosage-forms" placeholder="Select or type" value={form.dosage_form}
              onChange={(e) => update("dosage_form", e.target.value)} className="h-11 text-base" />
            <datalist id="dosage-forms">
              {DOSAGE_FORMS.map((f) => <option key={f} value={f} />)}
            </datalist>
          </div>
          <div className="space-y-2">
            <Label htmlFor="final_quantity">Final quantity</Label>
            <Input id="final_quantity" placeholder="e.g. 200 mL" value={form.final_quantity}
              onChange={(e) => update("final_quantity", e.target.value)} className="h-11 text-base" />
          </div>
        </div>

        <div className="space-y-3">
          <div>
            <Label>Sources</Label>
            <p className="text-xs text-slate-400 mt-1">
              Sources marked <Zap className="inline w-3 h-3" /> are searched automatically in the background. For
              the others, upload the PDF on the request page.
            </p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {FORMULA_SOURCES.map((source) => {
              const selected = form.sources.includes(source);
              const auto = automated.includes(source);
              return (
                <button
                  key={source}
                  type="button"
                  onClick={() => toggleSource(source)}
                  className={cn(
                    "flex items-center justify-between rounded-xl border px-4 py-3 min-h-[48px] transition-colors text-left",
                    selected ? "border-teal-300 bg-teal-50" : "border-slate-200 bg-white hover:bg-slate-50"
                  )}
                >
                  <span className={cn("text-sm font-medium flex items-center gap-1.5", selected ? "text-teal-800" : "text-slate-600")}>
                    {auto ? <Zap className="w-3.5 h-3.5 text-amber-500" /> : <Upload className="w-3.5 h-3.5 text-slate-400" />}
                    {source}
                  </span>
                  <span className={cn(
                    "flex items-center justify-center w-5 h-5 rounded-md border",
                    selected ? "border-teal-500 bg-teal-500 text-white" : "border-slate-300 bg-white"
                  )}>
                    {selected && <Check className="w-3.5 h-3.5" />}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="notes">Additional notes</Label>
          <Textarea id="notes" placeholder="Any context, references, or special requirements..." value={form.notes}
            onChange={(e) => update("notes", e.target.value)} rows={3} className="text-base" />
        </div>

        <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3.5">
          <div>
            <p className="text-sm font-medium text-slate-900">Exact match only</p>
            <p className="text-xs text-slate-500">Reject any formula that is not an exact match</p>
          </div>
          <Switch checked={form.exact_match_only} onCheckedChange={(v) => update("exact_match_only", v)} />
        </div>

        {create.error && <ErrorList errors={create.error.errors?.length ? create.error.errors : [create.error.message]} />}

        <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-end gap-3 pt-2">
          <Button type="button" variant="outline" onClick={() => navigate(-1)} className="h-11">
            Cancel
          </Button>
          <Button type="submit" disabled={create.isPending || !form.active_ingredient.trim()}
            className="bg-teal-600 hover:bg-teal-700 h-11">
            {create.isPending ? (
              <span className="flex items-center gap-2">
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Creating…
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <Search className="w-4 h-4" />
                {willAutoSearch.length ? "Create and search" : "Create request"}
              </span>
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}
