"""Database models.

Design notes
- Request status is *derived* from jobs/drafts (see services.request_status) so it
  can never drift out of sync with the records it summarises.
- Decisions (approve/reject/return) are append-only rows that snapshot who decided,
  their licence number from the server-side user profile, and a hash of the exact
  content that was decided on. Approved drafts are never edited; a change creates
  a new draft version linked to its predecessor.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, UTCDateTime, utcnow


def new_id() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    # admin: manages users. pharmacist: may approve. technician: prepares drafts.
    role: Mapped[str] = mapped_column(String(20))
    licence_number: Mapped[str | None] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # How many pharmacies (branches) this pharmacist may set up; decided by an admin.
    max_pharmacies: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class Pharmacy(TimestampMixin, Base):
    """A pharmacy (branch) of a pharmacist. The approving pharmacist picks one of theirs, and
    its name, address and logo head the approved master formula PDF."""

    __tablename__ = "pharmacies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(500), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    logo_sha256: Mapped[str | None] = mapped_column(String(64))
    logo_type: Mapped[str | None] = mapped_column(String(10))  # png | jpeg


class UserAISettings(Base):
    """A user's own AI extraction provider. No row means: use the server default
    from .env. The API key is encrypted (app.crypto) and never sent back to the
    browser; only its last four characters are kept in clear for display."""

    __tablename__ = "user_ai_settings"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    provider: Mapped[str] = mapped_column(String(20))  # none | openai | anthropic
    model: Mapped[str | None] = mapped_column(String(100))
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    key_last4: Mapped[str | None] = mapped_column(String(4))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class SourceAccount(Base):
    """A user's own login to a formula source (CompoundingToday, MEDISCA). Downloads run
    with the login of the user who asked for them. Both fields are encrypted
    (app.crypto); the password is never sent back to the browser."""

    __tablename__ = "source_accounts"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    source: Mapped[str] = mapped_column(String(40), primary_key=True)
    username_encrypted: Mapped[str] = mapped_column(Text)
    password_encrypted: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    # Result of the last "Test login", shown next to the account.
    checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    check_ok: Mapped[bool | None] = mapped_column(Boolean)
    check_message: Mapped[str | None] = mapped_column(String(500))


class AuthSession(TimestampMixin, Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    user: Mapped[User] = relationship(lazy="joined")


class PasswordToken(TimestampMixin, Base):
    """One-time link for choosing a password: an invitation for a new user or a
    reset issued by an admin. Only the token's digest is stored."""

    __tablename__ = "password_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    purpose: Mapped[str] = mapped_column(String(10))  # invite | reset
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    user: Mapped[User] = relationship(lazy="joined", foreign_keys=[user_id])


class SearchRequest(TimestampMixin, Base):
    __tablename__ = "search_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(32), unique=True)
    active_ingredient: Mapped[str] = mapped_column(String(300), index=True)
    strength: Mapped[str] = mapped_column(String(200), default="")
    dosage_form: Mapped[str] = mapped_column(String(200), default="")
    final_quantity: Mapped[str] = mapped_column(String(200), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    exact_match_only: Mapped[bool] = mapped_column(Boolean, default=False)
    sources: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Copy of the catalog formula the request was started from: {source, formula_id, title, url}.
    catalog_ref: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    # Cached summary refreshed by services.refresh_request_status in the same
    # transaction as every change that affects it; used for fast list filtering.
    status: Mapped[str] = mapped_column(String(40), default="New", index=True)

    jobs: Mapped[list["Job"]] = relationship(back_populates="request", order_by="Job.created_at")
    documents: Mapped[list["SourceDocument"]] = relationship(
        back_populates="request", order_by="SourceDocument.created_at"
    )
    drafts: Mapped[list["Draft"]] = relationship(back_populates="request", order_by="Draft.created_at")


class SourceDocument(TimestampMixin, Base):
    __tablename__ = "source_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    request_id: Mapped[str] = mapped_column(ForeignKey("search_requests.id"), index=True)
    source_name: Mapped[str] = mapped_column(String(120))
    source_formula_id: Mapped[str] = mapped_column(String(200), default="")
    title: Mapped[str] = mapped_column(String(500), default="")
    source_url: Mapped[str] = mapped_column(String(2000), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    match_level: Mapped[str | None] = mapped_column(String(20))
    origin: Mapped[str] = mapped_column(String(20))  # automated | upload
    file_name: Mapped[str | None] = mapped_column(String(300))
    file_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    file_size: Mapped[int | None] = mapped_column(Integer)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))

    request: Mapped[SearchRequest] = relationship(back_populates="documents")


class Job(TimestampMixin, Base):
    """Background work item. Claimed with a conditional UPDATE and a lease so a
    crashed worker never leaves a job 'running' forever."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(20))  # search | extract
    request_id: Mapped[str] = mapped_column(ForeignKey("search_requests.id"), index=True)
    source_name: Mapped[str | None] = mapped_column(String(120))
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"))
    # Extraction jobs run with this user's AI settings (server default when unset).
    requested_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    # Search jobs: the exact formula to download, {formula_id, title, url}; none = keyword search.
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # Queued | Running | Completed | No results | Failed | Cooldown | Cancelled
    status: Mapped[str] = mapped_column(String(20), default="Queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    error: Mapped[str | None] = mapped_column(Text)
    run_after: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    lease_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    request: Mapped[SearchRequest] = relationship(back_populates="jobs")


class Extraction(TimestampMixin, Base):
    """AI extraction result for one source file. Cached by file hash + provider +
    model + schema version, so the same PDF is never paid for twice."""

    __tablename__ = "extractions"
    __table_args__ = (
        UniqueConstraint("file_sha256", "provider", "model", "schema_version", name="uq_extraction_cache"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    file_sha256: Mapped[str] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(100))
    schema_version: Mapped[str] = mapped_column(String(20))
    output: Mapped[dict[str, Any]] = mapped_column(JSON)
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class Draft(TimestampMixin, Base):
    __tablename__ = "drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(40), unique=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("search_requests.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    predecessor_id: Mapped[str | None] = mapped_column(ForeignKey("drafts.id"))
    # Draft created | Pending pharmacist approval | Approved | Rejected | Requires correction
    status: Mapped[str] = mapped_column(String(40), default="Draft created", index=True)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_document_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    submitted_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    # Optimistic concurrency: every save must name the version it edited.
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    request: Mapped[SearchRequest] = relationship(back_populates="drafts")
    decisions: Mapped[list["Decision"]] = relationship(order_by="Decision.created_at")


class Decision(TimestampMixin, Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    draft_id: Mapped[str] = mapped_column(ForeignKey("drafts.id"), index=True)
    decision: Mapped[str] = mapped_column(String(20))  # approved | rejected | returned
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    actor_name: Mapped[str] = mapped_column(String(200))
    actor_licence: Mapped[str | None] = mapped_column(String(64))
    preparer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    preparer_name: Mapped[str | None] = mapped_column(String(200))
    preparer_licence: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str] = mapped_column(Text, default="")
    content_sha256: Mapped[str] = mapped_column(String(64))
    pdf_sha256: Mapped[str | None] = mapped_column(String(64))
    pdf_file: Mapped[str | None] = mapped_column(String(300))
    # Copy of the approving pharmacist's pharmacy at approval time:
    # {id, name, address, phone, logo_sha256, logo_type}. Later edits do not change it.
    pharmacy: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class CatalogEntry(Base):
    """One formula listed in a source's catalog (app.catalog). Re-importing a
    source replaces its rows; requests keep a copy of the entry they used."""

    __tablename__ = "catalog_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(40), index=True)
    source_formula_id: Mapped[str] = mapped_column(String(64), default="")
    title: Mapped[str] = mapped_column(String(1000))
    route: Mapped[str] = mapped_column(String(100), default="")
    base: Mapped[str] = mapped_column(String(500), default="")
    url: Mapped[str] = mapped_column(String(2000), default="")
    # Parsed from the title to prefill a new request.
    active_ingredient: Mapped[str] = mapped_column(String(1000), default="")
    strength: Mapped[str] = mapped_column(String(500), default="")
    dosage_form: Mapped[str] = mapped_column(String(200), default="")
    final_quantity: Mapped[str] = mapped_column(String(200), default="")
    search_text: Mapped[str] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
