import { FileText, ExternalLink } from "lucide-react";
import SourceLabel from "@/components/SourceLabel";

function safeDecode(s) {
  try {
    return decodeURIComponent(s);
  } catch {
    return s;
  }
}

export default function DraftSourceDocuments({ documents }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 sm:p-6">
      <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wide mb-4">Source documents</h2>
      <div className="space-y-3">
        {documents.map((d) => (
          <div key={d.id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 p-3">
            <div className="flex items-center gap-3 min-w-0">
              <FileText className="w-5 h-5 text-slate-400 shrink-0" />
              <div className="min-w-0">
                <p className="text-sm font-medium text-slate-900 truncate">
                  {d.title ? safeDecode(d.title) : d.file_name || "Untitled formula"}
                </p>
                <div className="flex items-center gap-2 mt-0.5">
                  <SourceLabel source={d.source_name} />
                  {d.source_formula_id && <span className="text-xs text-slate-400 font-mono">{d.source_formula_id}</span>}
                </div>
              </div>
            </div>
            <a href={`/api/documents/${d.id}/file`} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm text-teal-700 hover:text-teal-800 shrink-0 py-1">
              <ExternalLink className="w-3.5 h-3.5" /> Open
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}
