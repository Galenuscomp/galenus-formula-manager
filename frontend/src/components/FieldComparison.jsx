import React from "react";
import { CheckCircle2, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import SourceLabel from "@/components/SourceLabel";
import IngredientComparison from "@/components/IngredientComparison";
import {
  formatSourceValue,
  getFieldConfidence,
  isShortTextField,
} from "@/lib/extractionFields";

const confidenceStyles = {
  high: "bg-emerald-50 text-emerald-700 border-emerald-200",
  medium: "bg-amber-50 text-amber-700 border-amber-200",
  low: "bg-slate-100 text-slate-500 border-slate-200",
  "not found": "bg-rose-50 text-rose-600 border-rose-200",
};

const sourceButtonStyles = {
  CompoundingToday: "border-teal-300 text-teal-700 hover:bg-teal-50",
  MEDISCA: "border-indigo-300 text-indigo-700 hover:bg-indigo-50",
};

/**
 * Single field comparison with per-source values, confidence, conflict indicator,
 * action buttons (Use [source] / Enter manually / Leave blank), and proposed local value.
 */
export default function FieldComparison({
  field,
  sources,
  reviewState,
  onUseSource,
  onManualChange,
  onLeaveBlank,
}) {
  const inputRef = React.useRef(null);
  const rs = reviewState || { proposedValue: "", conflict: false, resolved: false, reviewMethod: null };

  const confidence = getFieldConfidence(sources, field);
  const isConflict = !!rs.conflict;
  const isResolved = !!rs.resolved;
  const isShort = isShortTextField(field.key);
  const hasDraftKey = !!field.draftKey;

  // Sort: CompoundingToday first, MEDISCA second, others after
  const sortedSources = [...sources].sort((a, b) => {
    const order = { CompoundingToday: 0, MEDISCA: 1 };
    return (order[a.sourceName] ?? 2) - (order[b.sourceName] ?? 2);
  });

  return (
    <div className={cn(
      "rounded-lg border p-4",
      isConflict && !isResolved && "border-amber-300 bg-amber-50/30",
      isConflict && isResolved && "border-amber-200 bg-white",
      !isConflict && "border-slate-200 bg-white"
    )}>
      {/* Header: label + confidence + conflict/resolved indicators */}
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <span className="text-sm font-medium text-slate-900">{field.label}</span>
        {confidence && (
          <span className={cn("inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border capitalize", confidenceStyles[confidence])}>
            {confidence === "not found" ? "Not found" : `${confidence} confidence`}
          </span>
        )}
        {isConflict && !isResolved && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border bg-amber-50 text-amber-700 border-amber-200">
            <AlertCircle className="w-3 h-3" /> Pharmacist decision required
          </span>
        )}
        {isConflict && isResolved && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border bg-emerald-50 text-emerald-700 border-emerald-200">
            <CheckCircle2 className="w-3 h-3" /> Reviewed
          </span>
        )}
        {rs.reviewMethod && rs.reviewMethod !== "auto-agreed" && !isConflict && (
          <span className="text-xs text-slate-400">via {rs.reviewMethod}</span>
        )}
      </div>

      {/* Per-source values */}
      <div className={cn("grid gap-2 mb-3", sources.length > 1 ? "grid-cols-1 sm:grid-cols-2" : "grid-cols-1")}>
        {sortedSources.map((source) => {
          const formatted = formatSourceValue(source.data[field.key], field.type);
          return (
            <div key={source.formulaId} className={cn("rounded-md border p-2.5", isConflict ? "border-amber-200" : "border-slate-200")}>
              <div className="mb-1">
                <SourceLabel source={source.sourceName} />
              </div>
              <p className={cn("text-sm whitespace-pre-wrap", formatted ? "text-slate-700" : "text-slate-400 italic")}>
                {formatted || "Not found in source document"}
              </p>
            </div>
          );
        })}
      </div>

      {/* Ingredient comparison table */}
      {field.type === "ingredients" && sources.length > 0 && (
        <IngredientComparison sources={sources} />
      )}

      {/* BUD special verification message */}
      {field.special === "bud" && isConflict && (
        <div className="mb-3 rounded-md bg-amber-50 border border-amber-200 px-3 py-2">
          <p className="text-xs text-amber-800">
            BUD requires pharmacist verification against source conditions, packaging, and storage.
            Never automatically select a BUD — review all values and choose manually.
          </p>
        </div>
      )}

      {/* Storage/packaging preserve wording message */}
      {field.preserveWording && isConflict && (
        <div className="mb-3 rounded-md bg-slate-50 border border-slate-200 px-3 py-2">
          <p className="text-xs text-slate-500">
            Source wording preserved exactly — do not simplify or combine conflicting instructions.
          </p>
        </div>
      )}

      {/* Action buttons */}
      {hasDraftKey && (
        <div className="flex flex-wrap gap-2 mb-3">
          {sortedSources.map((source) => {
            const formatted = formatSourceValue(source.data[field.key], field.type);
            if (!formatted) return null;
            return (
              <Button
                key={source.formulaId}
                size="sm"
                variant="outline"
                onClick={() => onUseSource(field.key, source.formulaId)}
                className={sourceButtonStyles[source.sourceName] || "border-slate-300 text-slate-600 hover:bg-slate-50"}
              >
                Use {source.sourceName} value
              </Button>
            );
          })}
          <Button
            size="sm"
            variant="outline"
            onClick={() => inputRef.current?.focus()}
            className="border-violet-300 text-violet-700 hover:bg-violet-50"
          >
            Enter local value manually
          </Button>
          {isConflict && !isResolved && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => onLeaveBlank(field.key)}
              className="border-slate-300 text-slate-500 hover:bg-slate-50"
            >
              Leave blank (reviewed)
            </Button>
          )}
        </div>
      )}

      {/* Proposed local value */}
      {hasDraftKey && (
        <div>
          <label className="text-xs text-slate-500 mb-1 block">Proposed local value</label>
          {isShort ? (
            <input
              ref={inputRef}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
              value={rs.proposedValue || ""}
              onChange={(e) => onManualChange(field.key, e.target.value)}
            />
          ) : (
            <textarea
              ref={inputRef}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
              rows={field.type === "ingredients" ? 6 : 4}
              value={rs.proposedValue || ""}
              onChange={(e) => onManualChange(field.key, e.target.value)}
            />
          )}
          {rs.reviewMethod === "blank-with-note" && (
            <p className="text-xs text-amber-600 mt-1">
              Left blank — pharmacist review note required to apply.
            </p>
          )}
        </div>
      )}
    </div>
  );
}