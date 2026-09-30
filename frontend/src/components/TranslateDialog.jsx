import React from "react";
import { useMutation } from "@tanstack/react-query";
import { Languages, Loader2 } from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { ErrorList } from "@/components/PageState";

// Prose fields the server translates (backend app/ai/translate.py TRANSLATABLE_FIELDS).
export const TRANSLATABLE = [
  ["proposed_formula_name", "Formula name"],
  ["dosage_form", "Dosage form"],
  ["ingredients", "Ingredients and quantities"],
  ["preparation_method", "Preparation method"],
  ["equipment", "Equipment"],
  ["packaging", "Packaging"],
  ["storage_conditions", "Storage conditions"],
  ["bud", "BUD"],
  ["labelling_instructions", "Labelling instructions"],
  ["warnings", "Warnings"],
  ["local_adaptation_notes", "Local adaptation notes"],
];

// AI translation of the draft to Hebrew, reviewed side by side before it replaces the English.
// Nothing is saved here: "Apply" updates the editor, and the draft is saved as usual.
export default function TranslateDialog({ open, onOpenChange, draftId, form, onApply }) {
  const [rows, setRows] = React.useState([]);
  const [errors, setErrors] = React.useState(null);
  const [sent, setSent] = React.useState(0);
  const translate = useMutation({
    mutationFn: (fields) => api.post(`/api/drafts/${draftId}/translate`, { fields }),
    onSuccess: (r) => setRows(TRANSLATABLE.filter(([k]) => k in r.translations).map(([k, label]) => (
      { key: k, label, english: form[k], hebrew: r.translations[k], use: true }))),
    onError: (err) => setErrors(err.errors?.length ? err.errors : [err.message]),
  });

  React.useEffect(() => {
    if (!open) return;
    setRows([]);
    setErrors(null);
    const fields = Object.fromEntries(TRANSLATABLE.map(([k]) => [k, form[k] || ""]).filter(([, v]) => v.trim()));
    setSent(Object.keys(fields).length);
    if (Object.keys(fields).length) translate.mutate(fields);
    else setErrors(["There is no text to translate yet."]);
    // Translate once per opening, with the text as it is at that moment.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const update = (key, patch) => setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  const apply = () => {
    onApply(Object.fromEntries(rows.filter((r) => r.use).map((r) => [r.key, r.hebrew])));
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[92vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Languages className="w-5 h-5" /> Translate to Hebrew</DialogTitle>
          <DialogDescription>
            Review each field against the original. Raw material names, grades, numbers and units stay in English.
            You can edit the Hebrew before applying; nothing is saved until you save the draft.
          </DialogDescription>
        </DialogHeader>
        {translate.isPending && (
          <div className="py-12 flex flex-col items-center gap-2 text-slate-500 text-sm">
            <Loader2 className="w-6 h-6 animate-spin text-teal-600" /> Translating with AI… this can take up to a minute.
          </div>
        )}
        {sent < TRANSLATABLE.length / 2 && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            Only {sent} of {TRANSLATABLE.length} fields have text, so only those are translated. If the source data
            was extracted but not yet applied, close this, click <b>Apply</b> in the AI extraction panel above
            (after reviewing any conflicts), then translate again.
          </div>
        )}
        <ErrorList errors={errors} />
        <div className="space-y-5">
          {rows.map((r) => (
            <div key={r.key} className="rounded-lg border border-slate-200 p-3">
              <label className="flex items-center gap-2 mb-2 text-sm font-medium text-slate-900">
                <Checkbox checked={r.use} onCheckedChange={(v) => update(r.key, { use: !!v })} />
                {r.label}
              </label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="text-sm text-slate-600 whitespace-pre-wrap bg-slate-50 rounded-md p-2" dir="ltr">{r.english}</div>
                <Textarea dir="rtl" value={r.hebrew} rows={Math.min(12, Math.max(2, r.hebrew.split("\n").length + 1))}
                  onChange={(e) => update(r.key, { hebrew: e.target.value })} className="text-base" disabled={!r.use} />
              </div>
            </div>
          ))}
        </div>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={apply} disabled={!rows.some((r) => r.use)} className="bg-teal-600 hover:bg-teal-700">
            Apply to draft
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
