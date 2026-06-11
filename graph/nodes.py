"""
Compass Agent Nodes — LangGraph node functions.

Contains the call_model node that invokes the LLM with bound tools.
"""

from graph.state import AgentState
from tools.file_tools import read_file, write_to_file, edit_file
from tools.directory_tools import list_dir, find_files
from tools.search_tools import grep_search
from tools.web_tools import web_search
from tools.shell_tool import shell_execute
from tools.memory_tool import memory
from tools.todo_tool import todo
from model.get_llm import llm
from langchain_core.messages import SystemMessage


_model = llm()
_model_with_tools = _model.bind_tools([
    read_file, write_to_file, edit_file,   # file tools
    list_dir, find_files,                   # directory tools
    grep_search,                            # search tools
    web_search,                             # web tools
    shell_execute,                          # shell tool
    memory,                                 # memory tool
    todo,                                   # todo tool
])


def call_model(state: AgentState):
    """Invoke the LLM with the current message history and bound tools."""
    messages = state["messages"]

    if state.get("summary"):
        # Prepend the running summary as a system message for context
        summary_msg = SystemMessage(
            content=f"Conversation Summary before this turn:\n{state['summary']}"
        )
        messages = [summary_msg] + messages

    response = _model_with_tools.invoke(messages)
    return {
        "messages": [response],
        "turn_count": state.get("turn_count", 0) + 1,
    }


def summary_node(state: AgentState):
    """Summarize the conversation to compact context."""
    from langchain_core.messages import HumanMessage, RemoveMessage

    existing_summary = state.get("summary", "")

    if existing_summary:
        prompt = (
            f"Existing summary:\n{existing_summary}\n\n"
            "Extend the summary using the new conversation above."
        )
    else:
        prompt = "Summarise the conversation above."

    message_for_summary = state["messages"] + [
        HumanMessage(content=prompt)
    ]
    response = _model.invoke(message_for_summary)

    # Keep the last 2 messages, delete everything else to free context
    messages_to_delete = state["messages"][:-2]
    return {
        "summary": response.content,
        "messages": [RemoveMessage(id=m.id) for m in messages_to_delete if m.id is not None],
    }
