import { useQuery } from "@tanstack/react-query";
import { BookOpen, Check, Download, ExternalLink, Loader2, Upload } from "lucide-react";
import { api, qs } from "@/api/client";
import { Button } from "@/components/ui/button";
import SourceLabel from "@/components/SourceLabel";

// Which catalog formulas match this request, so the right PDF is found without
// searching the source sites. "Download PDF" has the server fetch it with the
// pharmacy's login (sources in `automated`); "Upload" opens the upload pre-filled.
export default function CatalogMatches({ request, onAddPdf, onDownload, automated = [], busy }) {
  const ref = request.catalog_ref;
  const { data: hits = [] } = useQuery({
    queryKey: ["catalog-search", request.active_ingredient, "matches"],
    queryFn: () => api.get(`/api/catalog/search${qs({ q: request.active_ingredient, limit: 8 })}`),
    staleTime: 5 * 60 * 1000,
  });
  const others = hits.filter((h) => !ref || h.source !== ref.source || h.formula_id !== ref.formula_id || h.title !== ref.title);
  if (!ref && others.length === 0) return null;

  const onRequest = (e) => request.documents?.some((d) => d.source_name === e.source && d.source_formula_id === e.formula_id);
  const downloading = (e) => request.jobs?.some((j) => j.source_name === e.source && j.payload?.formula_id === e.formula_id
    && (j.status === "Queued" || j.status === "Running"));
  const row = (e, chosen) => (
    <li key={`${e.source}-${e.formula_id}-${e.title}`} className="p-3 flex items-start justify-between gap-3">
      <div className="min-w-0 flex items-start gap-2">
        <SourceLabel source={e.source} className="mt-0.5 shrink-0" />
        <div className="min-w-0">
          <p className="text-sm text-slate-900 leading-snug">
            {e.title}{chosen && <span className="ml-2 text-xs font-medium text-teal-700">selected</span>}
          </p>
          <p className="text-xs text-slate-400 flex items-center gap-2">
            <span className="font-mono">{e.formula_id}</span>
            {e.url && (
              <a href={e.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-0.5 text-teal-700 hover:underline">
                Open <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </p>
        </div>
      </div>
      {onRequest(e) ? (
        <span className="shrink-0 text-xs font-medium text-teal-700 flex items-center gap-1"><Check className="w-3.5 h-3.5" /> PDF added</span>
      ) : downloading(e) ? (
        <span className="shrink-0 text-xs text-slate-500 flex items-center gap-1"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Downloading…</span>
      ) : (
        <div className="shrink-0 flex gap-2">
          {onDownload && automated.includes(e.source) && (
            <Button size="sm" disabled={busy} className="bg-teal-600 hover:bg-teal-700"
              onClick={() => onDownload({ source: e.source, formula_id: e.formula_id, title: e.title, url: e.url || "" })}>
              <Download className="w-3.5 h-3.5 mr-1" /> Download PDF
            </Button>
          )}
          {onAddPdf && (
            <Button variant="outline" size="sm"
              onClick={() => onAddPdf({ source_name: e.source, title: e.title, source_formula_id: e.formula_id, source_url: e.url || "" })}>
              <Upload className="w-3.5 h-3.5 mr-1" /> Upload
            </Button>
          )}
        </div>
      )}
    </li>
  );

  return (
    <section className="mb-6">
      <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wide mb-3 flex items-center gap-2">
        <BookOpen className="w-4 h-4" /> In the catalogs
      </h2>
      <ul className="rounded-xl border border-slate-200 bg-white divide-y divide-slate-100">
        {ref && row(ref, true)}
        {others.map((e) => row(e, false))}
      </ul>
    </section>
  );
}
