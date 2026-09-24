"""Extraction schema ported from the Base44 app (src/lib/extractionFields.js).

Bump SCHEMA_VERSION whenever the schema or prompt changes: cached extractions are
keyed by it, so a bump forces fresh extraction instead of reusing stale output.
"""

import copy
from typing import Any

SCHEMA_VERSION = "1"

_S = {"type": "string"}


def _str(description: str) -> dict[str, Any]:
    return {"type": "string", "description": description}


def _list(description: str) -> dict[str, Any]:
    return {"type": "array", "items": _S, "description": description}


FORMULA_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "formula_title": _str("Title of the formula as printed at the top of the document."),
        "source_formula_id": _str("Reference number or ID from the source, e.g. 'Formula #123' or catalog number."),
        "active_ingredient": _str("Primary active pharmaceutical ingredient (API)."),
        "active_ingredients": {
            "type": "array",
            "description": (
                "ALL active pharmaceutical ingredients, from the title, composition table, function column "
                "or strength columns. Extract quantity (amount used in compounding) and concentration "
                "(strength in final product) separately when both are available."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "name": _str("Ingredient name without salt form"),
                    "salt_form": _str("Salt form, e.g. 'Hydrochloride'. Empty if none."),
                    "quantity": _str("Amount weighed/measured, e.g. '200'"),
                    "quantity_unit": _str("Unit for quantity, e.g. 'mg', 'g', 'mL'"),
                    "concentration": _str("Strength in final product, e.g. '10'"),
                    "concentration_unit": _str("Unit, e.g. 'mg/mL', '%', 'mg/suppository'"),
                    "function": _str("'active' or 'additional active'"),
                    "source_confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
            },
        },
        "strength": _str("Strength or concentration, e.g. '10 mg/mL', '2% w/w'"),
        "dosage_form": _str("Dosage form, e.g. 'oral suspension', 'topical cream', 'capsule'"),
        "final_quantity": _str("Final quantity to be compounded, e.g. '200 mL', '30 capsules'"),
        "ingredients": {
            "type": "array",
            "description": "EVERY row of the formula composition/ingredients table.",
            "items": {
                "type": "object",
                "properties": {
                    "ingredient_name": _str("Name of the ingredient"),
                    "quantity": _str("Quantity amount"),
                    "unit": _str("Unit of measure"),
                    "specification_or_grade": _str("e.g. 'USP', 'NF'"),
                    "function": _str("e.g. 'active', 'excipient', 'preservative', 'vehicle'"),
                    "notes": _str("Additional notes"),
                },
            },
        },
        "preparation_method": _list("Numbered preparation steps, in order, wording preserved."),
        "equipment": _list("Required equipment items."),
        "in_process_controls": {
            "type": "array",
            "description": "In-process / quality controls.",
            "items": {
                "type": "object",
                "properties": {"control": _str("e.g. 'pH'"), "requirement": _str("Acceptance criteria")},
            },
        },
        "packaging": {
            "type": "object",
            "description": "Packaging requirements.",
            "properties": {
                "container": _str("Container type"),
                "closure": _str("Closure type"),
                "package_size": _str("Package size"),
                "special_instructions": _str("Special packaging instructions"),
            },
        },
        "storage_conditions": {
            "type": "object",
            "description": "Storage conditions.",
            "properties": {
                "temperature": _str("Storage temperature"),
                "light_protection": _str("Light protection requirements"),
                "additional_instructions": _str("Additional storage instructions"),
            },
        },
        "bud": {
            "type": "object",
            "description": "Beyond-Use Date information as stated in the document.",
            "properties": {
                "approved_bud": _str("The BUD, e.g. '30 days'"),
                "storage_condition": _str("Storage condition applicable to the BUD"),
                "bud_source": _str("Source of the BUD, e.g. 'USP <795>', 'stability study'"),
                "supporting_reference": _str("Supporting reference"),
                "pharmacist_rationale": _str("Rationale, if stated"),
            },
        },
        "labelling_instructions": _list("Labelling instructions, one per item."),
        "warnings": _list("Warnings/precautions. If the document says 'None', include that single item."),
        "references": _list("All references cited, one per item."),
    },
}

EXTRACTION_INSTRUCTIONS = """You extract compounding master-formula data from a source document for a \
pharmacist to review. Rules:
- Copy values exactly as written in the document; preserve units and wording.
- Never infer, calculate, convert or invent a value. If a field is not in the document, return an \
empty string or empty list.
- Use headings, tables, numbered lists and multi-page sections to map content to fields \
(e.g. 'Formula Composition' -> ingredients, 'Method of Preparation' -> preparation_method).
- Include every ingredient row and every preparation step, in document order.
- Rate each active ingredient's source_confidence by how clearly the document states it."""


def strict_schema(schema: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a copy where every object forbids extra keys and requires all keys.

    Both providers' structured-output modes need this shape. Absent values are
    represented by empty strings/lists as instructed in the prompt.
    """
    out = copy.deepcopy(schema or FORMULA_EXTRACTION_SCHEMA)

    def walk(node: dict[str, Any]) -> None:
        if node.get("type") == "object":
            props = node.setdefault("properties", {})
            node["additionalProperties"] = False
            node["required"] = list(props.keys())
            for child in props.values():
                walk(child)
        elif node.get("type") == "array" and isinstance(node.get("items"), dict):
            walk(node["items"])

    walk(out)
    return out
