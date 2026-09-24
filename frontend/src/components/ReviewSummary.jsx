import { User, Calendar, FileText, CheckCircle2, AlertCircle, StickyNote } from "lucide-react";
import { formatDateTime } from "@/lib/utils";

export default function ReviewSummary({ review }) {
  if (!review?.reviewed_at) return null;
  const sources = review.sources_used || [];
  const items = [
    { icon: User, label: "Extraction reviewed by", value: review.reviewed_by || "—" },
    { icon: Calendar, label: "Review date", value: formatDateTime(review.reviewed_at) },
    { icon: CheckCircle2, label: "Resolved conflicts", value: String(review.resolved_conflicts ?? 0) },
    { icon: AlertCircle, label: "Fields intentionally left blank", value: String(review.blank_fields ?? 0) },
  ];
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 sm:p-6 mb-6">
      <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wide mb-4">Extraction review summary</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {items.map(({ icon: Icon, label, value }) => (
          <div key={label} className="flex items-center gap-2.5">
            <Icon className="w-4 h-4 text-slate-400 shrink-0" />
            <div>
              <p className="text-xs text-slate-400">{label}</p>
              <p className="text-sm text-slate-900">{value}</p>
            </div>
          </div>
        ))}
        <div className="flex items-start gap-2.5 sm:col-span-2">
          <FileText className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-xs text-slate-400">Sources used</p>
            <div className="flex flex-wrap gap-1 mt-1">
              {sources.length ? sources.map((s, i) => (
                <span key={i} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border bg-slate-50 text-slate-700 border-slate-200">{s}</span>
              )) : <span className="text-sm text-slate-400">—</span>}
            </div>
          </div>
        </div>
      </div>
      {review.pharmacist_note && (
        <div className="mt-4 pt-4 border-t border-slate-100 flex items-start gap-2.5">
          <StickyNote className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
          <div className="min-w-0">
            <p className="text-xs text-slate-400 mb-1">Review note</p>
            <p className="text-sm text-slate-700 whitespace-pre-wrap">{review.pharmacist_note}</p>
          </div>
        </div>
      )}
    </div>
  );
}
