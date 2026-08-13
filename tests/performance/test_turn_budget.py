import unittest
from collections import Counter

from tests.performance.fakes import CURRENT_SCENARIOS, TARGET_SCENARIOS, run_scenario


class TurnBudgetBaselineTests(unittest.TestCase):
    def test_current_call_counts_are_deterministic(self):
        for name, expected in CURRENT_SCENARIOS.items():
            with self.subTest(name=name):
                first = run_scenario(name)
                second = run_scenario(name)
                third = run_scenario(name)
                self.assertEqual(first, second)
                self.assertEqual(second, third)
                self.assertEqual(first, expected)

    @unittest.expectedFailure
    def test_executor_preparation_meets_once_per_turn_targets(self):
        for name, expected in TARGET_SCENARIOS.items():
            with self.subTest(name=name):
                actual = run_scenario(name)
                self.assertLessEqual(actual.memory_calls, expected.memory_calls)
                self.assertLessEqual(actual.mcp_calls, expected.mcp_calls)

    def test_fake_services_count_calls_without_sleeping(self):
        from tests.performance.fakes import services_for_counter

        counter = Counter()
        services = services_for_counter(counter)
        services.model("executor")
        services.memory()
        services.mcp()
        services.tool("read_file")

        self.assertEqual(
            counter,
            Counter(model_calls=1, memory_calls=1, mcp_calls=1, tool_calls=1),
        )


if __name__ == "__main__":
    unittest.main()
