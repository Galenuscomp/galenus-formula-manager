import { ExternalLink, CheckCircle2, FileText, Download } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { cn, formatDate } from "@/lib/utils";
import SourceLabel from "@/components/SourceLabel";

const matchLevelConfig = {
  Exact: "bg-emerald-50 text-emerald-700 border-emerald-200",
  Partial: "bg-amber-50 text-amber-700 border-amber-200",
  Alternative: "bg-blue-50 text-blue-700 border-blue-200",
};

function safeDecode(s) {
  try {
    return decodeURIComponent(s);
  } catch {
    return s;
  }
}

export default function FormulaResultCard({ doc, onToggleSelect, disabled }) {
  const fileUrl = `/api/documents/${doc.id}/file`;
  return (
    <div className={cn(
      "rounded-xl border bg-white p-4 sm:p-5 transition-colors",
      doc.selected ? "border-teal-300 ring-1 ring-teal-200" : "border-slate-200"
    )}>
      <div className="flex flex-wrap items-center gap-2 mb-1.5">
        <SourceLabel source={doc.source_name} />
        {doc.match_level && (
          <span className={cn("inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border", matchLevelConfig[doc.match_level])}>
            {doc.match_level}
          </span>
        )}
        <span className="text-xs text-slate-400">{doc.origin === "automated" ? "Automated download" : "Uploaded"}</span>
      </div>
      <p className="font-medium text-slate-900 break-words">
        {doc.title ? safeDecode(doc.title) : doc.file_name || "Untitled formula"}
      </p>
      <div className="mt-1 text-xs text-slate-500 flex flex-wrap gap-x-4 gap-y-1">
        {doc.source_formula_id && <span>Ref: {doc.source_formula_id}</span>}
        <span>Retrieved {formatDate(doc.retrieved_at)}</span>
        {doc.file_size ? <span>{Math.max(1, Math.round(doc.file_size / 1024))} KB</span> : null}
      </div>
      <div className="flex flex-wrap items-center gap-4 mt-3">
        <a href={fileUrl} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-sm text-teal-700 hover:text-teal-800 py-1">
          <FileText className="w-4 h-4" /> View PDF
        </a>
        <a href={fileUrl} download={doc.file_name || "formula.pdf"}
          className="inline-flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900 py-1">
          <Download className="w-4 h-4" /> Download
        </a>
        {doc.source_url && (
          <a href={doc.source_url} target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-sm text-teal-700 hover:text-teal-800 py-1">
            <ExternalLink className="w-3.5 h-3.5" /> Source
          </a>
        )}
      </div>
      {doc.notes && <p className="mt-3 pt-3 border-t border-slate-100 text-sm text-slate-600 whitespace-pre-wrap">{doc.notes}</p>}
      {onToggleSelect && (
        <label className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between gap-3 cursor-pointer">
          <div>
            <p className="text-sm font-medium text-slate-900 flex items-center gap-1.5">
              {doc.selected && <CheckCircle2 className="w-4 h-4 text-teal-600" />}
              Use for local draft
            </p>
            <p className="text-xs text-slate-400">{doc.selected ? "Included in the next draft" : "Toggle to include"}</p>
          </div>
          <Switch checked={!!doc.selected} disabled={disabled} onCheckedChange={(v) => onToggleSelect(doc.id, v)} />
        </label>
      )}
    </div>
  );
}
