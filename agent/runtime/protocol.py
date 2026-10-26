"""Shared transport-neutral interrupt and resume protocol."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ResumeAction(str, Enum):
    APPROVE = "approve"
    ALWAYS = "always"
    DENY = "deny"
    SKIP = "skip"
    EXECUTE_PLAN = "execute_plan"
    REVISE_PLAN = "revise_plan"
    CANCEL = "cancel"
    ANSWER = "answer"


TOOL_RESUME_ACTIONS = ("approve", "always", "skip", "deny")
PLAN_RESUME_ACTIONS = ("execute_plan", "revise_plan", "cancel")
CLARIFICATION_RESUME_ACTIONS = ("answer",)


class InterruptKind(str, Enum):
    TOOL_APPROVAL = "tool_approval"
    PLAN_APPROVAL = "plan_approval"
    CLARIFICATION = "clarification"


class ResumePayload(BaseModel):
    action: ResumeAction
    feedback: str | None = None


class InterruptData(BaseModel):
    kind: InterruptKind
    prompt: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    plan: str | None = None
