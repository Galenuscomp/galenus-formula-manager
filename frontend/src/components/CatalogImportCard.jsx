import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Upload } from "lucide-react";
import { api } from "@/api/client";
import { useToast } from "@/components/ui/use-toast";
import { ErrorList } from "@/components/PageState";
import SourceLabel from "@/components/SourceLabel";
import { formatDateTime } from "@/lib/utils";

// Admin: upload a MEDISCA or CompoundingToday catalog export (CSV). The source is
// detected from the file, and its previous catalog is replaced.
export default function CatalogImportCard() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [errors, setErrors] = React.useState(null);
  const { data } = useQuery({ queryKey: ["catalog-summary"], queryFn: () => api.get("/api/catalog/summary") });
  const upload = useMutation({
    mutationFn: (file) => {
      const body = new FormData();
      body.append("file", file);
      return api.upload("/api/catalog/import", body);
    },
    onSuccess: (r) => {
      setErrors(null);
      queryClient.invalidateQueries({ queryKey: ["catalog-summary"] });
      toast({ title: "Catalog imported", description: `${r.count.toLocaleString()} ${r.source} formulas` });
    },
    onError: (err) => setErrors(err.errors?.length ? err.errors : [err.message]),
  });

  return (
    <section className="mt-8 rounded-xl border border-slate-200 bg-white p-5 space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wide flex items-center gap-2">
          <BookOpen className="w-4 h-4" /> Formula catalogs
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          Used for autocomplete in New Formula Search. Upload a newer export to replace a catalog.
        </p>
      </div>
      <ul className="divide-y divide-slate-100">
        {(data || []).map((s) => (
          <li key={s.source} className="py-2 flex items-center justify-between gap-3 text-sm">
            <SourceLabel source={s.source} />
            <span className="text-slate-500 text-right">
              {s.count ? `${s.count.toLocaleString()} formulas · ${formatDateTime(s.imported_at)}` : "Not imported"}
            </span>
          </li>
        ))}
      </ul>
      <ErrorList errors={errors} />
      <label className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-4 py-2 text-sm font-medium cursor-pointer hover:bg-slate-50">
        <Upload className="w-4 h-4" />
        {upload.isPending ? "Importing…" : "Upload catalog CSV"}
        <input type="file" accept=".csv,text/csv" className="hidden" disabled={upload.isPending}
          onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) upload.mutate(f); }} />
      </label>
    </section>
  );
}
