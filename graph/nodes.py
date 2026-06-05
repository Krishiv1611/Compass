from graph.state import AgentState
from tools.file_tools import read_file,write_to_file,edit_file
from model.get_llm import llm
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode,tools_condition
def call_model(state:AgentState):
    model=llm()
    model = model.bind_tools([read_file,write_to_file,edit_file])
    message=state["messages"]
    response=model.invoke(message)
    return {"messages":[response],
    "turn_count":state.get("turn_count", 0)+1}
