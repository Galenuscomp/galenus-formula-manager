import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn, newId } from "@/lib/utils";

const functionConfig = {
  "active": { label: "Active ingredient", className: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  "additional active": { label: "Additional active", className: "bg-blue-50 text-blue-700 border-blue-200" },
  "primary": { label: "Active ingredient", className: "bg-emerald-50 text-emerald-700 border-emerald-200" },
};

const confidenceConfig = {
  "high": "bg-emerald-50 text-emerald-700",
  "medium": "bg-amber-50 text-amber-700",
  "low": "bg-rose-50 text-rose-600",
};

// Rows are normalized active ingredients (lib/extractionFields normalizeActiveIngredients).
const COLUMNS = [
  ["ingredient_name", "Active ingredient", "min-w-[10rem]"],
  ["salt_form", "Salt form", "min-w-[7rem]"],
  ["strength_value", "Strength", "w-20"],
  ["strength_unit", "Unit", "w-24"],
  ["quantity_value", "Quantity", "w-20"],
  ["quantity_unit", "Unit", "w-20"],
];

// With onChange the cells are editable, rows can be removed and added; every edit is
// marked manually_edited so the review record shows it did not come from the source.
export default function ActiveIngredientsTable({ activeIngredients = [], onChange }) {
  const editable = typeof onChange === "function";
  const update = (id, key, value) => onChange(activeIngredients.map((ai) => (ai.id === id
    ? { ...ai, [key]: value, ...(key === "strength_value" ? { concentration_value: value } : {}),
        ...(key === "strength_unit" ? { concentration_unit: value } : {}), manually_edited: true }
    : ai)));
  const remove = (id) => onChange(activeIngredients.filter((ai) => ai.id !== id));
  const add = () => onChange([...activeIngredients, {
    id: newId(), ingredient_name: "", salt_form: "", strength_value: "", strength_unit: "", concentration_value: "",
    concentration_unit: "", quantity_value: "", quantity_unit: "", function: "additional active", confidence: "",
    included_in_local_formula: true, exclusion_reason: "", sort_order: activeIngredients.length, review_status: "pending",
    manually_edited: true, edited_by: "", edited_at: "", source_value: "", proposed_local_value: "",
    local_formula_draft_id: "", source_formula_id: "",
  }]);

  if (!activeIngredients.length && !editable) {
    return <p className="text-sm text-slate-400 italic">No active ingredients identified</p>;
  }

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50">
              {COLUMNS.map(([key, label]) => (
                <th key={key} className="text-left py-2 px-3 font-medium text-slate-700 whitespace-nowrap">{label}</th>
              ))}
              <th className="text-left py-2 px-3 font-medium text-slate-700">Function</th>
              <th className="text-left py-2 px-3 font-medium text-slate-700">Confidence</th>
              {editable && <th className="w-10" />}
            </tr>
          </thead>
          <tbody>
            {activeIngredients.map((ai) => {
              const func = (ai.function || ai.role || "active").toLowerCase();
              const fc = functionConfig[func] || { label: func, className: "bg-slate-50 text-slate-600 border-slate-200" };
              const conf = (ai.confidence || ai.source_confidence || "").toLowerCase();
              return (
                <tr key={ai.id} className="border-b border-slate-100 last:border-0 align-top">
                  {COLUMNS.map(([key, , width]) => (
                    <td key={key} className={cn("py-1.5 px-2", key === "ingredient_name" && "font-medium text-slate-900")}>
                      {editable ? (
                        <Input value={ai[key] || ""} onChange={(e) => update(ai.id, key, e.target.value)}
                          className={cn("h-9 text-sm", width)} aria-label={key.replace("_", " ")} />
                      ) : (
                        <span className="px-1 text-slate-700">{ai[key] || "—"}</span>
                      )}
                    </td>
                  ))}
                  <td className="py-2 px-3">
                    <span className={cn("inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border whitespace-nowrap", fc.className)}>
                      {fc.label}
                    </span>
                  </td>
                  <td className="py-2 px-3">
                    {ai.manually_edited ? (
                      <span className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-violet-50 text-violet-700">edited</span>
                    ) : conf && (
                      <span className={cn("inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize", confidenceConfig[conf] || "bg-slate-50 text-slate-500")}>
                        {conf}
                      </span>
                    )}
                  </td>
                  {editable && (
                    <td className="py-1.5 px-1">
                      <button type="button" onClick={() => remove(ai.id)} aria-label="Remove active ingredient"
                        className="p-2 text-slate-400 hover:text-rose-600"><Trash2 className="w-4 h-4" /></button>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {editable && (
        <Button type="button" variant="outline" size="sm" onClick={add}>
          <Plus className="w-3.5 h-3.5 mr-1" /> Add active ingredient
        </Button>
      )}
    </div>
  );
}
