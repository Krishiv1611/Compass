import os
from tools.file_tools import read_file
from langgraph.graph import StateGraph, END, START
from graph.state import AgentState
from langgraph.prebuilt import ToolNode, tools_condition
from graph.nodes import call_model
from langgraph.checkpoint.postgres import PostgresSaver

DB_URI = os.environ["DB_URI"]  # raises KeyError if not set

workflow = StateGraph(AgentState)  # type: ignore

workflow.add_node("call_model", call_model)
workflow.add_node("tools", ToolNode([read_file]))

workflow.add_edge(START, "call_model")
workflow.add_conditional_edges("call_model", tools_condition)
workflow.add_edge("tools", "call_model")
with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    checkpointer.setup()


workflow = workflow.compile(checkpointer=checkpointer)
