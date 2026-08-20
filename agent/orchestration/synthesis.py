"""Deterministic evidence synthesis for read-only worker artifacts."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from itertools import combinations

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import Field

from agent.orchestration.models import (
    AgentArtifact,
    AgentEvidence,
    StrictModel,
    TaskStatus,
)
from agent.runtime.metrics import current_run_metrics


class SynthesisResult(StrictModel):
    summary: str = Field(min_length=1, max_length=4_000)
    supported_findings: list[AgentEvidence] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    proposed_changes: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)


def normalize_artifacts(artifacts: list[AgentArtifact]) -> list[AgentArtifact]:
    """Downgrade unsupported success claims before any model sees them."""
    normalized = []
    for artifact in artifacts:
        if artifact.status == TaskStatus.COMPLETED and not artifact.evidence:
            normalized.append(
                artifact.model_copy(
                    update={
                        "status": TaskStatus.INVALID,
                        "error": "Completed worker returned no evidence",
                    }
                )
            )
        else:
            normalized.append(artifact.model_copy(deep=True))
    return normalized


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value.strip()))


_NEGATIONS = {"no", "not", "never", "without", "cannot"}
_OPPOSITE_POLARITY = {
    "true": ("truth", True),
    "false": ("truth", False),
    "enabled": ("enabled", True),
    "disabled": ("enabled", False),
    "present": ("present", True),
    "absent": ("present", False),
    "passes": ("passes", True),
    "passed": ("passes", True),
    "fails": ("passes", False),
    "failed": ("passes", False),
    "success": ("success", True),
    "error": ("success", False),
    "current": ("current", True),
    "stale": ("current", False),
    "allows": ("allows", True),
    "denies": ("allows", False),
}
_IGNORED_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "it", "this", "that",
    "do", "does", "did",
}


def _stem(word: str) -> str:
    for suffix in ("ion", "ing", "ated", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) > len(suffix) + 3:
            word = word[: -len(suffix)]
            break
    if word.endswith("e") and len(word) > 4:
        word = word[:-1]
    return word


def _claim_assertions(claim: str) -> tuple[str, list[tuple[str, tuple[str, ...]]], list[tuple[str, tuple[str, ...]]]]:
    words = [word for word in re.findall(r"[a-z0-9_]+", claim.lower()) if word not in _IGNORED_WORDS]
    if not words:
        return "", [], []
    subject = _stem(words[0])
    positive: list[tuple[str, tuple[str, ...]]] = []
    negative: list[tuple[str, tuple[str, ...]]] = []
    index = 1
    while index < len(words):
        word = words[index]
        if word in _NEGATIONS:
            target_index = index + 1
            if target_index >= len(words):
                break
            if _stem(words[target_index]) == "perform" and target_index + 1 < len(words):
                target_index += 1
            target, _ = _OPPOSITE_POLARITY.get(
                words[target_index],
                (_stem(words[target_index]), True),
            )
            arguments = tuple(
                _stem(value)
                for value in words[target_index + 1 :]
                if value not in _NEGATIONS
            )
            negative.append((target, arguments))
            break
        concept, polarity = _OPPOSITE_POLARITY.get(word, (_stem(word), True))
        arguments = []
        for value in words[index + 1 :]:
            if value in _NEGATIONS:
                break
            arguments.append(_stem(value))
        (positive if polarity else negative).append((concept, tuple(arguments)))
        index += 1
    return subject, positive, negative


def _claims_conflict(first: str, second: str) -> bool:
    """Flag explicit opposites, without treating every different fact as a conflict."""
    left_subject, left_positive, left_negative = _claim_assertions(first)
    right_subject, right_positive, right_negative = _claim_assertions(second)
    if not left_subject or left_subject != right_subject:
        return False

    def oppose(
        positives: list[tuple[str, tuple[str, ...]]],
        negatives: list[tuple[str, tuple[str, ...]]],
    ) -> bool:
        return any(
            positive_concept == negative_concept
            and (
                not positive_arguments
                or not negative_arguments
                or positive_arguments == negative_arguments
            )
            for positive_concept, positive_arguments in positives
            for negative_concept, negative_arguments in negatives
        )

    return oppose(left_positive, right_negative) or oppose(right_positive, left_negative)


def _deterministic_result(artifacts: list[AgentArtifact]) -> SynthesisResult:
    evidence_by_locator: dict[tuple[str, str], dict[str, AgentEvidence]] = defaultdict(dict)
    proposals = []
    missing = []

    for artifact in artifacts:
        if artifact.status != TaskStatus.COMPLETED:
            missing.append(f"{artifact.task_id}: {artifact.status.value}")
            continue
        proposals.extend(artifact.proposed_changes)
        for evidence in artifact.evidence:
            key = (evidence.type.value, evidence.locator)
            evidence_by_locator[key][evidence.claim] = evidence

    supported = []
    conflicts = []
    for (_evidence_type, locator), claims in sorted(evidence_by_locator.items()):
        conflict_claims = {
            claim
            for first, second in combinations(sorted(claims), 2)
            if _claims_conflict(first, second)
            for claim in (first, second)
        }
        if conflict_claims:
            conflicts.append(f"{locator}: " + " <> ".join(sorted(conflict_claims)))
        supported.extend(
            evidence for claim, evidence in claims.items() if claim not in conflict_claims
        )

    summary = (
        f"Workers produced {len(supported)} supported finding(s), "
        f"{len(conflicts)} conflict(s), and {len(_unique(proposals))} change proposal(s). "
        "The main executor owns every write."
    )
    return SynthesisResult(
        summary=summary,
        supported_findings=supported,
        conflicts=conflicts,
        proposed_changes=_unique(proposals),
        missing_evidence=_unique(missing),
    )


async def _model_summary(model, deterministic: SynthesisResult) -> str:
    payload = deterministic.model_dump(mode="json")
    messages = [
        SystemMessage(
            content=(
                "Write a concise briefing for the main executor. Use only the "
                "provided verified evidence. Preserve conflicts and missing items. "
                "Change proposals are suggestions; never claim a write occurred."
            )
        ),
        HumanMessage(content=json.dumps(payload, ensure_ascii=False)[:20_000]),
    ]
    metrics = current_run_metrics()
    if metrics is None:
        response = await model.ainvoke(messages)
    else:
        async with metrics.span("synthesizer.model"):
            response = await model.ainvoke(messages)
        metrics.add_usage(
            "synthesizer",
            getattr(response, "usage_metadata", None) or {},
        )
    content = getattr(response, "content", "")
    text = content if isinstance(content, str) else str(content)
    return text.strip()[:4_000]


async def synthesize_artifacts(
    artifacts: list[AgentArtifact],
    *,
    model=None,
) -> SynthesisResult:
    """Normalize evidence, detect exact conflicts, then optionally brief once."""
    deterministic = _deterministic_result(normalize_artifacts(artifacts))
    if model is None:
        return deterministic
    try:
        summary = await _model_summary(model, deterministic)
    except Exception:
        return deterministic
    return deterministic.model_copy(update={"summary": summary or deterministic.summary})
