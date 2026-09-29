import React from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, FileEdit, FlaskConical, PlusCircle, Upload } from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import AddSourceFormulaDialog from "@/components/AddSourceFormulaDialog";
import CatalogMatches from "@/components/CatalogMatches";
import FormulaResultCard from "@/components/FormulaResultCard";
import FormulaStatusBadge from "@/components/FormulaStatusBadge";
import SourceLabel from "@/components/SourceLabel";
import SourceSearchJobCard from "@/components/SourceSearchJobCard";
import { ErrorBlock, LoadingBlock } from "@/components/PageState";
import { useAuth } from "@/lib/AuthContext";
import { isJobActive } from "@/lib/sourceSearchJobs";
import { SOURCE_ORDER } from "@/lib/sources";
import { formatDate, formatDateTime } from "@/lib/utils";

export default function SearchRequestDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { canPrepare } = useAuth();
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [uploadInitial, setUploadInitial] = React.useState(undefined);
  const openUpload = (initial) => { setUploadInitial(initial); setDialogOpen(true); };
  const key = ["request", id];

  const { data: config } = useQuery({ queryKey: ["config"], queryFn: () => api.get("/api/config"), staleTime: Infinity });
  const { data: request, isLoading, error, refetch } = useQuery({
    queryKey: key,
    queryFn: () => api.get(`/api/requests/${id}`),
    // Poll only while a background search is running; stop as soon as it ends.
    refetchInterval: (q) => (q.state.data?.jobs?.some((j) => isJobActive(j.status)) ? 2500 : false),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: key });
    queryClient.invalidateQueries({ queryKey: ["requests"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };
  const onError = (err) => toast({ title: "Action failed", description: err.message, variant: "destructive" });

  const retry = useMutation({
    mutationFn: (job) => api.post(`/api/requests/${id}/search`, { source_name: job.source_name }),
    onSuccess: invalidate, onError,
  });
  const cancel = useMutation({ mutationFn: (job) => api.post(`/api/jobs/${job.id}/cancel`), onSuccess: invalidate, onError });
  const select = useMutation({
    mutationFn: ({ docId, selected }) => api.patch(`/api/documents/${docId}`, { selected }),
    onMutate: ({ docId, selected }) =>
      queryClient.setQueryData(key, (old) => old && {
        ...old, documents: old.documents.map((d) => (d.id === docId ? { ...d, selected } : d)),
      }),
    onError: (err) => { onError(err); invalidate(); },
  });
  const createDraft = useMutation({
    mutationFn: (ids) => api.post(`/api/requests/${id}/drafts`, { source_document_ids: ids }),
    onSuccess: (draft) => { invalidate(); navigate(`/drafts/${draft.id}`); },
    onError,
  });

  if (isLoading) return <LoadingBlock />;
  if (error) {
    return (
      <div className="p-4 sm:p-10">
        <ErrorBlock error={error} onRetry={refetch} />
        <Link to="/requests" className="text-teal-700 text-sm ml-4">← Back to requests</Link>
      </div>
    );
  }

  const documents = request.documents;
  const selected = documents.filter((d) => d.selected && d.has_file);
  const groups = {};
  documents.forEach((d) => (groups[d.source_name] ||= []).push(d));
  const grouped = Object.keys(groups)
    .sort((a, b) => (SOURCE_ORDER.indexOf(a) + 1 || 999) - (SOURCE_ORDER.indexOf(b) + 1 || 999))
    .map((source) => ({ source, items: groups[source] }));
  const automated = config?.automated_sources || [];
  const manualSources = request.sources.filter((s) => !automated.includes(s));

  return (
    <div className="p-4 sm:p-6 md:p-10 max-w-5xl mx-auto pb-28 md:pb-10">
      <button onClick={() => navigate("/requests")}
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 mb-4 py-1">
        <ArrowLeft className="w-4 h-4" /> Back to requests
      </button>

      <div className="mb-5">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <span className="text-xs font-mono text-slate-400">{request.number}</span>
          <FormulaStatusBadge status={request.status} />
        </div>
        <h1 className="text-xl sm:text-2xl font-semibold text-slate-900 break-words">{request.active_ingredient}</h1>
        <p className="text-slate-500 mt-1 text-sm sm:text-base">
          {[request.strength, request.dosage_form, request.final_quantity].filter(Boolean).join(" · ")}
        </p>
        <p className="text-xs text-slate-400 mt-1">
          Created {formatDateTime(request.created_at)}{request.exact_match_only ? " · exact match only" : ""}
        </p>
        {request.notes && <p className="mt-3 text-sm text-slate-600 whitespace-pre-wrap">{request.notes}</p>}
      </div>

      {request.drafts.length > 0 && (
        <section className="mb-6">
          <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wide mb-3">Local drafts</h2>
          <ul className="rounded-xl border border-slate-200 bg-white divide-y divide-slate-100 overflow-hidden">
            {request.drafts.map((d) => (
              <li key={d.id}>
                <Link to={`/drafts/${d.id}`} className="flex items-center justify-between gap-3 p-4 hover:bg-slate-50">
                  <div className="min-w-0">
                    <p className="font-medium text-slate-900 truncate">{d.proposed_formula_name || d.number}</p>
                    <p className="text-xs text-slate-400">{d.number} · v{d.version} · {formatDate(d.updated_at)}</p>
                  </div>
                  <FormulaStatusBadge status={d.status} />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <CatalogMatches request={request} onAddPdf={canPrepare ? (initial) => openUpload(initial) : null} />

      {(request.jobs.length > 0 || manualSources.length > 0) && (
        <section className="mb-6">
          <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wide mb-3">Source search</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {request.jobs.map((job) => (
              <SourceSearchJobCard key={job.id} job={job} busy={retry.isPending || cancel.isPending}
                onRetry={canPrepare ? (j) => retry.mutate(j) : null}
                onCancel={canPrepare ? (j) => cancel.mutate(j) : null} />
            ))}
            {manualSources.map((s) => (
              <div key={s} className="rounded-xl border border-dashed border-slate-300 bg-white p-4 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0">
                  <SourceLabel source={s} />
                  <span className="text-xs text-slate-500">Manual — upload the PDF</span>
                </div>
                {canPrepare && (
                  <Button variant="outline" size="sm" onClick={() => openUpload({ source_name: s })}>
                    <Upload className="w-3.5 h-3.5 mr-1" /> Upload
                  </Button>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      <section id="formula-results">
        <div className="flex items-center justify-between gap-3 mb-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Formula results</h2>
            <p className="text-sm text-slate-500">{documents.length} source document{documents.length === 1 ? "" : "s"}</p>
          </div>
          {canPrepare && (
            <Button variant="outline" onClick={() => openUpload(undefined)} className="shrink-0">
              <PlusCircle className="w-4 h-4 sm:mr-2" />
              <span className="hidden sm:inline">Add source formula</span>
            </Button>
          )}
        </div>

        {documents.length === 0 ? (
          <div className="rounded-xl border border-slate-200 bg-white p-10 text-center">
            <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-3">
              <FlaskConical className="w-6 h-6 text-slate-400" />
            </div>
            <p className="text-slate-600 font-medium">No formula results yet</p>
            <p className="text-sm text-slate-400 mt-1">Upload a source PDF, or wait for the automated search.</p>
          </div>
        ) : (
          <div className="space-y-6">
            {grouped.map(({ source, items }) => (
              <div key={source}>
                <div className="flex items-center gap-2 mb-3">
                  <SourceLabel source={source} />
                  <span className="text-sm text-slate-400">{items.length} {items.length === 1 ? "result" : "results"}</span>
                </div>
                <div className="space-y-3">
                  {items.map((doc) => (
                    <FormulaResultCard key={doc.id} doc={doc} disabled={!canPrepare}
                      onToggleSelect={canPrepare ? (docId, v) => select.mutate({ docId, selected: v }) : null} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {canPrepare && documents.length > 0 && (
        <div className="fixed md:static bottom-[calc(4.5rem+env(safe-area-inset-bottom))] inset-x-0 z-20 px-4 md:px-0 md:mt-6">
          <Button
            onClick={() => createDraft.mutate(selected.map((d) => d.id))}
            disabled={selected.length === 0 || createDraft.isPending}
            className="w-full md:w-auto h-12 bg-teal-600 hover:bg-teal-700 shadow-lg md:shadow-none"
          >
            <FileEdit className="w-4 h-4 mr-2" />
            {createDraft.isPending
              ? "Creating…"
              : selected.length === 0
              ? "Select sources to create a draft"
              : `Create local draft from ${selected.length} source${selected.length === 1 ? "" : "s"}`}
          </Button>
        </div>
      )}

      <AddSourceFormulaDialog open={dialogOpen} onOpenChange={setDialogOpen} requestId={id} initial={uploadInitial}
        maxMb={config?.max_upload_mb} onAdded={() => { invalidate(); toast({ title: "Source formula added" }); }} />
    </div>
  );
}
