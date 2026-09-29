import { useQuery } from "@tanstack/react-query";
import { BookOpen, ExternalLink, Upload } from "lucide-react";
import { api, qs } from "@/api/client";
import { Button } from "@/components/ui/button";
import SourceLabel from "@/components/SourceLabel";

// Which catalog formulas match this request, so the right PDF is found without
// searching the source sites. "Add PDF" opens the upload with the formula pre-filled.
export default function CatalogMatches({ request, onAddPdf }) {
  const ref = request.catalog_ref;
  const { data: hits = [] } = useQuery({
    queryKey: ["catalog-search", request.active_ingredient, "matches"],
    queryFn: () => api.get(`/api/catalog/search${qs({ q: request.active_ingredient, limit: 8 })}`),
    staleTime: 5 * 60 * 1000,
  });
  const others = hits.filter((h) => !ref || h.source !== ref.source || h.formula_id !== ref.formula_id || h.title !== ref.title);
  if (!ref && others.length === 0) return null;

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
      {onAddPdf && (
        <Button variant="outline" size="sm" className="shrink-0"
          onClick={() => onAddPdf({ source_name: e.source, title: e.title, source_formula_id: e.formula_id, source_url: e.url || "" })}>
          <Upload className="w-3.5 h-3.5 mr-1" /> Add PDF
        </Button>
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
