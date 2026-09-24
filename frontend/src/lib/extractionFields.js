import { newId } from "@/lib/utils";

/**
 * Enhanced structured extraction schema for compounding formula PDFs.
 * The server runs extraction with the same schema (backend/app/ai/schema.py).
 *
 * The schema uses detailed descriptions to guide the LLM to:
 * - Use visual/layout context (headings, tables, numbered lists, multi-page sections)
 * - Map source headings semantically to the correct fields
 * - Extract all mandatory Master Formula fields
 */
export const FORMULA_EXTRACTION_SCHEMA = {
  type: "object",
  properties: {
    formula_title: {
      type: "string",
      description: "The title or name of the formula as printed at the top of the document. This becomes the proposed local formula name."
    },
    source_formula_id: {
      type: "string",
      description: "Reference number or ID from the source, e.g. 'Formula #123', 'Document ID', or catalog number"
    },
    active_ingredient: {
      type: "string",
      description: "The primary active pharmaceutical ingredient (API). For multi-ingredient formulas, this is the main active. Also populate the active_ingredients array with ALL active ingredients."
    },
    active_ingredients: {
      type: "array",
      items: {
        type: "object",
        properties: {
          name: { type: "string", description: "Name of the active ingredient (without salt form)" },
          salt_form: { type: "string", description: "Salt form, e.g. 'Hydrochloride', 'Sodium', 'Mesylate'. Leave empty if none." },
          quantity: { type: "string", description: "Quantity of this ingredient used in the formula (amount weighed/measured during compounding), e.g. '200', '0.5'" },
          quantity_unit: { type: "string", description: "Unit for the quantity, e.g. 'mg', 'g', 'mL'" },
          concentration: { type: "string", description: "Concentration or strength of the ingredient in the final product, e.g. '10', '2'" },
          concentration_unit: { type: "string", description: "Unit for concentration, e.g. 'mg/mL', '%', 'mg/suppository'" },
          function: { type: "string", description: "Function/role: 'active' for primary active, 'additional active' for secondary actives" },
          source_confidence: { type: "string", description: "Confidence in this extraction: 'high', 'medium', or 'low'" }
        },
        required: ["name"]
      },
      description: "ALL active pharmaceutical ingredients in the formula. Identify from the formula title, composition table, ingredient function column, or strength/concentration columns. A formula may have multiple active ingredients (e.g. Cyclobenzaprine Hydrochloride + Lidocaine in suppositories). Include every active ingredient. For each, extract the quantity (amount used in compounding) and concentration (strength in final product) separately if both are available."
    },
    strength: {
      type: "string",
      description: "Strength or concentration of the active ingredient, e.g. '10 mg/mL', '2% w/w'"
    },
    dosage_form: {
      type: "string",
      description: "Dosage form, e.g. 'oral suspension', 'topical cream', 'capsule', 'oral solution'"
    },
    final_quantity: {
      type: "string",
      description: "Final quantity to be compounded, e.g. '200 mL', '100 g', '30 capsules'"
    },
    ingredients: {
      type: "array",
      items: {
        type: "object",
        properties: {
          ingredient_name: { type: "string", description: "Name of the ingredient" },
          quantity: { type: "string", description: "Quantity amount, e.g. '2', '0.5'" },
          unit: { type: "string", description: "Unit of measure, e.g. 'mg', 'mL', 'g'" },
          specification_or_grade: { type: "string", description: "Specification, grade, or quality, e.g. 'USP', 'NF', 'ACS'" },
          function: { type: "string", description: "Function/role, e.g. 'active', 'excipient', 'preservative', 'buffer', 'flavoring', 'suspending agent'" },
          notes: { type: "string", description: "Any additional notes about this ingredient" },
        },
        required: ["ingredient_name"],
      },
      description: "ALL ingredients listed in the formula composition table or section. Map from headings like 'Formula Composition', 'Ingredients', 'Formula', 'Master Formula'. Include every ingredient row from any table.",
    },
    preparation_method: {
      type: "array",
      items: { type: "string" },
      description: "Numbered step-by-step preparation instructions. Map from headings like 'Preparation Method', 'Method of Preparation', 'Procedure', 'Compounding Instructions'. Preserve the numbered order.",
    },
    equipment: {
      type: "array",
      items: { type: "string" },
      description: "Required equipment. Map from headings like 'Equipment', 'Required Equipment', 'Supplies'. Include each item listed.",
    },
    in_process_controls: {
      type: "array",
      items: {
        type: "object",
        properties: {
          control: { type: "string", description: "Name of the in-process control, e.g. 'Appearance', 'pH', 'Homogeneity'" },
          requirement: { type: "string", description: "Acceptance criteria or requirement" },
        },
      },
      description: "In-process controls. Map from headings like 'In-Process Controls', 'Quality Control', 'In-Process Testing'.",
    },
    packaging: {
      type: "object",
      properties: {
        container: { type: "string", description: "Container type, e.g. 'plastic bottle', 'amber glass vial'" },
        closure: { type: "string", description: "Closure type, e.g. 'child-resistant cap', 'screw cap'" },
        package_size: { type: "string", description: "Package size, e.g. '200 mL', '100 g'" },
        special_instructions: { type: "string", description: "Special packaging instructions" },
      },
      description: "Packaging requirements. Map from headings like 'Packaging', 'Container', 'Packaging Requirements'. Extract container, closure, package size, and special instructions as separate sub-fields.",
    },
    storage_conditions: {
      type: "object",
      properties: {
        temperature: { type: "string", description: "Storage temperature, e.g. 'Room temperature', 'Refrigerate 2-8C', 'Store below 25C'" },
        light_protection: { type: "string", description: "Light protection requirements, e.g. 'Protect from light', 'No special requirements'" },
        additional_instructions: { type: "string", description: "Additional storage instructions" },
      },
      description: "Storage conditions. Map from headings like 'Storage Conditions', 'Storage', 'Storage Requirements'. Extract temperature, light protection, and additional instructions as separate sub-fields.",
    },
    bud: {
      type: "object",
      properties: {
        approved_bud: { type: "string", description: "The Beyond-Use Date (BUD), e.g. '14 days', '30 days', '6 months'. This is the assigned or recommended BUD." },
        storage_condition: { type: "string", description: "Storage condition applicable to the BUD, e.g. 'Refrigerated', 'Room temperature'" },
        bud_source: { type: "string", description: "Source of the BUD assignment, e.g. 'USP <795>', 'Stability study', 'Manufacturer data'" },
        supporting_reference: { type: "string", description: "Supporting reference for the BUD, e.g. 'USP Compounding Monograph'" },
        pharmacist_rationale: { type: "string", description: "Pharmacist rationale for the BUD, if stated in the document" },
      },
      description: "Beyond-Use Date information. Map from headings like 'Beyond-Use Date', 'BUD', 'Beyond Use Date', 'Expiration Date'. Extract all available sub-fields.",
    },
    labelling_instructions: {
      type: "array",
      items: { type: "string" },
      description: "Labelling instructions. Map from headings like 'Labelling', 'Labeling Instructions', 'Label Information'. Include each instruction as a separate item.",
    },
    warnings: {
      type: "array",
      items: { type: "string" },
      description: "Warnings and precautions. Map from headings like 'Warnings', 'Precautions', 'Warnings and Precautions', 'Cautions'. If the document explicitly states no warnings (e.g. 'None' or 'None stated'), include that as a single item. If no warnings section exists, leave empty.",
    },
    references: {
      type: "array",
      items: { type: "string" },
      description: "All references cited in the source PDF. Map from headings like 'References', 'Citations', 'Bibliography'. Include each reference as a separate item.",
    },
  },
  required: ["formula_title", "active_ingredient"],
};

/**
 * Field definitions for the pharmacist review comparison.
 * type: "text" | "list" | "ingredients" | "packaging" | "storage" | "bud"
 * special: null | "bud"
 * preserveWording: true — don't simplify or combine conflicting instructions
 */
export const COMPARISON_FIELDS = [
  { key: "formula_title", label: "Formula title", draftKey: "proposed_formula_name", type: "text" },
  { key: "active_ingredient", label: "Active ingredient", draftKey: "active_ingredient", type: "text" },
  { key: "strength", label: "Strength", draftKey: "strength", type: "text" },
  { key: "dosage_form", label: "Dosage form", draftKey: "dosage_form", type: "text" },
  { key: "final_quantity", label: "Final quantity", draftKey: "final_quantity", type: "text" },
  { key: "ingredients", label: "Ingredients", draftKey: "ingredients", type: "ingredients" },
  { key: "preparation_method", label: "Preparation method", draftKey: "preparation_method", type: "list" },
  { key: "equipment", label: "Equipment", draftKey: "equipment", type: "list" },
  { key: "packaging", label: "Packaging", draftKey: "packaging", type: "packaging", preserveWording: true },
  { key: "storage_conditions", label: "Storage conditions", draftKey: "storage_conditions", type: "storage", preserveWording: true },
  { key: "bud", label: "BUD (Beyond Use Date)", draftKey: "bud", type: "bud", special: "bud" },
  { key: "labelling_instructions", label: "Labelling instructions", draftKey: "labelling_instructions", type: "list" },
  { key: "warnings", label: "Warnings", draftKey: "warnings", type: "list" },
  { key: "references", label: "References", draftKey: "references", type: "list" },
  { key: "source_formula_id", label: "Source formula ID", draftKey: null, type: "text" },
];

const SHORT_TEXT_FIELDS = new Set([
  "formula_title", "active_ingredient", "strength",
  "dosage_form", "final_quantity", "source_formula_id",
]);

export function isShortTextField(fieldKey) {
  return SHORT_TEXT_FIELDS.has(fieldKey);
}

/**
 * Formats a raw extraction value for display/draft text.
 * Handles structured objects (packaging, storage, bud) and arrays.
 * Returns null for empty values.
 */
export function formatSourceValue(value, type) {
  if (value === undefined || value === null) return null;

  if (type === "ingredients") {
    if (!Array.isArray(value) || value.length === 0) return null;
    return value
      .filter((v) => v && v.ingredient_name)
      .map((v) => {
        const parts = [v.ingredient_name];
        if (v.quantity) parts.push(`— ${v.quantity}`);
        if (v.unit) parts.push(v.unit);
        if (v.specification_or_grade) parts.push(`[${v.specification_or_grade}]`);
        const func = v.function || v.role;
        if (func) parts.push(`(${func})`);
        if (v.notes) parts.push(`— ${v.notes}`);
        return parts.join(" ");
      })
      .join("\n");
  }

  if (type === "list") {
    if (Array.isArray(value)) {
      if (value.length === 0) return null;
      return value.map((step, i) => `${i + 1}. ${step}`).join("\n");
    }
    const str = String(value).trim();
    return str || null;
  }

  if (type === "packaging") {
    if (typeof value === "object" && !Array.isArray(value)) {
      const parts = [];
      if (value.container) parts.push(`Container: ${value.container}`);
      if (value.closure) parts.push(`Closure: ${value.closure}`);
      if (value.package_size) parts.push(`Package size: ${value.package_size}`);
      if (value.special_instructions) parts.push(`Special instructions: ${value.special_instructions}`);
      return parts.length > 0 ? parts.join("\n") : null;
    }
    const str = String(value).trim();
    return str || null;
  }

  if (type === "storage") {
    if (typeof value === "object" && !Array.isArray(value)) {
      const parts = [];
      if (value.temperature) parts.push(`Temperature: ${value.temperature}`);
      if (value.light_protection) parts.push(`Light protection: ${value.light_protection}`);
      if (value.additional_instructions) parts.push(`Additional: ${value.additional_instructions}`);
      return parts.length > 0 ? parts.join("\n") : null;
    }
    const str = String(value).trim();
    return str || null;
  }

  if (type === "bud") {
    if (typeof value === "object" && !Array.isArray(value)) {
      const parts = [];
      if (value.approved_bud) parts.push(`BUD: ${value.approved_bud}`);
      if (value.storage_condition) parts.push(`Storage: ${value.storage_condition}`);
      if (value.bud_source) parts.push(`Source: ${value.bud_source}`);
      if (value.supporting_reference) parts.push(`Reference: ${value.supporting_reference}`);
      if (value.pharmacist_rationale) parts.push(`Rationale: ${value.pharmacist_rationale}`);
      return parts.length > 0 ? parts.join("\n") : null;
    }
    const str = String(value).trim();
    return str || null;
  }

  // Default: text
  const str = String(value).trim();
  return str || null;
}

/**
 * Checks if sources conflict for a given field.
 * Case-sensitive for preserveWording fields (exact wording matters).
 */
export function getFieldConflict(doneSources, field) {
  if (doneSources.length <= 1) return false;
  const values = doneSources
    .map((s) => formatSourceValue(s.data[field.key], field.type))
    .filter((v) => v !== null);
  if (values.length <= 1) return false;
  if (field.preserveWording) {
    const first = values[0].trim();
    return values.some((v) => v.trim() !== first);
  }
  const first = values[0].trim().toLowerCase();
  return values.some((v) => v.trim().toLowerCase() !== first);
}

/**
 * Computes confidence level for a field based on source agreement.
 * Returns: "high" | "medium" | "low" | "not found"
 * - high: all sources agree
 * - medium: only one source has a value
 * - low: sources conflict
 * - not found: no source has a value
 */
export function getFieldConfidence(doneSources, field) {
  if (doneSources.length === 0) return "not found";
  const values = doneSources
    .map((s) => formatSourceValue(s.data[field.key], field.type))
    .filter((v) => v !== null);
  if (values.length === 0) return "not found";
  if (doneSources.length === 1) return "high";
  if (values.length === 1) return "medium";
  return getFieldConflict(doneSources, field) ? "low" : "high";
}

/**
 * Computes the initial review state for all fields after extraction.
 *
 * Rules:
 * - All sources agree -> copy common value, resolved = true
 * - One source empty, other has value -> use available value, resolved = true
 * - Sources conflict -> leave blank, conflict = true, resolved = false
 *
 * BUD: never auto-select; if values differ, leave blank.
 * Storage/packaging: preserve exact wording; if differ, leave blank.
 */
export function computeInitialReviewState(doneSources) {
  const state = {};

  COMPARISON_FIELDS.forEach((field) => {
    if (!field.draftKey) return;

    const values = doneSources.map((s) => formatSourceValue(s.data[field.key], field.type));
    const nonEmpty = values.filter((v) => v !== null);

    if (nonEmpty.length === 0) {
      state[field.key] = { proposedValue: "", conflict: false, resolved: true, reviewMethod: "auto-agreed" };
      return;
    }

    if (doneSources.length <= 1 || nonEmpty.length <= 1) {
      state[field.key] = { proposedValue: nonEmpty[0], conflict: false, resolved: true, reviewMethod: "auto-agreed" };
      return;
    }

    const conflict = getFieldConflict(doneSources, field);
    if (!conflict) {
      state[field.key] = { proposedValue: nonEmpty[0], conflict: false, resolved: true, reviewMethod: "auto-agreed" };
    } else {
      state[field.key] = { proposedValue: "", conflict: true, resolved: false, reviewMethod: null };
    }
  });

  return state;
}

/**
 * Converts review state to draft form values (keyed by draftKey).
 */
export function reviewStateToDraftValues(reviewState) {
  const values = {};
  COMPARISON_FIELDS.forEach((field) => {
    if (!field.draftKey) return;
    const rs = reviewState[field.key];
    if (rs && rs.proposedValue) {
      values[field.draftKey] = rs.proposedValue;
    }
  });
  return values;
}

/**
 * Formats active_ingredients array into a readable text string.
 */
export function formatActiveIngredientsValue(value) {
  if (!Array.isArray(value) || value.length === 0) return null;
  return value
    .filter((v) => v && v.name)
    .map((v) => {
      const parts = [v.name];
      if (v.salt_form) parts.push(v.salt_form);
      if (v.strength) parts.push(`— ${v.strength}`);
      if (v.strength_unit) parts.push(v.strength_unit);
      if (v.function) parts.push(`(${v.function})`);
      return parts.join(" ");
    })
    .join("\n");
}

/**
 * Returns the primary active ingredient name from the active_ingredients array.
 */
export function getPrimaryActiveIngredient(activeIngredients) {
  if (!Array.isArray(activeIngredients) || activeIngredients.length === 0) return null;
  const primary = activeIngredients.find((ai) => ai.function === "active" || ai.function === "primary" || ai.role === "active");
  return primary ? primary.name : activeIngredients[0].name;
}

/**
 * Checks whether the requested search ingredient matches at least one
 * extracted active ingredient. Additional active ingredients are allowed.
 * Returns { match: boolean, matched: string[], unmatched: string[] }
 */
export function validateSearchMatch(requestedIngredient, activeIngredients) {
  if (!requestedIngredient || !Array.isArray(activeIngredients) || activeIngredients.length === 0) {
    return { match: true, matched: [], unmatched: [] };
  }
  const requested = requestedIngredient.toLowerCase().trim();
  const matched = [];
  const unmatched = [];
  activeIngredients.forEach((ai) => {
    const name = (ai.name || "").toLowerCase().trim();
    const saltForm = (ai.salt_form || "").toLowerCase().trim();
    const fullName = saltForm ? `${name} ${saltForm}` : name;
    if (name.includes(requested) || requested.includes(name) || fullName.includes(requested) || requested.includes(fullName)) {
      matched.push(ai.name);
    } else {
      unmatched.push(ai.name);
    }
  });
  return { match: matched.length > 0, matched, unmatched };
}

/**
 * Normalizes raw extracted active ingredients into the full structured format
 * with ids, defaults, and preserved source values for audit trail.
 */
export function normalizeActiveIngredients(rawAIs, sourceName = "", sourceFormulaId = "") {
  if (!Array.isArray(rawAIs)) return [];
  return rawAIs
    .filter((ai) => ai && (ai.name || ai.ingredient_name))
    .map((ai, i) => {
      const name = ai.ingredient_name || ai.name || "";
      const saltForm = ai.salt_form || "";
      const strengthValue = ai.strength_value || ai.concentration || ai.strength || "";
      const strengthUnit = ai.strength_unit || ai.concentration_unit || ai.strength_unit || "";
      const quantityValue = ai.quantity_value || ai.quantity || "";
      const quantityUnit = ai.quantity_unit || "";
      const func = ai.function || ai.role || "active";
      const confidence = ai.confidence || ai.source_confidence || "medium";

      const sourceValue = JSON.stringify({
        ingredient_name: name,
        salt_form: saltForm,
        strength_value: strengthValue,
        strength_unit: strengthUnit,
        quantity_value: quantityValue,
        quantity_unit: quantityUnit,
        function: func,
      });

      return {
        id: ai.id || newId(),
        local_formula_draft_id: "",
        source_formula_id: sourceFormulaId || ai.source_formula_id || "",
        ingredient_name: name,
        salt_form: saltForm,
        strength_value: strengthValue,
        strength_unit: strengthUnit,
        concentration_value: ai.concentration_value || strengthValue,
        concentration_unit: ai.concentration_unit || strengthUnit,
        quantity_value: quantityValue,
        quantity_unit: quantityUnit,
        function: func,
        confidence: confidence,
        included_in_local_formula: ai.included_in_local_formula !== false,
        exclusion_reason: ai.exclusion_reason || "",
        sort_order: ai.sort_order ?? i,
        review_status: ai.review_status || "pending",
        manually_edited: false,
        edited_by: "",
        edited_at: "",
        source_value: sourceValue,
        proposed_local_value: "",
      };
    });
}

/**
 * Generates the proposed local formula name from included active ingredients.
 * E.g. "Cyclobenzaprine Hydrochloride and Lidocaine Suppositories"
 */
export function generateFormulaName(activeIngredients, dosageForm) {
  const included = (activeIngredients || []).filter(
    (ai) => ai.included_in_local_formula !== false && (ai.ingredient_name || ai.name) && (ai.ingredient_name || ai.name).trim()
  );
  if (included.length === 0) return null;
  const names = included.map((ai) =>
    [ai.ingredient_name || ai.name, ai.salt_form].filter(Boolean).join(" ").trim()
  );
  let joined;
  if (names.length === 1) {
    joined = names[0];
  } else if (names.length === 2) {
    joined = `${names[0]} and ${names[1]}`;
  } else {
    joined = `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
  }
  return dosageForm ? `${joined} ${dosageForm}` : joined;
}

/**
 * Validates active ingredients for approval.
 * Returns an array of error messages (empty if valid).
 */
export function validateActiveIngredients(activeIngredients, compositionText, legacyActiveIngredient) {
  const errors = [];
  const list = activeIngredients || [];
  const included = list.filter((ai) => ai.included_in_local_formula !== false);
  const excluded = list.filter((ai) => ai.included_in_local_formula === false);
  const RECONCILIATION_MSG = "Active ingredient reconciliation failed. The source formula and the local draft do not contain the same active ingredient records. Pharmacist review is required.";

  if (included.length === 0) {
    errors.push("There are zero included active ingredients. " + RECONCILIATION_MSG);
  }

  included.forEach((ai) => {
    const name = ai.ingredient_name || ai.name;
    if (!ai.strength_value || !ai.strength_value.trim()) {
      errors.push(`Active ingredient "${name}" requires a strength value.`);
    }
    if (!ai.quantity_value || !ai.quantity_value.trim()) {
      errors.push(`Active ingredient "${name}" requires a quantity value.`);
    }
  });

  excluded.forEach((ai) => {
    const name = ai.ingredient_name || ai.name;
    if (!ai.exclusion_reason || !ai.exclusion_reason.trim()) {
      errors.push(`Excluded active ingredient "${name}" requires an exclusion reason.`);
    }
  });

  // Reconciliation: B (composition active rows) must equal D (included)
  if (compositionText && included.length > 0) {
    const compLines = compositionText
      .split("\n")
      .filter((l) => l.trim() && l.toLowerCase().includes("(active)"));
    if (compLines.length !== included.length) {
      errors.push(RECONCILIATION_MSG);
    }
  }

  // Check for collapsed strings in legacy field
  if (list.length > 1 && legacyActiveIngredient) {
    const lower = legacyActiveIngredient.toLowerCase();
    if (lower.includes(" and ") || lower.includes(",")) {
      errors.push("Multiple active ingredients were collapsed into one string. " + RECONCILIATION_MSG);
    }
  }

  return errors;
}

/**
 * Syncs included active ingredients into the composition (ingredients) text.
 * Preserves non-active-ingredient rows. Replaces existing active ingredient
 * rows with current data from the active_ingredients array.
 */
export function syncActiveIngredientsToComposition(activeIngredients, existingIngredientsText) {
  const list = activeIngredients || [];
  const included = list.filter(
    (ai) => ai.included_in_local_formula !== false && (ai.ingredient_name || ai.name) && (ai.ingredient_name || ai.name).trim()
  );
  const allAINames = list
    .filter((ai) => ai.ingredient_name || ai.name)
    .map((ai) => (ai.ingredient_name || ai.name).toLowerCase().trim());

  // Parse existing ingredients into lines
  const existingLines = (existingIngredientsText || "")
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);

  // Keep lines that are NOT active ingredients (matched by name)
  const nonAILines = existingLines.filter((line) => {
    const lowerLine = line.toLowerCase();
    return !allAINames.some((name) => name && lowerLine.includes(name));
  });

  // Build active ingredient lines in the composition format
  const aiLines = included.map((ai) => {
    const fullName = [ai.ingredient_name || ai.name, ai.salt_form].filter(Boolean).join(" ").trim();
    const qty = ai.quantity_value || ai.strength_value || "";
    const unit = ai.quantity_unit || ai.strength_unit || "";
    const parts = [fullName];
    if (qty) parts.push(`— ${qty}`);
    if (unit) parts.push(unit);
    parts.push("(active)");
    return parts.join(" ");
  });

  return [...aiLines, ...nonAILines].join("\n");
}

/**
 * Validates that all mandatory Master Formula fields are populated
 * in the proposed draft values.
 *
 * Returns { isValid: boolean, missing: string[] }
 */
export function validateDraftValues(values) {
  const missing = [];

  if (!values.proposed_formula_name?.trim()) missing.push("Proposed formula name");
  const hasActiveIngredient = values.active_ingredient?.trim() ||
    (Array.isArray(values.active_ingredients) && values.active_ingredients.length > 0);
  if (!hasActiveIngredient) missing.push("Active ingredient");
  if (!values.strength?.trim()) missing.push("Strength");
  if (!values.dosage_form?.trim()) missing.push("Dosage form");
  if (!values.final_quantity?.trim()) missing.push("Final quantity");
  if (!values.ingredients?.trim()) missing.push("At least one ingredient");
  if (!values.preparation_method?.trim()) missing.push("At least one preparation step");
  if (!values.packaging?.trim()) missing.push("Packaging or container");
  if (!values.storage_conditions?.trim()) missing.push("Storage condition");
  if (!values.bud?.trim()) missing.push("BUD");
  if (!values.labelling_instructions?.trim()) missing.push("At least one labelling instruction");
  if (!values.warnings?.trim()) missing.push("Warnings or 'None stated'");

  return { isValid: missing.length === 0, missing };
}

/**
 * Count non-empty fields in an extraction result for diagnostics.
 */
export function countExtractedFields(extraction) {
  if (!extraction || typeof extraction !== "object") return 0;
  let count = 0;

  const scalarKeys = [
    "formula_title", "source_formula_id", "active_ingredient", "strength",
    "dosage_form", "final_quantity",
  ];
  scalarKeys.forEach((k) => {
    if (extraction[k] && String(extraction[k]).trim()) count++;
  });

  // Object keys (packaging, storage_conditions, bud) — count if any sub-field is populated
  const objectKeys = ["packaging", "storage_conditions", "bud"];
  objectKeys.forEach((k) => {
    const v = extraction[k];
    if (!v) return;
    if (typeof v === "object" && !Array.isArray(v)) {
      if (Object.values(v).some((sub) => sub && String(sub).trim())) count++;
    } else if (String(v).trim()) {
      count++;
    }
  });

  const arrayKeys = [
    "active_ingredients", "ingredients", "preparation_method", "equipment", "in_process_controls",
    "labelling_instructions", "warnings", "references",
  ];
  arrayKeys.forEach((k) => {
    if (Array.isArray(extraction[k]) && extraction[k].length > 0) count++;
  });

  return count;
}