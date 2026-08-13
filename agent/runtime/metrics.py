"""Request-scoped timing and usage aggregation for Compass runs."""

from contextvars import ContextVar, Token
from time import perf_counter
from typing import Any

from pydantic import BaseModel, Field


class SpanSnapshot(BaseModel):
    calls: int = 0
    errors: int = 0
    duration_ms: float = 0


class MetricsSnapshot(BaseModel):
    spans: dict[str, SpanSnapshot] = Field(default_factory=dict)
    calls_by_node: dict[str, int] = Field(default_factory=dict)
    usage_by_node: dict[str, dict[str, int]] = Field(default_factory=dict)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float | None = None
    tags: dict[str, str] = Field(default_factory=dict)


def _usage_value(usage: Any, *names: str) -> int:
    for name in names:
        value = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
        if isinstance(value, (int, float)):
            return int(value)
    return 0


class _Span:
    def __init__(self, metrics: "RunMetrics", name: str):
        self.metrics = metrics
        self.name = name
        self.started = 0.0

    def __enter__(self):
        self.started = perf_counter()
        return self

    def __exit__(self, exc_type, _exc, _traceback):
        self.metrics._finish_span(
            self.name,
            perf_counter() - self.started,
            failed=exc_type is not None,
        )
        return False

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, exc_type, exc, traceback):
        return self.__exit__(exc_type, exc, traceback)


class RunMetrics:
    """Collect safe aggregate metrics without prompts, tool args, or secrets."""

    _SAFE_TAGS = {"provider", "model", "mode", "execution_target"}

    def __init__(self):
        self._spans: dict[str, SpanSnapshot] = {}
        self._calls_by_node: dict[str, int] = {}
        self._usage_by_node: dict[str, dict[str, int]] = {}
        self._tags: dict[str, str] = {}

    def span(self, name: str) -> _Span:
        return _Span(self, name)

    def _finish_span(self, name: str, elapsed: float, *, failed: bool) -> None:
        value = self._spans.setdefault(name, SpanSnapshot())
        value.calls += 1
        value.errors += int(failed)
        value.duration_ms = round(value.duration_ms + elapsed * 1000, 3)

    def add_usage(self, node: str, usage_metadata: Any) -> None:
        input_tokens = _usage_value(usage_metadata, "input_tokens", "prompt_tokens")
        output_tokens = _usage_value(usage_metadata, "output_tokens", "completion_tokens")
        total_tokens = _usage_value(usage_metadata, "total_tokens") or input_tokens + output_tokens
        self._calls_by_node[node] = self._calls_by_node.get(node, 0) + 1
        bucket = self._usage_by_node.setdefault(
            node,
            {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        )
        bucket["input_tokens"] += input_tokens
        bucket["output_tokens"] += output_tokens
        bucket["total_tokens"] += total_tokens

    def add_tag(self, name: str, value: object) -> None:
        if name in self._SAFE_TAGS and isinstance(value, (str, int, float, bool)):
            self._tags[name] = str(value)

    def snapshot(self) -> MetricsSnapshot:
        total_input = sum(value["input_tokens"] for value in self._usage_by_node.values())
        total_output = sum(value["output_tokens"] for value in self._usage_by_node.values())
        total = sum(value["total_tokens"] for value in self._usage_by_node.values())
        estimated_cost = None
        model = self._tags.get("model", "").lower()
        pricing = {
            "openai/gpt-4o-mini": (0.15, 0.60),
            "openai/gpt-4o": (5.0, 15.0),
            "anthropic/claude-3.5-sonnet": (3.0, 15.0),
            "anthropic/claude-3-haiku": (0.25, 1.25),
            "google/gemini-1.5-pro": (3.5, 10.5),
            "google/gemini-1.5-flash": (0.075, 0.30),
        }
        rates = next((value for name, value in pricing.items() if name in model), None)
        if "free" in model:
            estimated_cost = 0.0
        elif rates:
            estimated_cost = round(
                total_input / 1_000_000 * rates[0]
                + total_output / 1_000_000 * rates[1],
                6,
            )
        return MetricsSnapshot(
            spans={name: value.model_copy(deep=True) for name, value in self._spans.items()},
            calls_by_node=dict(self._calls_by_node),
            usage_by_node={name: dict(value) for name, value in self._usage_by_node.items()},
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_tokens=total,
            estimated_cost_usd=estimated_cost,
            tags=dict(self._tags),
        )


_CURRENT_METRICS: ContextVar[RunMetrics | None] = ContextVar(
    "compass_run_metrics",
    default=None,
)


def current_run_metrics() -> RunMetrics | None:
    return _CURRENT_METRICS.get()


def begin_run_metrics(metrics: RunMetrics | None = None) -> tuple[RunMetrics, Token]:
    value = metrics or RunMetrics()
    return value, _CURRENT_METRICS.set(value)


def end_run_metrics(token: Token) -> None:
    _CURRENT_METRICS.reset(token)
