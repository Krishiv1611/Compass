from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from agent.skills.models import SkillDefinition, SubAgentState
from agent.llm import llm
from agent.graph.nodes import check_safety_node


class SubAgentFactory:
    """
    Factory that builds disposable LangGraph sub-graphs for skill execution.
    """

    def __init__(self, all_tools: list):
        self._all_tools_by_name = {t.name: t for t in all_tools}

    def build(self, skill: SkillDefinition, arguments: str):
        """
        Build an ephemeral sub-agent graph for a specific skill.
        Returns a CompiledGraph.
        """
        # 1. Resolve tools
        if skill.allowed_tools is not None:
            tools = [
                self._all_tools_by_name[n]
                for n in skill.allowed_tools
                if n in self._all_tools_by_name
            ]
        else:
            tools = list(self._all_tools_by_name.values())

        # 2. Build system prompt
        prompt = skill.system_prompt.replace("$ARGUMENTS", arguments)

        max_turns = skill.max_turns

        async def sub_executor(state: SubAgentState, config: RunnableConfig):
            configurable = config.get("configurable", {})
            sub_llm = llm(
                "executor",
                api_key=configurable.get("api_key"),
                provider=configurable.get("provider"),
                model=skill.model or configurable.get("model"),
            )
            sub_llm_with_tools = sub_llm.bind_tools(tools) if tools else sub_llm
            msgs = [SystemMessage(content=prompt)] + list(state["messages"])
            response = await sub_llm_with_tools.ainvoke(msgs)
            turn = state.get("turn_count", 0) + 1
            has_tools = (
                hasattr(response, "tool_calls")
                and bool(response.tool_calls)
                and bool(tools)
            )
            if has_tools and turn >= max_turns:
                return {
                    "messages": [
                        AIMessage(
                            content=(
                                "Sub-agent stopped at its maximum turn limit "
                                "before the requested tool call could be run."
                            )
                        )
                    ],
                    "turn_count": turn,
                    "is_done": True,
                    "pending_tool_calls": [],
                }
            return {
                "messages": [response],
                "turn_count": turn,
                "is_done": not has_tools or turn >= max_turns,
            }

        async def route(state: SubAgentState) -> str:
            if state.get("is_done", False):
                return END
            last = state["messages"][-1]
            if hasattr(last, "tool_calls") and last.tool_calls and tools:
                return "sub_safety"

        async def route_after_safety(state: SubAgentState) -> str:
            if state.get("approval_status") in ("denied", "skipped"):
                return "sub_executor"
            return "sub_tools"
            return END

        builder = StateGraph(SubAgentState)  # type: ignore
        builder.add_node("sub_executor", sub_executor)
        if tools:
            builder.add_node("sub_safety", check_safety_node)
            builder.add_node("sub_tools", ToolNode(tools))
            builder.add_conditional_edges("sub_safety", route_after_safety)
            builder.add_edge("sub_tools", "sub_executor")

        builder.add_edge(START, "sub_executor")
        builder.add_conditional_edges("sub_executor", route)

        return builder.compile()
