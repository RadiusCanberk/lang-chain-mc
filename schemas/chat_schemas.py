from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ChatRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    chat_id: str = Field(..., description="Chat ID")
    message: str = Field(..., description="Message")
    model_name: str = Field("openai/gpt-3.5-turbo", description="Name of OpenRouter Model")
    message_index: Optional[int] = Field(None, description="If provided, updates the message at this index instead of adding a new one")

class ToolCallLog(BaseModel):
    tool: str
    tool_input: str
    tool_output: str

class UIEvent(BaseModel):
    """
    UI-friendly logs for LLM chat UX (thinking/tooling/status).
    """
    type: str  # e.g. "thinking", "tool_call", "tool_result", "assistant", "status", "done"
    message: str
    tool: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    response: str
    tool_calls: List[ToolCallLog] = []
    user_id: str
    chat_id: str
    chat_pk: Optional[int] = None

    # New: UI log events (optional for backward compatibility)
    ui_events: List[UIEvent] = []

class HistoryMessage(BaseModel):
    role: str
    content: str
    name: Optional[str] = None
    type: Optional[str] = None
    index: Optional[int] = None

class UpdateMessageRequest(BaseModel):
    user_id: str
    chat_id: str
    message_index: int
    new_content: str

class DeleteMessageRequest(BaseModel):
    user_id: str
    chat_id: str
    message_index: int

class ChatHistoryResponse(BaseModel):
    user_id: str
    chat_id: str
    chat_pk: Optional[int] = None
    messages: List[HistoryMessage]