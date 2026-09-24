import React from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle, Archive, ArrowLeft, CheckCircle2, Download, FileText, GitBranch, Loader2, RotateCcw,
  Save, Send, ShieldCheck, XCircle,
} from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import ActiveIngredientsManager from "@/components/ActiveIngredientsManager";
import DraftEditForm from "@/components/DraftEditForm";
import DraftExtractionPanel from "@/components/DraftExtractionPanel";
import DraftSourceDocuments from "@/components/DraftSourceDocuments";
import FormulaStatusBadge from "@/components/FormulaStatusBadge";
import ReviewSummary from "@/components/ReviewSummary";
import { ErrorBlock, ErrorList, LoadingBlock } from "@/components/PageState";
import { useAuth } from "@/lib/AuthContext";
import {
  generateFormulaName, normalizeActiveIngredients, syncActiveIngredientsToComposition,
} from "@/lib/extractionFields";
import { formatDateTime } from "@/lib/utils";

const CONTENT_KEYS = [
  "active_ingredient", "proposed_formula_name", "strength", "dosage_form", "final_quantity", "ingredients",
  "preparation_method", "equipment", "packaging", "storage_conditions", "bud", "labelling_instructions",
  "warnings", "references", "local_adaptation_notes", "pharmacist_review_notes", "revision_change_notes",
];

function toForm(content = {}) {
  return Object.fromEntries(CONTENT_KEYS.map((k) => [k, content[k] || ""]));
}

const DECISION_LABEL = { approved: "Approved", rejected: "Rejected", returned: "Returned for correction" };

export default function LocalFormulaDraftDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const key = ["draft", id];

  const { data: config } = useQuery({ queryKey: ["config"], queryFn: () => api.get("/api/config"), staleTime: Infinity });
  const { data: draft, isLoading, error, refetch } = useQuery({
    queryKey: key,
    queryFn: () => api.get(`/api/drafts/${id}`),
    refetchInterval: (q) =>
      q.state.data?.extraction_jobs?.some((j) => j.status === "Queued" || j.status === "Running") ? 3000 : false,
  });

  const [form, setForm] = React.useState(toForm());
  const [activeIngredients, setActiveIngredients] = React.useState([]);
  const [review, setReview] = React.useState(null);
  const [dirty, setDirty] = React.useState(false);
  const [actionErrors, setActionErrors] = React.useState(null);
  const [decisionNotes, setDecisionNotes] = React.useState("");
  const loadedVersion = React.useRef(null);

  // Load server content into the form when the draft (or its saved version) changes,
  // but never overwrite unsaved local edits because of background polling.
  React.useEffect(() => {
    if (!draft) return;
    const marker = `${draft.id}:${draft.row_version}`;
    if (loadedVersion.current === marker) return;
    loadedVersion.current = marker;
    setForm(toForm(draft.content));
    setActiveIngredients(draft.content?.active_ingredients || []);
    setReview(draft.content?.review || null);
    setDirty(false);
  }, [draft]);

  React.useEffect(() => {
    if (!dirty) return undefined;
    const warn = (e) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const updateForm = (updater) => {
    setForm(updater);
    setDirty(true);
  };

  const refresh = (updated) => {
    if (updated?.id) queryClient.setQueryData(key, updated);
    queryClient.invalidateQueries({ queryKey: ["request", draft?.request_id] });
    queryClient.invalidateQueries({ queryKey: ["requests"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    queryClient.invalidateQueries({ queryKey: ["library"] });
  };
  const fail = (err) => {
    setActionErrors(err.errors?.length ? err.errors : [err.message]);
    if (err.status === 409) refetch();
  };

  const buildContent = () => ({ ...form, active_ingredients: activeIngredients, review });

  const save = useMutation({
    mutationFn: (content) => api.put(`/api/drafts/${id}`, { content, row_version: draft.row_version }),
    onSuccess: (updated) => {
      setActionErrors(null);
      loadedVersion.current = null;
      refresh(updated);
      toast({ title: "Draft saved" });
    },
    onError: fail,
  });

  const submit = useMutation({
    mutationFn: async () => {
      let rowVersion = draft.row_version;
      if (dirty) {
        const saved = await api.put(`/api/drafts/${id}`, { content: buildContent(), row_version: rowVersion });
        rowVersion = saved.row_version;
      }
      return api.post(`/api/drafts/${id}/submit`, { row_version: rowVersion });
    },
    onSuccess: (updated) => {
      setActionErrors(null);
      loadedVersion.current = null;
      refresh(updated);
      toast({ title: "Submitted for pharmacist approval" });
    },
    onError: (err) => {
      fail(err);
      loadedVersion.current = null;
      refetch();
    },
  });

  const decide = useMutation({
    mutationFn: (decision) =>
      api.post(`/api/drafts/${id}/decision`, {
        decision, notes: decisionNotes, content_sha256: draft.content_sha256,
      }),
    onSuccess: (updated, decision) => {
      setActionErrors(null);
      setDecisionNotes("");
      loadedVersion.current = null;
      refresh(updated);
      toast({ title: decision === "approved" ? "Master formula approved" : DECISION_LABEL[decision] });
    },
    onError: fail,
  });

  const revise = useMutation({
    mutationFn: () => api.post(`/api/drafts/${id}/revise`),
    onSuccess: (rev) => { refresh(); navigate(`/drafts/${rev.id}`); },
    onError: fail,
  });
  const archive = useMutation({
    mutationFn: () => api.post(`/api/drafts/${id}/archive`),
    onSuccess: () => { refetch(); refresh(); toast({ title: "Formula archived from the active library" }); },
    onError: fail,
  });
  const reextract = useMutation({
    mutationFn: () => api.post(`/api/drafts/${id}/extract`),
    onSuccess: () => refetch(),
    onError: fail,
  });

  const handleActiveIngredientsChange = (updated) => {
    setActiveIngredients(updated);
    updateForm((prev) => {
      const included = updated.filter((ai) => ai.included_in_local_formula !== false);
      const first = included[0];
      return {
        ...prev,
        proposed_formula_name: generateFormulaName(updated, prev.dosage_form) || prev.proposed_formula_name,
        active_ingredient: first ? [first.ingredient_name, first.salt_form].filter(Boolean).join(" ") : prev.active_ingredient,
        strength: first ? [first.strength_value, first.strength_unit].filter(Boolean).join(" ") : prev.strength,
        ingredients: syncActiveIngredientsToComposition(updated, prev.ingredients),
      };
    });
  };

  const handleApplyExtraction = async ({ values, activeIngredients: extracted, pharmacistNote, sourcesUsed, resolvedConflicts, blankFields }) => {
    const normalized = normalizeActiveIngredients(extracted);
    const first = normalized.find((ai) => ai.included_in_local_formula !== false);
    const merged = {
      ...form,
      ...values,
      proposed_formula_name:
        generateFormulaName(normalized, values.dosage_form || form.dosage_form) || values.proposed_formula_name || form.proposed_formula_name,
      active_ingredient: first ? [first.ingredient_name, first.salt_form].filter(Boolean).join(" ") : form.active_ingredient,
      strength: first ? [first.strength_value, first.strength_unit].filter(Boolean).join(" ") : form.strength,
      ingredients: syncActiveIngredientsToComposition(normalized, values.ingredients || form.ingredients),
    };
    const reviewMeta = {
      sources_used: sourcesUsed,
      resolved_conflicts: resolvedConflicts,
      blank_fields: blankFields,
      reviewed_at: new Date().toISOString(),
      reviewed_by: user?.full_name || user?.email || "",
      pharmacist_note: pharmacistNote,
    };
    const content = { ...toForm(merged), active_ingredients: normalized, review: reviewMeta };
    try {
      const updated = await api.put(`/api/drafts/${id}`, { content, row_version: draft.row_version });
      loadedVersion.current = null;
      refresh(updated);
      return { success: true };
    } catch (err) {
      return { success: false, error: err.message };
    }
  };

  if (isLoading) return <LoadingBlock />;
  if (error) {
    return (
      <div className="p-4 sm:p-10">
        <ErrorBlock error={error} onRetry={refetch} />
        <Link to="/requests" className="text-teal-700 text-sm ml-4">← Back to requests</Link>
      </div>
    );
  }

  const perms = draft.permissions;
  const locked = !perms.can_edit;
  const isApproved = draft.status === "Approved";
  const approval = draft.approval;
  const busy = save.isPending || submit.isPending || decide.isPending || revise.isPending || archive.isPending;
  const pdfUrl = `/api/drafts/${id}/pdf`;

  return (
    <div className="p-4 sm:p-6 md:p-10 max-w-5xl mx-auto pb-24 md:pb-10">
      <button onClick={() => navigate(`/requests/${draft.request_id}`)}
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 mb-4 py-1">
        <ArrowLeft className="w-4 h-4" /> Back to request
      </button>

      <div className="mb-5">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <span className="text-xs font-mono text-slate-400">{draft.number}</span>
          <span className="text-xs font-mono text-slate-400">v{draft.version}</span>
          <FormulaStatusBadge status={draft.status} />
          {draft.archived_at && <span className="text-xs text-slate-500">Archived</span>}
        </div>
        <h1 className="text-xl sm:text-2xl font-semibold text-slate-900 break-words">
          {form.proposed_formula_name || form.active_ingredient || "Local Formula Draft"}
        </h1>
        <p className="text-slate-500 mt-1 text-sm">
          Created {formatDateTime(draft.created_at)}
          {draft.submitted_by && ` · submitted by ${draft.submitted_by.full_name} ${formatDateTime(draft.submitted_at)}`}
        </p>
      </div>

      {isApproved && approval && (
        <div className="mb-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4 sm:p-5">
          <div className="flex items-start gap-3">
            <ShieldCheck className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
            <div className="min-w-0">
              <p className="text-sm font-semibold text-emerald-800">Approved Master Formula · version {draft.version}</p>
              <p className="text-sm text-emerald-700 mt-0.5">
                Approved by {approval.actor_name} (licence {approval.actor_licence}) on {formatDateTime(approval.created_at)}
              </p>
              <p className="text-xs text-emerald-700/80 mt-1 break-all">Content SHA-256 {approval.content_sha256}</p>
            </div>
          </div>
        </div>
      )}

      {draft.status === "Pending pharmacist approval" && !perms.can_decide && (
        <div className="mb-6 rounded-xl border border-violet-200 bg-violet-50 p-4 text-sm text-violet-800">
          Waiting for a pharmacist other than the submitter to review and decide.
        </div>
      )}

      <ReviewSummary review={review} />

      {draft.documents.length > 0 && (
        <div className="mb-6">
          <DraftSourceDocuments documents={draft.documents} />
        </div>
      )}

      {!locked && draft.documents.length > 0 && (
        <div className="mb-6">
          <DraftExtractionPanel draft={draft} form={form} onApply={handleApplyExtraction}
            onReextract={() => reextract.mutate()} reextracting={reextract.isPending}
            aiEnabled={config?.ai_enabled !== false} />
        </div>
      )}

      <div className="mb-6 rounded-xl border border-slate-200 bg-white p-4 sm:p-6">
        <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wide mb-3">Active ingredients</h2>
        <ActiveIngredientsManager activeIngredients={activeIngredients} draftId={draft.id}
          onChanged={handleActiveIngredientsChange} locked={locked} user={user} />
      </div>

      <div className="mb-6">
        <DraftEditForm form={form} onChange={updateForm} locked={locked}
          hasActiveIngredients={activeIngredients.length > 0} isRevision={draft.version > 1} />
      </div>

      {!isApproved && draft.approval_errors.length > 0 && (
        <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <p className="text-sm font-medium text-amber-800 mb-1.5">
            Before this draft can be approved{dirty ? " (as last saved)" : ""}:
          </p>
          <ul className="space-y-1">
            {draft.approval_errors.map((e, i) => (
              <li key={i} className="text-sm text-amber-800 flex items-start gap-1.5">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" /> {e}
              </li>
            ))}
          </ul>
        </div>
      )}

      {perms.can_decide && (
        <div className="mb-6 rounded-xl border border-slate-200 bg-white p-4 sm:p-6 space-y-3">
          <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wide">Pharmacist decision</h2>
          <p className="text-xs text-slate-500">
            You are deciding on exactly the content shown above (hash {draft.content_sha256.slice(0, 12)}…). Your name
            and licence number {user?.licence_number || "(missing — ask an admin)"} are recorded from your profile.
            This is an identified approval record, not a qualified electronic signature.
          </p>
          <Textarea rows={3} value={decisionNotes} onChange={(e) => setDecisionNotes(e.target.value)}
            placeholder="Decision notes (required to reject or return)" className="text-base" />
          <div className="grid grid-cols-1 sm:flex gap-2">
            <Button onClick={() => decide.mutate("approved")} disabled={busy}
              className="bg-emerald-600 hover:bg-emerald-700 h-11">
              {decide.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <CheckCircle2 className="w-4 h-4 mr-2" />}
              Approve Master Formula
            </Button>
            <Button onClick={() => decide.mutate("returned")} disabled={busy} variant="outline" className="h-11">
              <RotateCcw className="w-4 h-4 mr-2" /> Return for correction
            </Button>
            <Button onClick={() => decide.mutate("rejected")} disabled={busy} variant="outline"
              className="border-rose-300 text-rose-700 hover:bg-rose-50 h-11">
              <XCircle className="w-4 h-4 mr-2" /> Reject
            </Button>
          </div>
        </div>
      )}

      {draft.decisions.length > 0 && (
        <div className="mb-6 rounded-xl border border-slate-200 bg-white p-4 sm:p-6">
          <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wide mb-3">Decision history</h2>
          <ul className="space-y-3">
            {draft.decisions.map((d) => (
              <li key={d.id} className="text-sm">
                <p className="text-slate-900">
                  <span className="font-medium">{DECISION_LABEL[d.decision]}</span> by {d.actor_name}
                  {d.actor_licence ? ` (licence ${d.actor_licence})` : ""} · {formatDateTime(d.created_at)}
                </p>
                {d.notes && <p className="text-slate-600 whitespace-pre-wrap mt-0.5">{d.notes}</p>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {draft.revisions.length > 1 && (
        <div className="mb-6 rounded-xl border border-slate-200 bg-white p-4 sm:p-6">
          <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wide mb-3">Versions</h2>
          <ul className="divide-y divide-slate-100">
            {draft.revisions.map((r) => (
              <li key={r.id}>
                <Link to={`/drafts/${r.id}`} className="flex items-center justify-between gap-3 py-2.5">
                  <span className={`text-sm ${r.id === draft.id ? "font-semibold text-slate-900" : "text-slate-700"}`}>
                    v{r.version} · {r.number}
                  </span>
                  <FormulaStatusBadge status={r.status} />
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      {actionErrors && <div className="mb-4"><ErrorList errors={actionErrors} /></div>}

      {/* Action bar: one compact row pinned above the bottom navigation on phones */}
      <div className="fixed md:static bottom-[calc(4.5rem+env(safe-area-inset-bottom))] inset-x-0 z-20 bg-white/95 md:bg-transparent backdrop-blur border-t md:border-0 border-slate-200 px-3 py-2 md:p-0">
        <div className="flex gap-2 max-w-5xl mx-auto">
          {perms.can_edit && (
            <Button onClick={() => save.mutate(buildContent())} disabled={busy || !dirty} variant="outline"
              className="flex-1 md:flex-none h-11 px-3">
              <Save className="w-4 h-4 sm:mr-2" />
              <span className="ml-1.5 sm:ml-0">{save.isPending ? "Saving…" : dirty ? "Save" : "Saved"}</span>
            </Button>
          )}
          {perms.can_submit && (
            <Button onClick={() => submit.mutate()} disabled={busy}
              className="flex-[2] md:flex-none h-11 px-3 bg-teal-600 hover:bg-teal-700">
              {submit.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Send className="w-4 h-4 mr-2" />}
              Submit<span className="hidden sm:inline">&nbsp;for approval</span>
            </Button>
          )}
          {perms.can_revise && (
            <Button onClick={() => revise.mutate()} disabled={busy}
              className="flex-[2] md:flex-none h-11 px-3 bg-teal-600 hover:bg-teal-700">
              <GitBranch className="w-4 h-4 mr-2" /> New revision
            </Button>
          )}
          <a href={pdfUrl} target="_blank" rel="noopener noreferrer" aria-label={isApproved ? "Approved PDF" : "Preview PDF"}
            className={perms.can_edit || perms.can_revise ? "shrink-0" : "flex-1 md:flex-none"}>
            <Button variant="outline" className="w-full h-11 px-3">
              <FileText className="w-4 h-4" />
              <span className={perms.can_edit || perms.can_revise ? "hidden sm:inline ml-2" : "ml-2"}>
                {isApproved ? "Approved PDF" : "Preview PDF"}
              </span>
            </Button>
          </a>
          {isApproved && (
            <a href={pdfUrl} download={`${draft.number}-v${draft.version}.pdf`} className="hidden md:block">
              <Button variant="outline" className="h-11"><Download className="w-4 h-4 mr-2" /> Download</Button>
            </a>
          )}
          {isApproved && user?.role === "pharmacist" && !draft.archived_at && (
            <Button onClick={() => archive.mutate()} disabled={busy} variant="outline" aria-label="Archive"
              className="h-11 px-3 text-slate-600 shrink-0">
              <Archive className="w-4 h-4" /><span className="hidden sm:inline ml-2">Archive</span>
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
