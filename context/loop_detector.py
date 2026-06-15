from langchain_core.messages import AIMessage
from graph.state import AgentState

def is_looping(state:AgentState,max_identical_calls: int=3)->bool:
    """
    Detects if the agent is calling the same tool with same tool with the same arguements repeatedly
    """
    messages=state[]