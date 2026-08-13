import asyncio
import unittest

from agent.runtime.metrics import RunMetrics


class RuntimeMetricsTests(unittest.TestCase):
    def test_usage_sums_all_nodes(self):
        metrics = RunMetrics()
        metrics.add_usage("planner", {"input_tokens": 10, "output_tokens": 4})
        metrics.add_usage("executor", {"input_tokens": 20, "output_tokens": 6})

        snapshot = metrics.snapshot()

        self.assertEqual(snapshot.total_input_tokens, 30)
        self.assertEqual(snapshot.total_output_tokens, 10)
        self.assertEqual(snapshot.calls_by_node, {"planner": 1, "executor": 1})

    def test_nested_spans_and_exceptions_are_recorded(self):
        metrics = RunMetrics()
        with metrics.span("turn"):
            with self.assertRaisesRegex(ValueError, "boom"):
                with metrics.span("executor.model"):
                    raise ValueError("boom")

        snapshot = metrics.snapshot()
        self.assertEqual(snapshot.spans["turn"].calls, 1)
        self.assertEqual(snapshot.spans["executor.model"].errors, 1)
        self.assertGreaterEqual(snapshot.spans["turn"].duration_ms, 0)

    def test_secret_values_are_not_serialized(self):
        metrics = RunMetrics()
        metrics.add_tag("provider", "openrouter")
        metrics.add_tag("api_key", "secret-value")

        serialized = metrics.snapshot().model_dump_json()

        self.assertIn("openrouter", serialized)
        self.assertNotIn("secret-value", serialized)
        self.assertNotIn("api_key", serialized)

    def test_known_model_cost_is_aggregated_and_unknown_cost_stays_unavailable(self):
        metrics = RunMetrics()
        metrics.add_tag("model", "openai/gpt-4o-mini")
        metrics.add_usage("executor", {"input_tokens": 1_000_000, "output_tokens": 1_000_000})
        self.assertEqual(metrics.snapshot().estimated_cost_usd, 0.75)

        unknown = RunMetrics()
        unknown.add_tag("model", "private/model")
        unknown.add_usage("executor", {"input_tokens": 10})
        self.assertIsNone(unknown.snapshot().estimated_cost_usd)


class AsyncRuntimeMetricsTests(unittest.IsolatedAsyncioTestCase):
    async def test_span_supports_async_context(self):
        metrics = RunMetrics()
        async with metrics.span("executor.model"):
            await asyncio.sleep(0)

        self.assertEqual(metrics.snapshot().spans["executor.model"].calls, 1)


if __name__ == "__main__":
    unittest.main()
