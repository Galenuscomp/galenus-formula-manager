import React from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { FileText, Library, Search } from "lucide-react";
import { api, qs } from "@/api/client";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { ErrorBlock, LoadingBlock } from "@/components/PageState";
import { useDebounced } from "@/lib/useDebounced";
import { formatDate } from "@/lib/utils";

export default function ApprovedLibrary() {
  const [query, setQuery] = React.useState("");
  const [showArchived, setShowArchived] = React.useState(false);
  const q = useDebounced(query.trim());
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["library", q, showArchived],
    queryFn: () => api.get(`/api/library${qs({ q, include_archived: showArchived || "", limit: 200 })}`),
  });

  return (
    <div className="p-4 sm:p-6 md:p-10 max-w-6xl mx-auto">
      <div className="flex items-center gap-3 mb-5 sm:mb-6">
        <div className="w-10 h-10 rounded-lg bg-teal-50 flex items-center justify-center">
          <Library className="w-5 h-5 text-teal-600" />
        </div>
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold text-slate-900">Approved Library</h1>
          <p className="text-sm text-slate-500">Pharmacist-approved master formulas</p>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 mb-5">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <Input type="search" placeholder="Formula name, ingredient or number…" value={query}
            onChange={(e) => setQuery(e.target.value)} className="pl-9 h-11 text-base" />
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-600 px-1">
          <Switch checked={showArchived} onCheckedChange={setShowArchived} /> Show archived
        </label>
      </div>

      {isLoading ? (
        <LoadingBlock />
      ) : error ? (
        <ErrorBlock error={error} onRetry={refetch} />
      ) : data.items.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-slate-600">
          {q ? "No matching formulas" : "No approved formulas yet"}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">
          {data.items.map((d) => (
            <div key={d.id} className="rounded-xl border border-slate-200 bg-white p-4 sm:p-5 flex flex-col">
              <div className="flex flex-wrap items-center gap-2 mb-1.5">
                <span className="text-xs font-mono text-slate-400">{d.number} · v{d.version}</span>
                {d.superseded && (
                  <span className="text-xs px-2 py-0.5 rounded-full border bg-amber-50 text-amber-700 border-amber-200">
                    Superseded
                  </span>
                )}
                {d.archived_at && (
                  <span className="text-xs px-2 py-0.5 rounded-full border bg-slate-100 text-slate-600 border-slate-200">
                    Archived
                  </span>
                )}
              </div>
              <Link to={`/drafts/${d.id}`} className="font-medium text-slate-900 hover:text-teal-700 break-words">
                {d.proposed_formula_name || d.active_ingredient}
              </Link>
              <p className="text-sm text-slate-500 mt-0.5">
                {[d.strength, d.dosage_form].filter(Boolean).join(" · ")}
              </p>
              {d.approval && (
                <p className="text-xs text-slate-400 mt-2">
                  Approved by {d.approval.actor_name} · {formatDate(d.approval.created_at)}
                </p>
              )}
              <div className="mt-3 pt-3 border-t border-slate-100 flex gap-4">
                <a href={`/api/drafts/${d.id}/pdf`} target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-sm text-teal-700 hover:text-teal-800 py-1">
                  <FileText className="w-4 h-4" /> Approved PDF
                </a>
                <Link to={`/drafts/${d.id}`} className="text-sm text-slate-600 hover:text-slate-900 py-1">
                  Details →
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
