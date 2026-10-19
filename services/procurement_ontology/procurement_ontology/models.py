"""Validated contracts shared by extraction, governance and storage."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceRevision(DomainModel):
    id: str = Field(min_length=1)
    scope_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    simulated: bool
    submitted_by: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def verify_digest(self) -> SourceRevision:
        if hashlib.sha256(self.text.encode("utf-8")).hexdigest() != self.sha256.lower():
            raise ValueError("Source digest does not match saved text")
        if self.created_at.tzinfo is None:
            raise ValueError("Source timestamp must include timezone")
        self.sha256 = self.sha256.lower()
        return self


class SourceSpan(DomainModel):
    revision_id: str = Field(min_length=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1)

    @model_validator(mode="after")
    def verify_range(self) -> SourceSpan:
        if self.end <= self.start:
            raise ValueError("Source span end must follow start")
        return self

    def validate_against(self, source: SourceRevision) -> None:
        if self.revision_id != source.id:
            raise ValueError("Source revision does not match span")
        if self.end > len(source.text) or source.text[self.start:self.end] != self.quote:
            raise ValueError("Source span does not match original text")


class CategoryNode(DomainModel):
    id: str = Field(min_length=1)
    level: Literal[1, 2, 3]
    parent_id: str | None = None
    label: str = Field(min_length=1)

    @model_validator(mode="after")
    def verify_parent(self) -> CategoryNode:
        if (self.level == 1) != (self.parent_id is None):
            raise ValueError("Only level one nodes have no parent")
        if self.parent_id == self.id:
            raise ValueError("Category cannot be its own parent")
        return self


class Applicability(DomainModel):
    project_ref: str | None = None
    device_type: str | None = None
    stage: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None


class KnowledgeItem(DomainModel):
    id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = ""
    category_id: str = Field(min_length=1)
    scope: Applicability = Field(default_factory=Applicability)
    properties: dict[str, Any] = Field(default_factory=dict)
    source_spans: list[SourceSpan] = Field(default_factory=list)
    simulated: bool = False
    schema_version: str | None = None
    access_policy_ref: str | None = None


class KnowledgeRelation(DomainModel):
    id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    object_id: str = Field(min_length=1)
    source_spans: list[SourceSpan] = Field(default_factory=list)
    scope: Applicability = Field(default_factory=Applicability)


class Candidate(DomainModel):
    id: str = Field(min_length=1)
    item: KnowledgeItem | KnowledgeRelation
    status: Literal["PENDING_REVIEW", "ACCEPTED", "REJECTED", "MODEL_SUGGESTION"] = "PENDING_REVIEW"

    @model_validator(mode="after")
    def require_evidence(self) -> Candidate:
        if not self.item.source_spans:
            if self.status == "ACCEPTED":
                raise ValueError("Cannot accept a candidate without evidence")
            if self.status != "REJECTED":
                self.status = "MODEL_SUGGESTION"
        return self


class PublishedSnapshot(DomainModel):
    id: str = Field(min_length=1)
    kind: Literal["tree", "ontology"]
    payload: dict[str, Any]
    previous_id: str | None = None
    created_by: str
    created_at: datetime = Field(default_factory=utc_now)
