import React from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Lock } from "lucide-react";

const dosageForms = [
  "Oral suspension",
  "Oral capsule",
  "Oral solution",
  "Topical cream",
  "Topical gel",
  "Topical ointment",
  "Suppository",
  "Ophthalmic solution",
  "Nasal solution",
];

const textareaFields = [
  { key: "ingredients", label: "Ingredients and quantities", rows: 4, placeholder: "List all ingredients with quantities..." },
  { key: "preparation_method", label: "Preparation method", rows: 6, placeholder: "Step-by-step preparation instructions..." },
  { key: "equipment", label: "Equipment", rows: 3, placeholder: "Required equipment..." },
  { key: "packaging", label: "Packaging", rows: 2, placeholder: "Packaging requirements..." },
  { key: "labelling_instructions", label: "Labelling instructions", rows: 3, placeholder: "Label text and instructions..." },
  { key: "warnings", label: "Warnings", rows: 3, placeholder: "Warnings and precautions..." },
  { key: "references", label: "References", rows: 3, placeholder: "References..." },
  { key: "local_adaptation_notes", label: "Local adaptation notes", rows: 3, placeholder: "Notes on adaptations made to the source formula..." },
  { key: "pharmacist_review_notes", label: "Pharmacist review notes", rows: 3, placeholder: "Review notes..." },
  { key: "revision_change_notes", label: "Revision change notes", rows: 2, placeholder: "What changed compared to the previous approved version...", revisionOnly: true },
];

export default function DraftEditForm({ form, onChange, locked = false, hasActiveIngredients = false, isRevision = false }) {
  const update = (key, value) => {
    if (locked) return;
    onChange((f) => ({ ...f, [key]: value }));
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wide">
          Draft details
        </h2>
        {locked && (
          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-400">
            <Lock className="w-3.5 h-3.5" />
            Fields locked — approved master formula
          </span>
        )}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {!hasActiveIngredients && (
          <div className="space-y-2">
            <Label htmlFor="active_ingredient">Active ingredient</Label>
            <Input
              id="active_ingredient"
              value={form.active_ingredient || ""}
              onChange={(e) => update("active_ingredient", e.target.value)}
              placeholder="e.g. Metronidazole"
              disabled={locked}
            />
          </div>
        )}
        <div className="space-y-2">
          <Label htmlFor="proposed_formula_name">Proposed local formula name</Label>
          <Input
            id="proposed_formula_name"
            value={form.proposed_formula_name || ""}
            onChange={(e) => update("proposed_formula_name", e.target.value)}
            placeholder="e.g. Metronidazole 50 mg/mL Topical Cream"
            disabled={locked}
          />
        </div>
        {!hasActiveIngredients && (
          <div className="space-y-2">
            <Label htmlFor="strength">Strength</Label>
            <Input
              id="strength"
              value={form.strength || ""}
              onChange={(e) => update("strength", e.target.value)}
              placeholder="e.g. 50 mg/mL"
              disabled={locked}
            />
          </div>
        )}
        <div className="space-y-2">
          <Label htmlFor="dosage_form">Dosage form</Label>
          <Input
            id="dosage_form"
            list="draft-dosage-forms"
            value={form.dosage_form || ""}
            onChange={(e) => update("dosage_form", e.target.value)}
            placeholder="Select or type"
            disabled={locked}
          />
          <datalist id="draft-dosage-forms">
            {dosageForms.map((f) => <option key={f} value={f} />)}
          </datalist>
        </div>
        <div className="space-y-2">
          <Label htmlFor="final_quantity">Final quantity</Label>
          <Input
            id="final_quantity"
            value={form.final_quantity || ""}
            onChange={(e) => update("final_quantity", e.target.value)}
            placeholder="e.g. 200 mL"
            disabled={locked}
          />
        </div>
        <div className="space-y-2 md:col-span-2">
          <Label htmlFor="storage_conditions">Storage conditions</Label>
          <Textarea
            id="storage_conditions"
            value={form.storage_conditions || ""}
            onChange={(e) => update("storage_conditions", e.target.value)}
            rows={2}
            placeholder="e.g. Refrigerate, 2-8°C"
            disabled={locked}
          />
        </div>
        <div className="space-y-2 md:col-span-2">
          <Label htmlFor="bud">BUD</Label>
          <Textarea
            id="bud"
            value={form.bud || ""}
            onChange={(e) => update("bud", e.target.value)}
            rows={2}
            placeholder="e.g. 30 days"
            disabled={locked}
          />
        </div>
        {textareaFields.filter((f) => !f.revisionOnly || isRevision).map(({ key, label, rows, placeholder }) => (
          <div key={key} className="space-y-2 md:col-span-2">
            <Label htmlFor={key}>{label}</Label>
            <Textarea
              id={key}
              value={form[key] || ""}
              onChange={(e) => update(key, e.target.value)}
              rows={rows}
              placeholder={placeholder}
              disabled={locked}
            />
          </div>
        ))}
      </div>
    </div>
  );
}