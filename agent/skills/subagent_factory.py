from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from agent.skills.models import SkillDefinition, SubAgentState
from agent.model.get_llm import llm


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

        # 3. Get LLM
        # If model override exists, we could use a custom llm getter, but for now we'll
        # just use executor. The model override logic can be expanded in get_llm.py later if needed.
        # Currently get_llm.py only takes roles. We will use the 'executor' role as a base.
        sub_llm = llm("executor")
        sub_llm_with_tools = sub_llm.bind_tools(tools) if tools else sub_llm

        max_turns = skill.max_turns

        async def sub_executor(state: SubAgentState):
            msgs = [SystemMessage(content=prompt)] + list(state["messages"])
            response = await sub_llm_with_tools.ainvoke(msgs)
            turn = state.get("turn_count", 0) + 1
            has_tools = (
                hasattr(response, "tool_calls")
                and bool(response.tool_calls)
                and bool(tools)
            )
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
                return "sub_tools"
            return END

        builder = StateGraph(SubAgentState)  # type: ignore
        builder.add_node("sub_executor", sub_executor)
        if tools:
            builder.add_node("sub_tools", ToolNode(tools))
            builder.add_edge("sub_tools", "sub_executor")

        builder.add_edge(START, "sub_executor")
        builder.add_conditional_edges("sub_executor", route)

        return builder.compile()
