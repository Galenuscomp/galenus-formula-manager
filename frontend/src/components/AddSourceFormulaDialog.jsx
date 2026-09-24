import React from "react";
import { FileText, Upload } from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ErrorList } from "@/components/PageState";
import { FORMULA_SOURCES } from "@/lib/sources";

const EMPTY = { source_name: "", title: "", source_formula_id: "", source_url: "", match_level: "", notes: "" };

export default function AddSourceFormulaDialog({ open, onOpenChange, requestId, onAdded, maxMb = 25 }) {
  const [form, setForm] = React.useState(EMPTY);
  const [file, setFile] = React.useState(null);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState(null);
  const update = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  React.useEffect(() => {
    if (open) {
      setForm(EMPTY);
      setFile(null);
      setError(null);
    }
  }, [open]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.source_name || !file) {
      setError(["Choose a source and a PDF file."]);
      return;
    }
    if (file.size > maxMb * 1024 * 1024) {
      setError([`The PDF is larger than ${maxMb} MB.`]);
      return;
    }
    const body = new FormData();
    Object.entries(form).forEach(([k, v]) => v && body.append(k, v));
    body.append("file", file);
    setSubmitting(true);
    setError(null);
    try {
      const doc = await api.upload(`/api/requests/${requestId}/documents`, body);
      onAdded?.(doc);
      onOpenChange(false);
    } catch (err) {
      setError(err.errors?.length ? err.errors : [err.message]);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[92vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Add source formula</DialogTitle>
          <DialogDescription>Upload the original PDF from MEDISCA, USP, literature or any other source.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label>Original PDF <span className="text-rose-500">*</span></Label>
            <label className="flex items-center gap-3 rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-4 cursor-pointer hover:bg-slate-100">
              {file ? <FileText className="w-5 h-5 text-teal-600" /> : <Upload className="w-5 h-5 text-slate-400" />}
              <span className="text-sm text-slate-700 truncate">{file ? file.name : "Choose PDF file"}</span>
              <input type="file" accept="application/pdf,.pdf" className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] || null)} />
            </label>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Source <span className="text-rose-500">*</span></Label>
              <Select value={form.source_name} onValueChange={(v) => update("source_name", v)}>
                <SelectTrigger className="h-11"><SelectValue placeholder="Select source" /></SelectTrigger>
                <SelectContent>
                  {FORMULA_SOURCES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Match level</Label>
              <Select value={form.match_level} onValueChange={(v) => update("match_level", v)}>
                <SelectTrigger className="h-11"><SelectValue placeholder="Select match level" /></SelectTrigger>
                <SelectContent>
                  {["Exact", "Partial", "Alternative"].map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="title">Formula title</Label>
              <Input id="title" value={form.title} onChange={(e) => update("title", e.target.value)} className="h-11 text-base"
                placeholder="e.g. Metronidazole 50 mg/mL Topical Cream" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="source_formula_id">Source reference</Label>
              <Input id="source_formula_id" value={form.source_formula_id} className="h-11 text-base"
                onChange={(e) => update("source_formula_id", e.target.value)} placeholder="e.g. F009661" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="source_url">Source URL</Label>
              <Input id="source_url" type="url" value={form.source_url} className="h-11 text-base"
                onChange={(e) => update("source_url", e.target.value)} placeholder="https://…" />
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="notes">Notes</Label>
              <Textarea id="notes" rows={2} value={form.notes} onChange={(e) => update("notes", e.target.value)} className="text-base" />
            </div>
          </div>
          <ErrorList errors={error} />
          <DialogFooter className="gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={submitting} className="bg-teal-600 hover:bg-teal-700">
              {submitting ? "Uploading…" : "Add formula"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
