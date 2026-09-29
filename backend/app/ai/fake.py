"""Deterministic extractor for tests and demos. Never used unless AI_PROVIDER=fake."""

from app.ai.base import ExtractionResult


class FakeExtractor:
    provider = "fake"
    model = "fake-extractor"

    def verify(self) -> None:
        pass

    def extract(self, pdf: bytes, filename: str) -> ExtractionResult:
        return ExtractionResult(
            model=self.model,
            output={
                "formula_title": "Fictional Example Oral Suspension 10 mg/mL",
                "source_formula_id": "DEMO-001",
                "active_ingredient": "Examplamide",
                "active_ingredients": [
                    {
                        "name": "Examplamide",
                        "salt_form": "Hydrochloride",
                        "quantity": "2",
                        "quantity_unit": "g",
                        "concentration": "10",
                        "concentration_unit": "mg/mL",
                        "function": "active",
                        "source_confidence": "high",
                    }
                ],
                "strength": "10 mg/mL",
                "dosage_form": "oral suspension",
                "final_quantity": "200 mL",
                "ingredients": [
                    {"ingredient_name": "Examplamide Hydrochloride", "quantity": "2", "unit": "g",
                     "specification_or_grade": "USP", "function": "active", "notes": ""},
                    {"ingredient_name": "Suspension vehicle", "quantity": "qs 200", "unit": "mL",
                     "specification_or_grade": "", "function": "vehicle", "notes": ""},
                ],
                "preparation_method": ["Weigh the powder.", "Levigate with vehicle.", "Bring to volume."],
                "equipment": ["Balance", "Mortar and pestle"],
                "in_process_controls": [],
                "packaging": {"container": "Amber bottle", "closure": "Child-resistant cap",
                              "package_size": "200 mL", "special_instructions": ""},
                "storage_conditions": {"temperature": "Refrigerate", "light_protection": "Protect from light",
                                       "additional_instructions": ""},
                "bud": {"approved_bud": "14 days", "storage_condition": "Refrigerated", "bud_source": "",
                        "supporting_reference": "", "pharmacist_rationale": ""},
                "labelling_instructions": ["Shake well"],
                "warnings": ["None stated"],
                "references": ["Fictional reference for demonstration only"],
            },
        )
