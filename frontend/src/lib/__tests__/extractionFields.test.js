import { describe, expect, it } from "vitest";
import {
  computeInitialReviewState,
  normalizeActiveIngredients,
  reviewStateToDraftValues,
  validateDraftValues,
} from "@/lib/extractionFields";

describe("normalizeActiveIngredients", () => {
  it("gives every ingredient a stable id and the canonical field names", () => {
    const [ai] = normalizeActiveIngredients([{ name: "Minoxidil", concentration: "5", concentration_unit: "%", quantity: "1.5", quantity_unit: "g" }]);
    expect(ai.id).toBeTruthy();
    expect(ai.ingredient_name).toBe("Minoxidil");
    expect(ai.strength_value).toBe("5");
    expect(ai.quantity_value).toBe("1.5");
    expect(ai.included_in_local_formula).toBe(true);
  });

  it("keeps an existing id", () => {
    expect(normalizeActiveIngredients([{ id: "keep", name: "X" }])[0].id).toBe("keep");
  });

  it("round-trips already-normalized rows, keeping the pharmacist's edits and their mark", () => {
    const [first] = normalizeActiveIngredients([{ name: "Aspirin", concentration: "81", concentration_unit: "mg/mL" }]);
    const edited = { ...first, strength_value: "20", manually_edited: true };
    const [again] = normalizeActiveIngredients([edited]);
    expect(again.ingredient_name).toBe("Aspirin");
    expect(again.strength_value).toBe("20");
    expect(again.strength_unit).toBe("mg/mL");
    expect(again.manually_edited).toBe(true);
    expect(again.id).toBe(first.id);
  });
});

describe("review state", () => {
  it("flags conflicting sources and never picks a value silently", () => {
    const sources = [
      { sourceName: "A", formulaId: "a", data: { bud: { approved_bud: "14 days" }, dosage_form: "cream" } },
      { sourceName: "B", formulaId: "b", data: { bud: { approved_bud: "30 days" }, dosage_form: "cream" } },
    ];
    const state = computeInitialReviewState(sources);
    expect(state.bud.conflict).toBe(true);
    expect(state.dosage_form.conflict).toBeFalsy();
    const values = reviewStateToDraftValues(state);
    expect(values.dosage_form).toBe("cream");
  });

  it("reports missing mandatory fields", () => {
    const { isValid, missing } = validateDraftValues({ proposed_formula_name: "X" });
    expect(isValid).toBe(false);
    expect(missing).toContain("BUD");
  });
});
