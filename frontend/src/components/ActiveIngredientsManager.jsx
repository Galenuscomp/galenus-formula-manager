import React from "react";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Pencil,
  RotateCcw,
  Plus,
  Copy,
  ChevronUp,
  ChevronDown,
  FileText,
  Edit3,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDateTime, newId } from "@/lib/utils";

const EXCLUSION_REASONS = [
  "Clinical decision",
  "Not required for local formula",
  "Incorrect extraction",
  "Duplicate ingredient",
  "Replaced by another ingredient",
  "Not locally available",
  "Other",
];

const FUNCTION_OPTIONS = [
  { value: "active", label: "Active ingredient" },
  { value: "additional active", label: "Additional active" },
];

const CONFIDENCE_CONFIG = {
  high: "bg-emerald-50 text-emerald-700 border-emerald-200",
  medium: "bg-amber-50 text-amber-700 border-amber-200",
  low: "bg-rose-50 text-rose-600 border-rose-200",
};

function safeDecode(s) {
  if (!s) return s;
  try {
    return decodeURIComponent(s);
  } catch {
    return s;
  }
}

function parseSourceValue(sv) {
  if (!sv) return null;
  if (typeof sv === "object") return sv;
  try {
    return JSON.parse(sv);
  } catch {
    return null;
  }
}

function newIngredientData(draftId, sortOrder) {
  return {
    local_formula_draft_id: draftId,
    source_formula_id: "",
    ingredient_name: "",
    salt_form: "",
    strength_value: "",
    strength_unit: "",
    concentration_value: "",
    concentration_unit: "",
    quantity_value: "",
    quantity_unit: "",
    function: "active",
    source_value: "",
    proposed_local_value: "",
    confidence: "medium",
    included_in_local_formula: true,
    exclusion_reason: "",
    sort_order: sortOrder,
    review_status: "pending",
    manually_edited: false,
    edited_by: "",
    edited_at: "",
  };
}

function ActiveIngredientCard({
  ai,
  index,
  total,
  onUpdate,
  onToggle,
  onDuplicate,
  onMove,
  onUseSource,
  locked,
}) {
  const isIncluded = ai.included_in_local_formula !== false;
  const isEdited = ai.manually_edited === true;
  const confidence = (ai.confidence || "").toLowerCase();
  const sv = parseSourceValue(ai.source_value);
  const hasSource = sv && (sv.ingredient_name || sv.strength_value || sv.name);

  const sourceStr = sv
    ? [
        [sv.ingredient_name || sv.name, sv.salt_form].filter(Boolean).join(" "),
        [
          sv.strength_value || sv.strength || sv.concentration,
          sv.strength_unit || sv.concentration_unit,
        ]
          .filter(Boolean)
          .join(" "),
      ]
        .filter(Boolean)
        .join(" — ")
    : null;

  return (
    <div
      className={cn(
        "rounded-lg border p-4 transition-colors",
        isIncluded ? "border-slate-200 bg-white" : "border-slate-200 bg-slate-50"
      )}
    >
      {/* Header */}
      <div className="flex items-start gap-3 mb-3">
        <Switch
          checked={isIncluded}
          onCheckedChange={(checked) => onToggle(ai.id, checked)}
          disabled={locked}
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-slate-900">
              {safeDecode(ai.ingredient_name) || "New ingredient"}
            </span>
            {ai.salt_form && (
              <span className="text-sm text-slate-500">{ai.salt_form}</span>
            )}
            {confidence && (
              <span
                className={cn(
                  "inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium border capitalize",
                  CONFIDENCE_CONFIG[confidence] ||
                    "bg-slate-50 text-slate-500 border-slate-200"
                )}
              >
                {confidence}
              </span>
            )}
            {isEdited && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
                <Pencil className="w-3 h-3" /> Edited
              </span>
            )}
            {!isIncluded && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200">
                Excluded
              </span>
            )}
          </div>
          {ai.review_status && (
            <p className="text-xs text-slate-400 mt-0.5 capitalize">
              Review: {ai.review_status}
            </p>
          )}
        </div>
        {/* Card actions: reorder + duplicate */}
        {!locked && (
          <div className="flex items-center gap-0.5 shrink-0">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => onMove(index, -1)}
              disabled={index === 0}
              title="Move up"
            >
              <ChevronUp className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => onMove(index, 1)}
              disabled={index === total - 1}
              title="Move down"
            >
              <ChevronDown className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => onDuplicate(index)}
              title="Duplicate ingredient"
            >
              <Copy className="w-4 h-4" />
            </Button>
          </div>
        )}
      </div>

      {/* Original source value */}
      {hasSource && (
        <div className="mb-3 rounded-md bg-slate-50 border border-slate-100 px-3 py-2">
          <p className="text-xs font-medium text-slate-400 mb-0.5 flex items-center gap-1">
            <FileText className="w-3 h-3" /> Original source value
          </p>
          <p className="text-sm text-slate-600">{safeDecode(sourceStr)}</p>
        </div>
      )}

      {/* Included + editable: proposed local value */}
      {isIncluded && !locked && (
        <div className="space-y-3">
          <p className="text-xs font-medium text-slate-500">Proposed local value</p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <div>
              <Label className="text-xs text-slate-500">Ingredient name</Label>
              <Input
                value={ai.ingredient_name || ""}
                onChange={(e) => onUpdate(ai.id, "ingredient_name", e.target.value)}
                className="h-8 text-sm"
              />
            </div>
            <div>
              <Label className="text-xs text-slate-500">Salt form</Label>
              <Input
                value={ai.salt_form || ""}
                onChange={(e) => onUpdate(ai.id, "salt_form", e.target.value)}
                className="h-8 text-sm"
              />
            </div>
            <div>
              <Label className="text-xs text-slate-500">Strength value</Label>
              <Input
                value={ai.strength_value || ""}
                onChange={(e) => onUpdate(ai.id, "strength_value", e.target.value)}
                className="h-8 text-sm"
                placeholder="e.g. 10"
              />
            </div>
            <div>
              <Label className="text-xs text-slate-500">Strength unit</Label>
              <Input
                value={ai.strength_unit || ""}
                onChange={(e) => onUpdate(ai.id, "strength_unit", e.target.value)}
                className="h-8 text-sm"
                placeholder="e.g. mg/suppository"
              />
            </div>
            <div>
              <Label className="text-xs text-slate-500">Quantity value</Label>
              <Input
                value={ai.quantity_value || ""}
                onChange={(e) => onUpdate(ai.id, "quantity_value", e.target.value)}
                className="h-8 text-sm"
                placeholder="e.g. 1"
              />
            </div>
            <div>
              <Label className="text-xs text-slate-500">Quantity unit</Label>
              <Input
                value={ai.quantity_unit || ""}
                onChange={(e) => onUpdate(ai.id, "quantity_unit", e.target.value)}
                className="h-8 text-sm"
                placeholder="e.g. g"
              />
            </div>
            <div>
              <Label className="text-xs text-slate-500">Function</Label>
              <Select
                value={ai.function || "active"}
                onValueChange={(v) => onUpdate(ai.id, "function", v)}
              >
                <SelectTrigger className="h-8 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {FUNCTION_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          {hasSource && (
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => onUseSource(ai.id)}>
                <FileText className="w-3 h-3 mr-1.5" />
                Use source value
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  onUpdate(ai.id, "strength_value", "") ||
                  onUpdate(ai.id, "quantity_value", "")
                }
              >
                <Edit3 className="w-3 h-3 mr-1.5" />
                Enter local value manually
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Included + locked: read-only display */}
      {isIncluded && locked && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
          <div>
            <span className="text-slate-400">Strength:</span>{" "}
            {ai.strength_value || "—"} {ai.strength_unit || ""}
          </div>
          <div>
            <span className="text-slate-400">Qty.:</span>{" "}
            {ai.quantity_value || "—"} {ai.quantity_unit || ""}
          </div>
          <div>
            <span className="text-slate-400">Function:</span>{" "}
            {ai.function || "—"}
          </div>
        </div>
      )}

      {/* Excluded: reason + re-include */}
      {!isIncluded && (
        <div className="space-y-3">
          <div>
            <Label className="text-xs text-slate-500">
              Exclusion reason <span className="text-rose-500">*</span>
            </Label>
            <Select
              value={ai.exclusion_reason || ""}
              onValueChange={(v) => onUpdate(ai.id, "exclusion_reason", v)}
              disabled={locked}
            >
              <SelectTrigger className="h-8 text-sm">
                <SelectValue placeholder="Select reason..." />
              </SelectTrigger>
              <SelectContent>
                {EXCLUSION_REASONS.map((r) => (
                  <SelectItem key={r} value={r}>
                    {r}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {!locked && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onToggle(ai.id, true)}
            >
              <RotateCcw className="w-3 h-3 mr-1.5" />
              Re-include
            </Button>
          )}
        </div>
      )}

      {/* Audit footer */}
      {isEdited && ai.edited_by && ai.edited_at && (
        <div className="mt-3 pt-3 border-t border-slate-100 text-xs text-slate-400">
          Edited by {ai.edited_by} on{" "}
          {formatDateTime(ai.edited_at)}
        </div>
      )}
    </div>
  );
}

export default function ActiveIngredientsManager({
  activeIngredients = [],
  draftId = "",
  onChanged,
  locked = false,
  user = null,
}) {
  // Ingredients live in the draft content and are saved with the draft; this
  // component only edits the list in memory.
  const list = activeIngredients || [];
  const editor = () => ({
    manually_edited: true,
    edited_by: user?.full_name || user?.email || "",
    edited_at: new Date().toISOString(),
    review_status: "reviewed",
  });
  const withOrder = (items) => items.map((ai, i) => ({ ...ai, sort_order: i }));

  const handleFieldUpdate = (id, field, value) => {
    onChanged(list.map((ai) => (ai.id === id ? { ...ai, [field]: value, ...editor() } : ai)));
  };

  const handleToggle = (id, included) => {
    onChanged(
      list.map((ai) =>
        ai.id === id
          ? {
              ...ai,
              included_in_local_formula: included,
              exclusion_reason: included ? "" : ai.exclusion_reason,
              review_status: included ? "pending" : "excluded",
            }
          : ai
      )
    );
  };

  const handleAdd = () => {
    onChanged([...list, { ...newIngredientData(draftId, list.length), id: newId() }]);
  };

  const handleDuplicate = (index) => {
    const original = list[index];
    const copy = {
      ...newIngredientData(draftId, index + 1),
      ...Object.fromEntries(
        [
          "ingredient_name", "salt_form", "strength_value", "strength_unit", "concentration_value",
          "concentration_unit", "quantity_value", "quantity_unit", "function", "confidence",
          "source_value", "source_formula_id",
        ].map((k) => [k, original[k] ?? ""])
      ),
      id: newId(),
    };
    const updated = [...list];
    updated.splice(index + 1, 0, copy);
    onChanged(withOrder(updated));
  };

  const handleMove = (index, direction) => {
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= list.length) return;
    const updated = [...list];
    [updated[index], updated[newIndex]] = [updated[newIndex], updated[index]];
    onChanged(withOrder(updated));
  };

  const handleUseSource = (id) => {
    const ai = list.find((a) => a.id === id);
    const sv = ai && parseSourceValue(ai.source_value);
    if (!sv) return;
    onChanged(
      list.map((a) =>
        a.id === id
          ? {
              ...a,
              ingredient_name: sv.ingredient_name || sv.name || a.ingredient_name,
              salt_form: sv.salt_form || a.salt_form,
              strength_value: sv.strength_value || sv.strength || sv.concentration || "",
              strength_unit: sv.strength_unit || sv.concentration_unit || "",
              quantity_value: sv.quantity_value || "",
              quantity_unit: sv.quantity_unit || a.quantity_unit,
              function: sv.function || a.function || "active",
              ...editor(),
            }
          : a
      )
    );
  };

  return (
    <div className="space-y-3">
      {list.length === 0 && (
        <p className="text-sm text-slate-400 italic">
          No active ingredients identified. Click "Add active ingredient" to create one manually.
        </p>
      )}

      {list.map((ai, i) => (
        <ActiveIngredientCard
          key={ai.id || i}
          ai={ai}
          index={i}
          total={list.length}
          onUpdate={handleFieldUpdate}
          onToggle={handleToggle}
          onDuplicate={handleDuplicate}
          onMove={handleMove}
          onUseSource={handleUseSource}
          locked={locked}
        />
      ))}

      {!locked && (
        <Button variant="outline" size="sm" onClick={handleAdd}>
          <Plus className="w-4 h-4 mr-1.5" />
          Add active ingredient
        </Button>
      )}
    </div>
  );
}