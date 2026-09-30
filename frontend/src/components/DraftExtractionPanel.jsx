import React from "react";
import { Link } from "react-router-dom";
import { Sparkles, CheckCircle2, AlertCircle, Loader2, ChevronDown, ChevronUp, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import SourceLabel from "@/components/SourceLabel";
import ExtractionComparisonTable from "@/components/ExtractionComparisonTable";
import ActiveIngredientsTable from "@/components/ActiveIngredientsTable";
import {
  computeInitialReviewState,
  reviewStateToDraftValues,
  countExtractedFields,
  formatSourceValue,
  validateDraftValues,
  validateSearchMatch,
  normalizeActiveIngredients,
  COMPARISON_FIELDS,
} from "@/lib/extractionFields";
import { useAuth } from "@/lib/AuthContext";
import { cn } from "@/lib/utils";
import { formatDateTime } from "@/lib/utils";

const progressSteps = [
  "Queued",
  "Reading PDF",
  "Extracting formula data",
  "Preparing comparison",
  "Extraction completed",
];

// Same active ingredients (names and strengths) in two sources need no choice.
function aiSignature(source) {
  return (source.data?.active_ingredients || [])
    .map((ai) => `${(ai.name || "").toLowerCase().trim()}|${ai.concentration || ""}${ai.concentration_unit || ""}`)
    .sort().join(";");
}

// Extraction runs on the server in the background. This panel only reads the
// stored results, so leaving the page or refreshing never loses or repeats work.
function deriveSources(draft) {
  const latestJob = {};
  (draft.extraction_jobs || []).forEach((j) => {
    const prev = latestJob[j.source_document_id];
    if (!prev || (j.created_at || "") > (prev.created_at || "")) latestJob[j.source_document_id] = j;
  });
  return (draft.documents || []).map((doc) => {
    const ext = draft.extractions?.[doc.id];
    const job = latestJob[doc.id];
    const fieldCount = ext ? countExtractedFields(ext.output) : 0;
    let status = "idle";
    let error = null;
    if (ext) {
      status = fieldCount > 0 ? "done" : "error";
      if (!fieldCount) error = "No structured formula information was detected.";
    } else if (job && (job.status === "Queued" || job.status === "Running")) {
      status = job.status === "Running" ? "reading" : "pending";
    } else if (job && job.status === "Failed") {
      status = "error";
      error = job.error || "Extraction failed";
    }
    return {
      sourceName: doc.source_name || "Unknown",
      formulaId: doc.id,
      status,
      error,
      data: ext?.output || null,
      completedAt: ext?.created_at || null,
      model: ext ? `${ext.provider} · ${ext.model}` : null,
      attempts: job?.attempts || 0,
      fieldCount,
    };
  });
}

export default function DraftExtractionPanel({ draft, form = {}, onApply, onReextract, reextracting = false, aiEnabled = true }) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const sources = React.useMemo(() => deriveSources(draft), [draft]);
  const [reviewState, setReviewState] = React.useState({});
  const [pharmacistNote, setPharmacistNote] = React.useState("");
  const [showDiagnostics, setShowDiagnostics] = React.useState(false);
  const [confirmPhase, setConfirmPhase] = React.useState("idle"); // idle | confirming | applied
  const [pendingApply, setPendingApply] = React.useState(null);
  const [applyError, setApplyError] = React.useState(null);
  const [applying, setApplying] = React.useState(false);
  const [validationResult, setValidationResult] = React.useState(null);
  const [activeIngredients, setActiveIngredients] = React.useState([]);
  const [aiSourceId, setAiSourceId] = React.useState(null); // which source's active ingredients are used
  const [searchMatch, setSearchMatch] = React.useState(null);

  const anyRunning = sources.some((s) => s.status === "pending" || s.status === "reading");
  const anyResult = sources.some((s) => s.status === "done" || s.status === "error");
  const status = anyRunning ? "extracting" : anyResult ? "complete" : "idle";
  const globalProgressStep = sources.some((s) => s.status === "reading") ? 2 : 1;
  const extractionStatus = sources.some((s) => s.status === "done") ? "completed" : anyResult ? "failed" : null;
  const extractionError = sources.find((s) => s.error)?.error || null;
  const extractionCompletedAt = sources.map((s) => s.completedAt).filter(Boolean).sort().pop() || null;
  const needsRetry = sources.some((s) => s.status === "error" || s.status === "idle");
  const handleExtract = () => onReextract?.();

  // (Re)build the comparison only when the set of completed sources changes, so
  // background polling never discards the reviewer's choices.
  const doneKey = sources.filter((s) => s.status === "done").map((s) => s.formulaId).join(",");
  React.useEffect(() => {
    const doneSources = sources.filter((s) => s.status === "done" && s.data);
    if (doneSources.length === 0) {
      setReviewState({});
      setActiveIngredients([]);
      setValidationResult(null);
      setSearchMatch(null);
      return;
    }
    const initialReviewState = computeInitialReviewState(doneSources);
    setReviewState(initialReviewState);
    setConfirmPhase("idle");
    // Active ingredients come from one source. When sources disagree the pharmacist chooses;
    // nothing is picked for them.
    const withAIs = doneSources.filter((s) => s.data?.active_ingredients?.length > 0);
    const agree = withAIs.length > 0 && withAIs.every((s) => aiSignature(s) === aiSignature(withAIs[0]));
    const chosen = withAIs.length === 1 || agree ? withAIs[0] : null;
    setAiSourceId(chosen ? chosen.formulaId : null);
    setActiveIngredients(chosen
      ? normalizeActiveIngredients(chosen.data.active_ingredients, chosen.sourceName, chosen.formulaId) : []);
  }, [doneKey]);

  const chooseAiSource = (formulaId) => {
    const s = sources.find((x) => x.formulaId === formulaId);
    setAiSourceId(formulaId);
    setActiveIngredients(normalizeActiveIngredients(s?.data?.active_ingredients || [], s?.sourceName, s?.formulaId));
  };

  // Kept current as the pharmacist resolves fields: fields that differ between sources are
  // listed apart from fields no source has.
  React.useEffect(() => {
    const unresolved = Object.entries(reviewState).filter(([, s]) => s.conflict && !s.resolved).map(([k]) => k);
    const draftValues = reviewStateToDraftValues(reviewState);
    unresolved.forEach((k) => {
      const field = COMPARISON_FIELDS.find((f) => f.key === k);
      if (field?.draftKey) draftValues[field.draftKey] = "(awaiting choice)";
    });
    const result = validateDraftValues({ ...draftValues, active_ingredients: activeIngredients });
    setValidationResult({
      ...result,
      conflicts: unresolved.map((k) => COMPARISON_FIELDS.find((f) => f.key === k)?.label || k),
    });
    setSearchMatch(draft.request?.active_ingredient && activeIngredients.length > 0
      ? validateSearchMatch(draft.request.active_ingredient, activeIngredients.map((ai) => ({
        ...ai, name: ai.ingredient_name || ai.name })))
      : null);
  }, [reviewState, activeIngredients, draft.request?.active_ingredient]);

  // With AI off for this user, results someone else already extracted are still shown.
  if (!aiEnabled && !anyResult) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4 sm:p-6">
        <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wide">AI extraction</h2>
        <p className="text-sm text-slate-500 mt-2">
          AI extraction is turned off for your account. Choose a provider under{" "}
          <Link to="/account" className="text-teal-700 underline">Account</Link>, or fill in the draft fields
          manually from the source PDFs.
        </p>
      </div>
    );
  }

  const handleUseSource = (fieldKey, sourceFormulaId) => {
    const field = COMPARISON_FIELDS.find((f) => f.key === fieldKey);
    if (!field) return;
    const source = sources.find((s) => s.formulaId === sourceFormulaId);
    if (!source) return;
    const formatted = formatSourceValue(source.data[fieldKey], field.type);
    setReviewState((prev) => ({
      ...prev,
      [fieldKey]: {
        ...prev[fieldKey],
        proposedValue: formatted || "",
        resolved: true,
        reviewMethod: source.sourceName,
      },
    }));
  };

  const handleManualChange = (fieldKey, value) => {
    setReviewState((prev) => ({
      ...prev,
      [fieldKey]: {
        ...prev[fieldKey],
        proposedValue: value,
        resolved: true,
        reviewMethod: "manual",
      },
    }));
  };

  const handleLeaveBlank = (fieldKey) => {
    setReviewState((prev) => ({
      ...prev,
      [fieldKey]: {
        ...prev[fieldKey],
        proposedValue: "",
        resolved: true,
        reviewMethod: "blank-with-note",
      },
    }));
  };

  const doneSources = sources.filter((s) => s.status === "done");
  const errorSources = sources.filter((s) => s.status === "error");
  const extracting = status === "extracting";

  // Apply validation
  const conflictFields = Object.entries(reviewState).filter(([, s]) => s.conflict);
  const unresolvedConflicts = conflictFields.filter(([, s]) => !s.resolved);
  const hasNote = pharmacistNote.trim().length > 0;
  const aiSources = doneSources.filter((s) => s.data?.active_ingredients?.length > 0);
  const aiChoicePending = aiSources.length > 1 && !aiSourceId;
  const canApply = doneSources.length > 0 && unresolvedConflicts.length === 0 && hasNote && !aiChoicePending;

  const validationMessages = [];
  if (aiChoicePending) {
    validationMessages.push("Choose which source's active ingredients to use.");
  }
  if (unresolvedConflicts.length > 0) {
    validationMessages.push(
      `${unresolvedConflicts.length} conflict field${unresolvedConflicts.length === 1 ? "" : "s"} require pharmacist review before applying.`
    );
  }
  if (!hasNote && doneSources.length > 0) {
    validationMessages.push("A pharmacist review note is required before applying reviewed values.");
  }

  const doApply = async (draftValues) => {
    setApplying(true);
    setApplyError(null);
    try {
      const sourcesUsed = doneSources.map((s) => s.sourceName).filter(Boolean);
      const resolvedConflicts = conflictFields.filter(([, s]) => s.resolved).length;
      const blankFields = Object.values(reviewState).filter(
        (s) => s.reviewMethod === "blank-with-note"
      ).length;

      const result = await onApply({
        values: draftValues,
        activeIngredients,
        pharmacistNote,
        sourcesUsed,
        resolvedConflicts,
        blankFields,
      });

      if (result?.success) {
        setConfirmPhase("applied");
      } else {
        setApplyError(result?.error || "Failed to apply reviewed values.");
        setConfirmPhase("idle");
      }
    } catch (err) {
      setApplyError(err?.message || "Failed to apply reviewed values.");
      setConfirmPhase("idle");
    } finally {
      setApplying(false);
    }
  };

  const handleApplyClick = () => {
    setApplyError(null);
    const draftValues = reviewStateToDraftValues(reviewState);
    const overwriteFields = [];

    Object.entries(draftValues).forEach(([key, value]) => {
      if (!value || !String(value).trim()) return;
      const existing = form[key] ? String(form[key]).trim() : "";
      if (existing && existing !== String(value).trim()) {
        overwriteFields.push({ key, oldValue: form[key], newValue: value });
      }
    });

    if (overwriteFields.length > 0) {
      setPendingApply({ draftValues, overwriteFields });
      setConfirmPhase("confirming");
    } else {
      doApply(draftValues);
    }
  };

  const handleConfirmOverwrite = () => {
    if (pendingApply) doApply(pendingApply.draftValues);
  };

  const handleCancelOverwrite = () => {
    setConfirmPhase("idle");
    setPendingApply(null);
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 sm:p-6">
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wide">
          Pharmacist review &amp; local proposal
        </h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Structured extraction with field-by-field comparison and pharmacist review
        </p>
      </div>

      {status === "idle" && (
        <div className="space-y-3">
          {extractionStatus === "failed" && extractionError && (
            <div className="rounded-lg bg-rose-50 border border-rose-200 px-4 py-3">
              <p className="text-sm text-rose-700 flex items-center gap-1.5">
                <AlertCircle className="w-4 h-4 shrink-0" /> {extractionError}
              </p>
            </div>
          )}
          {extractionStatus === "completed" && extractionCompletedAt && (
            <p className="text-xs text-slate-400">
              Last extraction completed {formatDateTime(extractionCompletedAt)}
            </p>
          )}
          <Button onClick={handleExtract} disabled={reextracting} className="bg-violet-600 hover:bg-violet-700">
            <Sparkles className="w-4 h-4 mr-2" />
            {reextracting ? "Queuing…" : "Extract from source PDFs"}
          </Button>
        </div>
      )}

      {extracting && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm font-medium text-violet-700">
            <Loader2 className="w-4 h-4 animate-spin" />
            Extracting from source PDFs in the background…
          </div>
          <p className="text-xs text-slate-500">
            You can leave this page — results are saved on the server and appear here automatically.
          </p>
          <div className="flex flex-wrap gap-2">
            {progressSteps.map((step, i) => (
              <div
                key={step}
                className={cn(
                  "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border",
                  i < globalProgressStep && "bg-emerald-50 text-emerald-700 border-emerald-200",
                  i === globalProgressStep && "bg-violet-50 text-violet-700 border-violet-200",
                  i > globalProgressStep && "bg-slate-50 text-slate-400 border-slate-200"
                )}
              >
                {i < globalProgressStep && <CheckCircle2 className="w-3 h-3" />}
                {i === globalProgressStep && <Loader2 className="w-3 h-3 animate-spin" />}
                {step}
              </div>
            ))}
          </div>

          <div className="space-y-2">
            {sources.map((s) => (
              <div key={s.formulaId} className="flex items-center gap-2 text-sm p-2.5 rounded-md bg-slate-50">
                {s.status === "pending" && <Loader2 className="w-4 h-4 animate-spin text-slate-400" />}
                {s.status === "reading" && <Loader2 className="w-4 h-4 animate-spin text-violet-600" />}
                {s.status === "done" && <CheckCircle2 className="w-4 h-4 text-emerald-600" />}
                {s.status === "error" && <AlertCircle className="w-4 h-4 text-rose-500" />}
                <SourceLabel source={s.sourceName} />
                <span className="text-slate-500">
                  {s.status === "pending" && "Waiting..."}
                  {s.status === "reading" && `Reading PDF and extracting formula data…${s.attempts > 1 ? ` (attempt ${s.attempts})` : ""}`}
                  {s.status === "done" && `Extracted ${s.fieldCount} field${s.fieldCount === 1 ? "" : "s"}`}
                  {s.status === "error" && "Extraction failed"}
                  {s.status === "idle" && "Not extracted yet"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {status === "complete" && errorSources.length > 0 && (
        <div className="mb-4 space-y-2">
          {errorSources.map((s) => (
            <div key={s.formulaId} className="rounded-lg bg-rose-50 border border-rose-200 p-3">
              <div className="flex items-center gap-2 mb-1">
                <AlertCircle className="w-4 h-4 text-rose-600" />
                <span className="text-sm font-medium text-rose-700">{s.sourceName} — extraction failed</span>
              </div>
              <p className="text-xs text-rose-600 ml-6">
                {s.error || "The PDF could not be read or no structured formula information was detected."}
              </p>
            </div>
          ))}
        </div>
      )}

      {status === "complete" && doneSources.length > 0 && (
        <>
          {validationResult?.conflicts?.length > 0 && (
            <div className="mb-3 rounded-lg bg-violet-50 border border-violet-200 px-4 py-3">
              <p className="text-sm font-medium text-violet-800">
                {validationResult.conflicts.length} field{validationResult.conflicts.length === 1 ? " differs" : "s differ"} between
                the sources — choose a value for each below
              </p>
              <div className="flex flex-wrap gap-1.5 mt-1.5">
                {validationResult.conflicts.map((field) => (
                  <span key={field} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-violet-100 text-violet-800 border border-violet-200">
                    {field}
                  </span>
                ))}
              </div>
            </div>
          )}
          {validationResult && !validationResult.isValid && (
            <div className="mb-4 rounded-lg bg-amber-50 border border-amber-200 px-4 py-3">
              <div className="flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-amber-800">Not found in any source</p>
                  <div className="flex flex-wrap gap-1.5 mt-1.5">
                    {validationResult.missing.map((field) => (
                      <span key={field} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800 border border-amber-200">
                        {field}
                      </span>
                    ))}
                  </div>
                  <p className="text-xs text-amber-600 mt-1.5">
                    Enter these manually below (or after applying, in the draft), or retry extraction.
                  </p>
                </div>
              </div>
            </div>
          )}
          {extractionCompletedAt && (
            <p className="text-xs text-slate-400 mb-3">
              Extraction completed {formatDateTime(extractionCompletedAt)}
            </p>
          )}
          {aiSources.length > 0 && (
            <div className="mb-4 space-y-2">
              <h3 className="text-sm font-semibold text-slate-900">Active Ingredients</h3>
              {aiSources.length > 1 && (
                <div className="flex flex-wrap items-center gap-2">
                  <span className={cn("text-xs", aiChoicePending ? "text-violet-700 font-medium" : "text-slate-500")}>
                    {aiChoicePending ? "The sources differ — use active ingredients from:" : "Active ingredients from:"}
                  </span>
                  {aiSources.map((s) => (
                    <button key={s.formulaId} type="button" onClick={() => chooseAiSource(s.formulaId)}
                      className={cn("rounded-lg border px-3 py-1.5 text-xs text-left",
                        aiSourceId === s.formulaId ? "border-teal-400 bg-teal-50" : "border-slate-200 bg-white hover:bg-slate-50")}>
                      <SourceLabel source={s.sourceName} />{" "}
                      <span className="text-slate-600">
                        {s.data.active_ingredients.map((ai) => [ai.name, ai.concentration, ai.concentration_unit].filter(Boolean).join(" ")).join(", ")}
                      </span>
                    </button>
                  ))}
                </div>
              )}
              {!aiChoicePending && (
                <ActiveIngredientsTable activeIngredients={activeIngredients} onChange={setActiveIngredients} />
              )}
            </div>
          )}
          {searchMatch && !searchMatch.match && (
            <div className="mb-4 rounded-lg bg-rose-50 border border-rose-200 px-4 py-3">
              <div className="flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-rose-800">
                    Search ingredient mismatch
                  </p>
                  <p className="text-xs text-rose-700 mt-0.5">
                    The requested ingredient "{draft.request?.active_ingredient}" does not match any extracted active ingredient
                    {searchMatch.unmatched.length > 0 && ` (${searchMatch.unmatched.join(", ")})`}.
                    Verify this is the correct formula.
                  </p>
                </div>
              </div>
            </div>
          )}
          {searchMatch && searchMatch.match && searchMatch.unmatched.length > 0 && (
            <div className="mb-4 rounded-lg bg-blue-50 border border-blue-200 px-4 py-2.5">
              <p className="text-xs text-blue-700">
                <span className="font-medium">Additional active ingredients detected:</span> {searchMatch.unmatched.join(", ")}
              </p>
            </div>
          )}
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="rounded-lg bg-violet-50 border border-violet-200 px-4 py-2.5 flex-1 min-w-0">
              <p className="text-sm text-violet-800 font-medium">
                Review each field below — resolve conflicts and apply reviewed values to the local draft
              </p>
            </div>
            {needsRetry && (
              <Button onClick={handleExtract} variant="outline" className="shrink-0" disabled={applying || reextracting}>
                <RotateCcw className="w-4 h-4 mr-2" />
                Retry failed sources
              </Button>
            )}
          </div>

          <ExtractionComparisonTable
            sources={sources}
            reviewState={reviewState}
            onUseSource={handleUseSource}
            onManualChange={handleManualChange}
            onLeaveBlank={handleLeaveBlank}
          />

          {/* Pharmacist review note + apply */}
          <div className="mt-6 pt-4 border-t border-slate-100 space-y-4">
            <div>
              <label className="text-sm font-medium text-slate-900 mb-1 block">
                Pharmacist review note <span className="text-rose-500">*</span>
              </label>
              <textarea
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
                rows={3}
                placeholder="Document your review decisions, especially for conflicting fields left blank..."
                value={pharmacistNote}
                onChange={(e) => setPharmacistNote(e.target.value)}
                disabled={confirmPhase === "applied"}
              />
              {!hasNote && confirmPhase !== "applied" && (
                <p className="text-xs text-slate-400 mt-1">
                  A review note is required before applying reviewed values.
                </p>
              )}
            </div>

            {confirmPhase === "idle" && (
              <>
                {validationMessages.length > 0 && (
                  <div className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 space-y-1">
                    {validationMessages.map((msg, i) => (
                      <p key={i} className="text-sm text-amber-800 flex items-center gap-1.5">
                        <AlertCircle className="w-4 h-4 shrink-0" /> {msg}
                      </p>
                    ))}
                  </div>
                )}
                {applyError && (
                  <div className="rounded-lg bg-rose-50 border border-rose-200 px-4 py-3">
                    <p className="text-sm text-rose-700 flex items-center gap-1.5">
                      <AlertCircle className="w-4 h-4 shrink-0" /> {applyError}
                    </p>
                  </div>
                )}
                <Button
                  onClick={handleApplyClick}
                  disabled={!canApply || applying}
                  className="bg-violet-600 hover:bg-violet-700"
                >
                  {applying ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <CheckCircle2 className="w-4 h-4 mr-2" />
                  )}
                  {applying ? "Applying..." : "Apply reviewed values to local draft"}
                </Button>
              </>
            )}

            {confirmPhase === "confirming" && pendingApply && (
              <div className="rounded-lg border border-slate-200 p-4 space-y-3">
                <h3 className="text-sm font-semibold text-slate-900">Confirm overwrite</h3>
                <p className="text-xs text-slate-500">
                  Some fields already have manually entered values. Confirm to overwrite them with reviewed values.
                </p>
                <div className="space-y-1.5">
                  {pendingApply.overwriteFields.map((f) => (
                    <div key={f.key} className="flex items-start gap-1.5 flex-wrap text-sm">
                      <span className="font-medium text-slate-900">{f.key}:</span>
                      <span className="text-slate-400 line-through truncate max-w-xs">{f.oldValue}</span>
                      <span className="text-slate-400">→</span>
                      <span className="text-slate-900 truncate max-w-xs">{f.newValue}</span>
                    </div>
                  ))}
                </div>
                <div className="flex gap-2 pt-1">
                  <Button
                    onClick={handleConfirmOverwrite}
                    disabled={applying}
                    className="bg-violet-600 hover:bg-violet-700"
                  >
                    {applying ? (
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <CheckCircle2 className="w-4 h-4 mr-2" />
                    )}
                    {applying ? "Applying..." : "Confirm and apply"}
                  </Button>
                  <Button variant="outline" onClick={handleCancelOverwrite} disabled={applying}>
                    Cancel
                  </Button>
                </div>
              </div>
            )}

            {confirmPhase === "applied" && (
              <div className="inline-flex items-center gap-2 text-sm text-emerald-700">
                <CheckCircle2 className="w-4 h-4" />
                Reviewed values applied and saved to the draft. Review the fields below, then submit for approval.
              </div>
            )}
          </div>
        </>
      )}

      {status === "complete" && doneSources.length === 0 && (
        <div className="rounded-lg bg-slate-50 border border-slate-200 p-4 space-y-3">
          <p className="text-sm text-slate-500">
            Extraction could not be completed for any source document. You can still fill in the draft fields manually below.
          </p>
          <Button onClick={handleExtract} disabled={reextracting} className="bg-violet-600 hover:bg-violet-700">
            <RotateCcw className="w-4 h-4 mr-2" />
            Retry extraction
          </Button>
        </div>
      )}

      {/* Admin diagnostics */}
      {isAdmin && sources.length > 0 && (
        <div className="mt-6 pt-4 border-t border-slate-100">
          <button
            onClick={() => setShowDiagnostics((v) => !v)}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-700"
          >
            {showDiagnostics ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            Development diagnostics
          </button>
          {showDiagnostics && (
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-slate-500">
                    <th className="py-2 pr-3 font-medium">Document ID</th>
                    <th className="py-2 pr-3 font-medium">Source</th>
                    <th className="py-2 pr-3 font-medium">Model</th>
                    <th className="py-2 pr-3 font-medium">Status</th>
                    <th className="py-2 pr-3 font-medium">Field count</th>
                    <th className="py-2 pr-3 font-medium">Error</th>
                  </tr>
                </thead>
                <tbody>
                  {sources.map((s) => (
                    <tr key={s.formulaId} className="border-b border-slate-100 align-top">
                      <td className="py-2 pr-3 font-mono text-slate-600">{s.formulaId}</td>
                      <td className="py-2 pr-3 text-slate-600">{s.sourceName}</td>
                      <td className="py-2 pr-3 text-slate-600">{s.model || "—"}</td>
                      <td className="py-2 pr-3 text-slate-600">{s.status}</td>
                      <td className="py-2 pr-3 text-slate-600">{s.fieldCount}</td>
                      <td className="py-2 pr-3 text-rose-500 max-w-xs break-words">{s.error || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}