from typing import Annotated, Sequence, TypedDict, List
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """Rappresenta lo stato dell'agente CESARE."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    bible_context: str
    override_active: bool
    experience_context: str
    last_tool_status: str # "success", "error", or None
    reflection_log: str