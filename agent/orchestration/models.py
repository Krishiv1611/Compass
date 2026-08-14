"""Strict data contracts shared by orchestration planners and workers."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


TASK_ID_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,39}$"
MAX_TIMEOUT_SECONDS = 600
MAX_TOKEN_BUDGET = 50_000


class WorkerKind(str, Enum):
    ANALYSIS = "analysis"
    RESEARCH = "research"
    VERIFICATION = "verification"
    IMPLEMENTATION_PROPOSAL = "implementation_proposal"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    INVALID = "invalid"


class EvidenceType(str, Enum):
    FILE = "file"
    COMMAND = "command"
    URL = "url"
    TEST = "test"
    FINDING = "finding"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _non_empty_strings(values: list[str]) -> list[str]:
    cleaned = [value.strip() for value in values]
    if any(not value for value in cleaned):
        raise ValueError("values must be non-empty strings")
    return cleaned


class AgentTask(StrictModel):
    id: str = Field(pattern=TASK_ID_PATTERN)
    title: str = Field(min_length=1, max_length=120)
    objective: str = Field(min_length=1, max_length=4_000)
    kind: WorkerKind
    depends_on: list[str] = Field(default_factory=list, max_length=12)
    allowed_tools: list[str] = Field(min_length=1, max_length=12)
    success_criteria: list[str] = Field(min_length=1, max_length=5)
    timeout_seconds: int = Field(default=300, ge=1)
    token_budget: int = Field(default=20_000, ge=1)

    @field_validator("timeout_seconds", mode="before")
    @classmethod
    def clamp_timeout(cls, value):
        return min(int(value), MAX_TIMEOUT_SECONDS)

    @field_validator("token_budget", mode="before")
    @classmethod
    def clamp_token_budget(cls, value):
        return min(int(value), MAX_TOKEN_BUDGET)

    @field_validator("depends_on")
    @classmethod
    def validate_dependencies(cls, values: list[str]) -> list[str]:
        for value in values:
            if not re.fullmatch(TASK_ID_PATTERN, value):
                raise ValueError(f"invalid dependency ID: {value}")
        if len(set(values)) != len(values):
            raise ValueError("dependency IDs must be unique")
        return values

    @field_validator("allowed_tools", "success_criteria")
    @classmethod
    def validate_non_empty_lists(cls, values: list[str]) -> list[str]:
        cleaned = _non_empty_strings(values)
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("list values must be unique")
        return cleaned


class ExecutionPlan(StrictModel):
    tasks: list[AgentTask] = Field(min_length=1, max_length=12)


class AgentEvidence(StrictModel):
    type: EvidenceType
    locator: str = Field(min_length=1, max_length=1_000)
    claim: str = Field(min_length=1, max_length=500)


def _sanitize_error(value: str) -> str:
    text = " ".join(value.split())[:10_000]
    substitutions = (
        (
            r"(?i)([a-z][a-z0-9+.-]*://)[^/@\s]+(?::[^/@\s]*)?@",
            r"\1[REDACTED]@",
        ),
        (r"(?i)(authorization\s*:\s*(?:bearer|basic)\s+)\S+", r"\1[REDACTED]"),
        (
            r"(?i)((?:api[_-]?key|token|secret|password)\s*[:=]\s*)\S+",
            r"\1[REDACTED]",
        ),
        (
            r"\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{20,}|"
            r"github_pat_[A-Za-z0-9_]{20,}|glpat-[A-Za-z0-9_-]{12,}|"
            r"xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|"
            r"AIza[0-9A-Za-z_-]{20,})\b",
            "[REDACTED]",
        ),
    )
    for pattern, replacement in substitutions:
        text = re.sub(pattern, replacement, text)
    return text[:500]


class AgentArtifact(StrictModel):
    task_id: str = Field(pattern=TASK_ID_PATTERN)
    status: TaskStatus
    summary: str = Field(min_length=1, max_length=2_000)
    evidence: list[AgentEvidence] = Field(default_factory=list, max_length=50)
    files_considered: list[str] = Field(default_factory=list, max_length=2_000)
    proposed_changes: list[str] = Field(default_factory=list, max_length=100)
    checks: list[str] = Field(default_factory=list, max_length=100)
    usage: dict[str, int | float] = Field(default_factory=dict)
    started_at: datetime
    ended_at: datetime | None = None
    error: str | None = None

    @field_validator("files_considered", "proposed_changes", "checks")
    @classmethod
    def validate_text_lists(cls, values: list[str]) -> list[str]:
        return _non_empty_strings(values)

    @field_validator("error")
    @classmethod
    def sanitize_error(cls, value: str | None) -> str | None:
        return _sanitize_error(value) if value else None

    @field_validator("started_at", "ended_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("artifact timestamps must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_timestamps(self):
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at cannot be before started_at")
        return self
