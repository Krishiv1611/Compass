from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
)

from langchain_core.runnables import RunnableConfig
from agent.graph.state import AgentState
from agent.skills.registry import SkillRegistry
from agent.skills.subagent_factory import SubAgentFactory


class SkillManagerAgent:
    """
    Always runs between planner and executor.
    - If a matching skill is found → spawn sub-agent, run it, return result
    - If no match → pass through (return state unchanged, executor handles it)
    """

    def __init__(self, factory: SubAgentFactory, registry: SkillRegistry):
        self._factory = factory
        self._registry = registry

    async def __call__(self, state: AgentState, config: RunnableConfig) -> dict:
        active_skill = state.get("active_skill")

        # ── No skill requested → pass through to executor ────────────
        if not active_skill:
            return {}  # empty update = state unchanged, executor runs next

        if config.get("configurable", {}).get("delegation_allowed") is False:
            return {
                "active_skill": None,
                "skill_result": {
                    "skill_name": active_skill.get("name", ""),
                    "status": "error",
                    "error": "Worker delegation is disabled.",
                },
                "messages": [
                    SystemMessage(
                        content="Worker delegation is disabled; continue without nesting."
                    )
                ],
                "is_done": False,
            }

        skill_name = active_skill.get("name", "")
        arguments = active_skill.get("arguments", "")

        # ── Look up skill in registry ────────────────────────────────
        skill = self._registry.get(skill_name)
        if not skill:
            error = f"Requested skill '{skill_name}' is not registered."
            return {
                "active_skill": None,
                "skill_result": {
                    "skill_name": skill_name,
                    "status": "error",
                    "error": error,
                },
                "messages": [
                    SystemMessage(
                        content=(
                            f"Skill request error: {error} "
                            "Continue with the main executor."
                        )
                    )
                ],
                "is_done": False,
            }

        # ── Build and run sub-agent ──────────────────────────────────
        sub_graph = self._factory.build(skill, arguments)

        initial_state = {
            "messages": [HumanMessage(content=arguments)],
            "turn_count": 0,
            "is_done": False,
            "mode": state.get("mode", "edit"),
            "approval_status": None,
            "approved_operations": state.get("approved_operations", []),
            "pending_tool_calls": [],
            "usage": {},
        }

        final_state = await sub_graph.ainvoke(initial_state, config=config)

        # ── Extract result ───────────────────────────────────────────
        result_messages = final_state.get("messages", [])
        final_response = ""
        tool_count = 0
        for msg in result_messages:
            if isinstance(msg, AIMessage) and msg.content:
                final_response = (
                    msg.content if isinstance(msg.content, str) else str(msg.content)
                )
            if isinstance(msg, ToolMessage):
                tool_count += 1

        skill_result = {
            "skill_name": skill.name,
            "output": final_response,
            "tool_calls_made": tool_count,
            "turns_used": final_state.get("turn_count", 0),
        }

        return {
            "active_skill": None,  # clear after execution
            "skill_result": skill_result,
            "messages": [AIMessage(content=final_response)],
        }
