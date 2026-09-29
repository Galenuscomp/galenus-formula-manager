from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Text = Field(default="", max_length=50_000)
Short = Field(default="", max_length=500)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginIn(Strict):
    email: str = Field(max_length=320)
    password: str = Field(max_length=200)


# New passwords are checked by security.password_problems, which gives readable messages.
class PasswordChangeIn(Strict):
    current_password: str = Field(max_length=200)
    new_password: str = Field(max_length=200)


class PasswordLinkCheckIn(Strict):
    token: str = Field(min_length=20, max_length=100)


class PasswordLinkSetIn(Strict):
    token: str = Field(min_length=20, max_length=100)
    new_password: str = Field(max_length=200)


class AISettingsIn(Strict):
    # default: the server's provider from .env. none: no AI extraction.
    provider: Literal["default", "none", "openai", "anthropic"]
    model: str | None = Field(default=None, max_length=100)
    # Omit to keep the key already saved for the same provider.
    api_key: str | None = Field(default=None, max_length=500)


class UserCreateIn(Strict):
    email: str = Field(max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    full_name: str = Field(min_length=1, max_length=200)
    role: Literal["admin", "pharmacist", "technician"]
    licence_number: str | None = Field(default=None, max_length=64)
    # Omit to create the user with an invitation link where they choose their own.
    password: str | None = Field(default=None, max_length=200)


class UserUpdateIn(Strict):
    email: str | None = Field(default=None, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    role: Literal["admin", "pharmacist", "technician"] | None = None
    licence_number: str | None = Field(default=None, max_length=64)
    is_active: bool | None = None
    password: str | None = Field(default=None, max_length=200)


class CatalogRefIn(Strict):
    source: str = Field(max_length=40)
    formula_id: str = Field(default="", max_length=64)
    title: str = Field(max_length=1000)
    url: str = Field(default="", max_length=2000, pattern=r"^(https://.*)?$")


class RequestCreateIn(Strict):
    active_ingredient: str = Field(min_length=1, max_length=300)
    strength: str = Field(default="", max_length=200)
    dosage_form: str = Field(default="", max_length=200)
    final_quantity: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=5000)
    exact_match_only: bool = False
    sources: list[str] = Field(default_factory=list, max_length=20)
    # The catalog formula picked in the form, if any.
    catalog_ref: CatalogRefIn | None = None


class RetrySearchIn(Strict):
    source_name: str = Field(max_length=120)
    # Retry the download of this exact formula; empty: the request's catalog formula or a keyword search.
    formula_id: str = Field(default="", max_length=64)
    title: str = Field(default="", max_length=1000)
    url: str = Field(default="", max_length=2000)


class SourceAccountIn(Strict):
    username: str = Field(min_length=1, max_length=200)
    # Omit to keep the saved password.
    password: str | None = Field(default=None, max_length=200)


class SourceUpdateIn(Strict):
    selected: bool | None = None
    match_level: Literal["Exact", "Partial", "Alternative"] | None = None


class DraftCreateIn(Strict):
    source_document_ids: list[str] = Field(min_length=1, max_length=10)


class ActiveIngredient(Strict):
    local_formula_draft_id: str = Short
    source_formula_id: str = Short
    ingredient_name: str = Short
    salt_form: str = Short
    strength_value: str = Short
    strength_unit: str = Short
    concentration_value: str = Short
    concentration_unit: str = Short
    quantity_value: str = Short
    quantity_unit: str = Short
    function: str = Short
    confidence: str = Short
    included_in_local_formula: bool = True
    exclusion_reason: str = Field(default="", max_length=2000)
    sort_order: int = 0
    review_status: str = Short
    manually_edited: bool = False
    edited_by: str = Short
    edited_at: str = Short
    source_value: str = Field(default="", max_length=5000)
    proposed_local_value: str = Field(default="", max_length=5000)
    id: str = Short


class ReviewMeta(Strict):
    sources_used: list[str] = Field(default_factory=list, max_length=20)
    resolved_conflicts: int = 0
    blank_fields: int = 0
    reviewed_at: str = Short
    reviewed_by: str = Short
    pharmacist_note: str = Field(default="", max_length=5000)


class DraftContent(Strict):
    active_ingredient: str = Short
    proposed_formula_name: str = Short
    strength: str = Short
    dosage_form: str = Short
    final_quantity: str = Short
    ingredients: str = Text
    preparation_method: str = Text
    equipment: str = Text
    packaging: str = Text
    storage_conditions: str = Text
    bud: str = Text
    labelling_instructions: str = Text
    warnings: str = Text
    references: str = Text
    local_adaptation_notes: str = Text
    pharmacist_review_notes: str = Text
    revision_change_notes: str = Text
    active_ingredients: list[ActiveIngredient] = Field(default_factory=list, max_length=50)
    review: ReviewMeta | None = None


class DraftSaveIn(Strict):
    content: DraftContent
    row_version: int


class RowVersionIn(Strict):
    row_version: int


class DecisionIn(Strict):
    decision: Literal["approved", "rejected", "returned"]
    notes: str = Field(default="", max_length=5000)
    content_sha256: str = Field(min_length=64, max_length=64)
