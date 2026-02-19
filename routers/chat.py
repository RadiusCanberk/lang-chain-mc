from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langsmith import traceable
from schemas.chat_schemas import (
    ChatRequest,
    ChatResponse,
    ToolCallLog,
    ChatHistoryResponse,
    HistoryMessage,
    UIEvent,
    UpdateMessageRequest,
    DeleteMessageRequest,
)
from database.history import get_session_history, clear_history, get_chat_pk, PersistentChatMessageHistory
from agents.agent import get_agent_executor
import logging
import json

# Setup logging for local debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

REASONING_INSTRUCTION = (
    "Before answering, call the tool `reasoning_tool` with a SHORT, user-visible plan/reasoning summary "
    "(2-6 bullet points). Do NOT reveal hidden chain-of-thought; keep it high level."
)


@router.get("/history", response_model=ChatHistoryResponse)
async def get_history(user_id: str, chat_id: str):
    """
    Returns persisted chat history for (user_id, chat_id).
    UI uses this to "continue an existing chat" and show visible history.
    """
    try:
        history = get_session_history(user_id, chat_id)
        chat_pk = get_chat_pk(user_id, chat_id)

        out: list[HistoryMessage] = []
        for i, msg in enumerate(history.messages):
            if isinstance(msg, HumanMessage):
                out.append(HistoryMessage(role="user", content=str(msg.content), type="human", index=i))
            elif isinstance(msg, AIMessage):
                out.append(HistoryMessage(role="assistant", content=str(msg.content), type="ai", index=i))
            elif isinstance(msg, ToolMessage):
                out.append(
                    HistoryMessage(
                        role="tool",
                        content=str(msg.content),
                        name=getattr(msg, "name", None),
                        type="tool",
                        index=i,
                    )
                )
            else:
                out.append(
                    HistoryMessage(
                        role="system",
                        content=str(getattr(msg, "content", msg)),
                        type=msg.__class__.__name__,
                        index=i,
                    )
                )

        return ChatHistoryResponse(
            user_id=user_id,
            chat_id=chat_id,
            chat_pk=chat_pk,
            messages=out,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/history/message")
async def update_message_endpoint(request: UpdateMessageRequest):
    try:
        history = get_session_history(request.user_id, request.chat_id)
        if isinstance(history, PersistentChatMessageHistory):
            history.update_message(request.message_index, request.new_content)
            return {"status": "success"}
        else:
            raise HTTPException(status_code=400, detail="History is not persistent")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history/message")
async def delete_message_endpoint(user_id: str, chat_id: str, message_index: int):
    try:
        history = get_session_history(user_id, chat_id)
        if isinstance(history, PersistentChatMessageHistory):
            history.delete_message_after(message_index)
            return {"status": "success"}
        else:
            raise HTTPException(status_code=400, detail="History is not persistent")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat", response_model=ChatResponse)
@traceable(
    name="chat_endpoint",
    tags=["chat", "agent", "lang-chain-mc"],
    metadata={"endpoint": "/agent/chat"}
)
async def chat_endpoint(request: ChatRequest):
    """
    Agent Chat endpoint with LangSmith tracing.
    """
    try:
        history = get_session_history(request.user_id, request.chat_id)
        
        if request.message_index is not None:
            if isinstance(history, PersistentChatMessageHistory):
                history.update_message(request.message_index, request.message)
                history.delete_message_after(request.message_index + 1)
        else:
            history.add_message(HumanMessage(content=request.message))

        agent = get_agent_executor(request.model_name)
        # We still pass history.messages to inputs because the first message
        # is necessary if the checkpointer is new. LangGraph will handle
        # deduplication if messages are identical, but it's safer to provide
        # the current message.
        inputs = {"messages": history.messages}
        config = {
            "configurable": {"thread_id": f"{request.user_id}:{request.chat_id}"},
            "metadata": {
                "user_id": request.user_id,
                "chat_id": request.chat_id,
                "model_name": request.model_name,
                "endpoint": "chat"
            },
            "tags": ["chat", "agent", request.model_name]
        }

        final_response = ""
        tool_logs: list[ToolCallLog] = []
        ui_events: list[UIEvent] = []

        ui_events.append(UIEvent(type="thinking", message="Thinking..."))

        for event in agent.stream(inputs, config=config, stream_mode="updates"):
            logger.info(f"Agent Event: {event}")

            for _, content in event.items():
                if "messages" not in content:
                    continue

                messages_to_persist = []

                for msg in content["messages"]:
                    # Don't duplicate the already-persisted user message
                    if isinstance(msg, HumanMessage):
                        continue

                    # AI messages: detect tool calls + intermediate/final text
                    if isinstance(msg, AIMessage):
                        # Tool calls announced by the model
                        if getattr(msg, "tool_calls", None):
                            for tc in msg.tool_calls:
                                tool_name = tc.get("name")
                                tool_args = tc.get("args")
                                ui_events.append(
                                    UIEvent(
                                        type="tool_call",
                                        message=f"Calling tool: {tool_name}",
                                        tool=tool_name,
                                        data={"args": tool_args},
                                    )
                                )
                                logger.info(f"Tool Call: {tool_name} with args: {tool_args}")

                        # Plain assistant content (can be intermediate step or final)
                        if msg.content:
                            text = str(msg.content)
                            final_response = text
                            ui_events.append(
                                UIEvent(
                                    type="assistant",
                                    message="Assistant produced output.",
                                    data={"text_preview": text[:200]},
                                )
                            )
                            logger.info(f"AI Response Step: {text[:100]}...")

                    # Tool results
                    if isinstance(msg, ToolMessage):
                        tool_name = getattr(msg, "name", "tool")
                        tool_out = str(msg.content)

                        ui_events.append(
                            UIEvent(
                                type="tool_result",
                                message=f"Tool finished: {tool_name}",
                                tool=tool_name,
                                data={"output_preview": tool_out[:500]},
                            )
                        )

                        tool_logs.append(
                            ToolCallLog(
                                tool=tool_name,
                                tool_input=str(getattr(msg, "tool_call_id", "")),
                                tool_output=tool_out,
                            )
                        )

                        logger.info(f"Tool Output ({tool_name}): {tool_out[:100]}...")

                    messages_to_persist.append(msg)

                if messages_to_persist:
                    history.add_messages(messages_to_persist)

        ui_events.append(UIEvent(type="done", message="Done."))

        chat_pk = get_chat_pk(request.user_id, request.chat_id)

        return ChatResponse(
            response=final_response,
            tool_calls=tool_logs,
            ui_events=ui_events,
            user_id=request.user_id,
            chat_id=request.chat_id,
            chat_pk=chat_pk,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat/stream")
@traceable(
    name="chat_stream_endpoint",
    tags=["chat", "stream", "agent", "lang-chain-mc"],
    metadata={"endpoint": "/agent/chat/stream"}
)
async def chat_stream_endpoint(request: ChatRequest):
    """
    SSE streaming chat endpoint with LangSmith tracing.
    Sends incremental UI events + assistant deltas as they happen.
    """
    try:
        history = get_session_history(request.user_id, request.chat_id)
        
        if request.message_index is not None:
            if isinstance(history, PersistentChatMessageHistory):
                history.update_message(request.message_index, request.message)
                history.delete_message_after(request.message_index + 1)
        else:
            history.add_message(HumanMessage(content=request.message))

        agent = get_agent_executor(request.model_name)

        # Inject reasoning instruction without persisting it
        # Note: In LangGraph, we can pass the system message in the first turn.
        # Checkpointer will remember previous messages, so we only need to pass
        # the NEW human message if thread exists, but passing full history
        # is also fine as LangGraph's default message state handles it.
        inputs = {"messages": [SystemMessage(content=REASONING_INSTRUCTION)] + history.messages}
        config = {
            "configurable": {"thread_id": f"{request.user_id}:{request.chat_id}"},
            "metadata": {
                "user_id": request.user_id,
                "chat_id": request.chat_id,
                "model_name": request.model_name,
                "endpoint": "chat_stream"
            },
            "tags": ["chat", "stream", "agent", request.model_name]
        }

        def sse(event: dict) -> bytes:
            return f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8")

        def event_generator():
            final_response = ""
            tool_logs: list[ToolCallLog] = []

            yield sse({"type": "thinking", "message": "Thinking..."})

            try:
                for event in agent.stream(inputs, config=config, stream_mode="updates"):
                    logger.info(f"Agent Event: {event}")

                    for _, content in event.items():
                        if "messages" not in content:
                            continue

                        messages_to_persist = []

                        for msg in content["messages"]:
                            if isinstance(msg, HumanMessage):
                                continue

                            # Tool calls announced by the model
                            if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                                for tc in msg.tool_calls:
                                    tool_name = tc.get("name")
                                    tool_args = tc.get("args")
                                    yield sse(
                                        {
                                            "type": "tool_call",
                                            "message": f"Calling tool: {tool_name}",
                                            "tool": tool_name,
                                            "data": {"args": tool_args},
                                        }
                                    )

                            # Assistant content (stream as delta if possible)
                            if isinstance(msg, AIMessage) and msg.content:
                                text = str(msg.content)

                                delta = text
                                if text.startswith(final_response):
                                    delta = text[len(final_response):]
                                final_response = text

                                if delta:
                                    yield sse({"type": "assistant_delta", "delta": delta})
                                else:
                                    yield sse({"type": "status", "message": "Assistant updated."})

                            # Tool result (includes reasoning_tool output)
                            if isinstance(msg, ToolMessage):
                                tool_name = getattr(msg, "name", "tool")
                                tool_out = str(msg.content)

                                tool_logs.append(
                                    ToolCallLog(
                                        tool=tool_name,
                                        tool_input=str(getattr(msg, "tool_call_id", "")),
                                        tool_output=tool_out,
                                    )
                                )

                                if tool_name == "reasoning_tool":
                                    # Special: reasoning summary event
                                    yield sse(
                                        {
                                            "type": "reasoning",
                                            "message": "Reasoning / Plan",
                                            "tool": tool_name,
                                            "data": {"summary": tool_out},
                                        }
                                    )
                                else:
                                    yield sse(
                                        {
                                            "type": "tool_result",
                                            "message": f"Tool finished: {tool_name}",
                                            "tool": tool_name,
                                            "data": {"output_preview": tool_out[:800]},
                                        }
                                    )

                            messages_to_persist.append(msg)

                        if messages_to_persist:
                            history.add_messages(messages_to_persist)

                chat_pk = get_chat_pk(request.user_id, request.chat_id)
                yield sse(
                    {
                        "type": "done",
                        "message": "Done.",
                        "data": {
                            "user_id": request.user_id,
                            "chat_id": request.chat_id,
                            "chat_pk": chat_pk,
                            "tool_calls": [t.model_dump() for t in tool_logs],
                            "final_response": final_response,
                        },
                    }
                )
            except Exception as e:
                logger.exception("Streaming failed")
                yield sse({"type": "error", "message": str(e)})

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/history")
async def delete_history(user_id: str, chat_id: str):
    """Deletes chat history."""
    clear_history(user_id, chat_id)
    return {"status": "History cleared"}