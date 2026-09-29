"""English -> Hebrew translation of a draft's text fields, for pharmacist review.

The pharmacist sees each field side by side with the original and edits before
applying; nothing is saved by the translation itself.
"""

from typing import Any

# Draft fields that are prose. Names, strengths and quantities stay as entered.
TRANSLATABLE_FIELDS = (
    "proposed_formula_name", "dosage_form", "ingredients", "preparation_method", "equipment", "packaging",
    "storage_conditions", "bud", "labelling_instructions", "warnings", "local_adaptation_notes",
)

TRANSLATION_INSTRUCTIONS = """You translate pharmaceutical compounding master formulas from English to Hebrew \
for a licensed pharmacist in Israel. Produce an accurate, technical, professional Hebrew translation, in the \
register of Israeli pharmacy practice and compounding SOPs.

Keep exactly as written, in English/Latin characters, never transliterated or translated:
- names of raw materials, active ingredients, excipients, vehicles and bases (e.g. Baclofen, Ora-Plus, \
SyrSpend SF, Propylene Glycol, Methylparaben), including salt forms (Hydrochloride, Sodium);
- brand and trade names, suppliers, grades and pharmacopoeias (USP, NF, BP, Ph. Eur.), chapter numbers \
(USP <795>);
- all numbers, units and concentrations (10 mg/mL, 2% w/w, 2-8°C, qs, pH 4.5), formula and lot numbers.

Everything else is translated into Hebrew: instructions, equipment, container and closure types, storage \
and labelling text, warnings, dosage form words (oral suspension -> תרחיף פומי, topical cream -> קרם \
לשימוש חיצוני).

Rules:
- Translate faithfully; do not add, drop, summarise, explain or "improve" anything. No new warnings.
- Keep the structure: the same line breaks, numbering, bullets and order of steps.
- Use standard Hebrew pharmaceutical terminology. For a technical term whose Hebrew rendering is not \
unambiguous (e.g. levigate, triturate, geometric dilution, beyond-use date), write the Hebrew followed by \
the English term in parentheses, so the pharmacist can verify it. If there is no accepted Hebrew term, \
keep the English term.
- Text that is already Hebrew is returned unchanged.
- Return every field you were given, with the same key."""


def translation_schema(keys: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {k: {"type": "string"} for k in keys},
        "required": list(keys),
        "additionalProperties": False,
    }


def translation_request(fields: dict[str, str]) -> str:
    import json

    return "Translate the value of each field to Hebrew. Fields (JSON):\n" + json.dumps(fields, ensure_ascii=False)
