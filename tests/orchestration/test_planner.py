import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from agent.graph.nodes import planner_node
from agent.orchestration.models import AgentTask, ExecutionPlan
from agent.orchestration.planner import (
    PLANNING_PROMPT,
    create_execution_plan,
    ready_task_ids,
)
from agent.runtime.metrics import begin_run_metrics, end_run_metrics
from agent.runtime.turn_context import TurnContext


def task_payload(task_id: str, **overrides) -> dict:
    values = {
        "id": task_id,
        "title": f"Task {task_id}",
        "objective": f"Inspect {task_id}",
        "kind": "analysis",
        "depends_on": [],
        "allowed_tools": ["read_file"],
        "success_criteria": ["Return evidence"],
    }
    values.update(overrides)
    return values


class _StructuredInvoker:
    def __init__(self, payload):
        self.payload = payload

    async def ainvoke(self, _messages):
        return self.payload


class StructuredModel:
    def __init__(self, payload):
        self.payload = payload

    def with_structured_output(self, _schema):
        return _StructuredInvoker(self.payload)


class TextModel:
    def __init__(self, content: str):
        self.content = content

    async def ainvoke(self, _messages):
        return AIMessage(content=self.content)


class UnsupportedStructuredModel(TextModel):
    def with_structured_output(self, _schema):
        raise NotImplementedError("structured output unsupported")


class UsageStructuredModel:
    def __init__(self, payload):
        self.payload = payload

    def with_structured_output(self, schema, *, include_raw=False):
        self.include_raw = include_raw
        parsed = schema.model_validate(self.payload)
        return _StructuredInvoker(
            {
                "raw": AIMessage(
                    content="",
                    usage_metadata={
                        "input_tokens": 12,
                        "output_tokens": 5,
                        "total_tokens": 17,
                    },
                ),
                "parsed": parsed,
                "parsing_error": None,
            }
        )


class ExecutionPlannerTests(unittest.IsolatedAsyncioTestCase):
    def context(self):
        return SimpleNamespace(
            tools=[
                SimpleNamespace(name="read_file"),
                SimpleNamespace(name="grep_search"),
                SimpleNamespace(name="edit_file"),
            ],
            project_instructions="Prefer small modules.",
        )

    def test_prompt_states_worker_concurrency_bounds(self):
        self.assertIn("2 workers by default", PLANNING_PROMPT)
        self.assertIn("never more than 4", PLANNING_PROMPT)

    async def test_structured_plan_validates_dependencies_and_ready_tasks(self):
        payload = {
            "tasks": [
                task_payload("audit-backend"),
                task_payload("audit-web", allowed_tools=["grep_search"]),
                task_payload(
                    "synthesize",
                    kind="implementation_proposal",
                    depends_on=["audit-backend", "audit-web"],
                ),
            ]
        }

        plan = await create_execution_plan(
            "Audit backend and web, then synthesize findings.",
            self.context(),
            StructuredModel(payload),
        )

        self.assertEqual(
            ready_task_ids(plan),
            ["audit-backend", "audit-web"],
        )
        self.assertEqual(plan.tasks[2].depends_on, ["audit-backend", "audit-web"])

    async def test_malformed_output_uses_single_main_executor_fallback(self):
        objective = "Audit the project without losing the original request."

        plan = await create_execution_plan(
            objective,
            self.context(),
            TextModel("not valid json"),
        )

        self.assertEqual(len(plan.tasks), 1)
        self.assertEqual(plan.tasks[0].id, "main-executor")
        self.assertEqual(plan.tasks[0].kind.value, "analysis")
        self.assertEqual(plan.tasks[0].objective, objective)

    async def test_fallback_preserves_a_long_original_objective(self):
        objective = "Inspect carefully. " * 400

        plan = await create_execution_plan(
            objective,
            self.context(),
            TextModel("not valid json"),
        )

        self.assertEqual(plan.tasks[0].objective, objective.strip())

    async def test_unsupported_structured_output_parses_one_json_object(self):
        model = UnsupportedStructuredModel(
            'prefix {"tasks": [{"id": "audit", "title": "Audit", '
            '"objective": "Audit safely", "kind": "verification", '
            '"depends_on": [], "allowed_tools": ["read_file"], '
            '"success_criteria": ["Report evidence"]}]} suffix'
        )

        plan = await create_execution_plan("Audit safely", self.context(), model)

        self.assertEqual([task.id for task in plan.tasks], ["audit"])

    async def test_invalid_tool_plan_falls_back_without_raising(self):
        payload = {"tasks": [task_payload("unsafe", allowed_tools=["edit_file"])]}

        plan = await create_execution_plan(
            "Propose an edit safely.",
            self.context(),
            StructuredModel(payload),
        )

        self.assertEqual([task.id for task in plan.tasks], ["main-executor"])

    async def test_structured_call_is_included_in_run_metrics(self):
        payload = {"tasks": [task_payload("audit")]}
        model = UsageStructuredModel(payload)
        metrics, token = begin_run_metrics()
        try:
            await create_execution_plan(
                "Audit safely.",
                self.context(),
                model,
            )
            snapshot = metrics.snapshot()
        finally:
            end_run_metrics(token)

        self.assertTrue(model.include_raw)
        self.assertEqual(snapshot.calls_by_node, {"planner.structured": 1})
        self.assertEqual(snapshot.spans["planner.structured_model"].calls, 1)
        self.assertEqual(snapshot.total_input_tokens, 12)
        self.assertEqual(snapshot.total_output_tokens, 5)
        self.assertEqual(snapshot.total_tokens, 17)


class PlannerNodeIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def execution_plan(self) -> ExecutionPlan:
        return ExecutionPlan(
            tasks=[
                AgentTask(
                    id="audit-web",
                    title="Audit web",
                    objective="Inspect the web surface",
                    kind="analysis",
                    allowed_tools=["read_file"],
                    success_criteria=["Return file evidence"],
                )
            ]
        )

    async def test_planner_node_stores_and_renders_typed_tasks(self):
        context = TurnContext(
            user_query="Audit the web surface.",
            model_clients={"planner": TextModel("1. Inspect the web surface.")},
        )
        config = {"configurable": {"_turn_context": context}}
        structured_plan = self.execution_plan()

        with patch(
            "agent.graph.nodes.create_execution_plan",
            new=AsyncMock(return_value=structured_plan),
        ):
            update = await planner_node(
                {"messages": [HumanMessage(content=context.user_query)]},
                config,
            )

        self.assertTrue(update["orchestration_enabled"])
        self.assertEqual(update["execution_plan"]["tasks"][0]["id"], "audit-web")
        self.assertIn("Read-only worker task graph", update["plan"])
        self.assertEqual(update["worker_artifacts"], [])

    async def test_planner_node_includes_revision_feedback(self):
        context = TurnContext(
            user_query="",
            model_clients={"planner": TextModel("1. Revise the audit plan.")},
        )
        config = {"configurable": {"_turn_context": context}}
        create_plan = AsyncMock(return_value=self.execution_plan())
        state = {
            "messages": [
                HumanMessage(content="Audit the project."),
                AIMessage(content="User rejected plan with feedback: Split web and backend"),
            ]
        }

        with patch("agent.graph.nodes.create_execution_plan", new=create_plan):
            await planner_node(state, config)

        request = create_plan.await_args.args[0]
        self.assertIn("Audit the project.", request)
        self.assertIn("Planner feedback: Split web and backend", request)


if __name__ == "__main__":
    unittest.main()
