import os
import uuid
import json
import requests
import streamlit as st

st.set_page_config(page_title="LangChain Agent Chat", layout="wide")
st.title("LangChain Agentic System")

# Safe secrets/env fallback:
# - If `.streamlit/secrets.toml` doesn't exist, accessing st.secrets may raise.
try:
    API_BASE = st.secrets["API_BASE"]
except Exception:
    API_BASE = os.environ.get("API_BASE", "http://localhost:8000")


def _history_key(user_id: str, chat_id: str) -> str:
    return f"messages::{user_id}::{chat_id}"


def fetch_history(user_id: str, chat_id: str) -> list[dict]:
    resp = requests.get(
        f"{API_BASE}/agent/history",
        params={"user_id": user_id, "chat_id": chat_id},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    msgs: list[dict] = []
    for m in data.get("messages", []):
        role = m.get("role", "assistant")
        content = m.get("content", "")
        name = m.get("name")
        index = m.get("index")
        msg = {"role": role, "content": content}
        if name:
            msg["name"] = name
        if index is not None:
            msg["index"] = index
        msgs.append(msg)
    return msgs


def _new_chat_id() -> str:
    return f"chat_{uuid.uuid4().hex[:8]}"


# -----------------------
# Sidebar (Configuration)
# -----------------------
with st.sidebar:
    st.header("Configuration")

    user_id = st.text_input(
        "User ID",
        value=st.session_state.get("user_id", "default_user"),
        key="input_user_id",
    )
    st.session_state["user_id"] = user_id

    # Chat controls
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("New Chat", use_container_width=True, key="btn_new_chat"):
            st.session_state["chat_id"] = _new_chat_id()
            k = _history_key(st.session_state["user_id"], st.session_state["chat_id"])
            st.session_state[k] = []
            st.rerun()

    with col_b:
        if st.button("Load Chat", use_container_width=True, key="btn_load_chat"):
            current_chat_id = st.session_state.get("chat_id", "chat_1")
            k = _history_key(user_id, current_chat_id)
            try:
                st.session_state[k] = fetch_history(user_id, current_chat_id)
                st.success("Chat history loaded.")
            except Exception as e:
                st.error(f"Failed to load history: {e}")

    chat_id = st.text_input(
        "Chat ID",
        value=st.session_state.get("chat_id", "chat_1"),
        key="input_chat_id",
    )
    st.session_state["chat_id"] = chat_id

    model_name = st.selectbox(
        "Model Name",
        ["google/gemini-3-flash-preview", "moonshotai/kimi-k2.5", "openai/gpt-5.2", "openai/gpt-3.5-turbo", "openai/gpt-4-turbo", "anthropic/claude-3-opus", "google/gemini-pro-1.5"],
        index=0,
        key="select_model_name",
    )

    st.subheader("Agent Panels")
    show_reasoning = st.toggle("Show Reasoning / Plan", value=True, key="toggle_show_reasoning")
    show_tools = st.toggle("Show Tool Calls & Results", value=True, key="toggle_show_tools")
    show_debug = st.toggle("Show Debug Events", value=False, key="toggle_show_debug")

    st.subheader("Transport")
    use_streaming = st.toggle("Streaming responses (SSE)", value=True, key="toggle_use_streaming")

    col_c, col_d = st.columns(2)
    with col_c:
        if st.button("Refresh History", use_container_width=True, key="btn_refresh_history"):
            k = _history_key(user_id, chat_id)
            try:
                st.session_state[k] = fetch_history(user_id, chat_id)
                st.success("History refreshed.")
            except Exception as e:
                st.error(f"Failed to refresh: {e}")

    with col_d:
        if st.button("Clear Chat History", use_container_width=True, key="btn_clear_history"):
            try:
                resp = requests.delete(
                    f"{API_BASE}/agent/history",
                    params={"user_id": user_id, "chat_id": chat_id},
                    timeout=60,
                )
                if resp.status_code == 200:
                    k = _history_key(user_id, chat_id)
                    st.session_state[k] = []
                    st.success("History cleared!")
                else:
                    st.error(f"Failed to clear history: {resp.status_code} - {resp.text}")
            except Exception as e:
                st.error(f"Error: {e}")

    st.caption(f"API: {API_BASE}")


# -----------------------------------------
# Initialize per-chat message cache (DB -> UI)
# -----------------------------------------
key = _history_key(user_id, chat_id)
if key not in st.session_state:
    st.session_state[key] = []
    try:
        st.session_state[key] = fetch_history(user_id, chat_id)
    except Exception:
        # API down or empty chat -> ignore
        st.session_state[key] = []

messages = st.session_state[key]


# -----------------------
# Render chat history
# -----------------------
# Re-fetch messages if needed (e.g. after edit)
messages = st.session_state[key]

# We need a placeholder to re-trigger the chat if an edit happens in session state
if "edit_triggered_prompt" not in st.session_state:
    st.session_state.edit_triggered_prompt = None
if "edit_triggered_index" not in st.session_state:
    st.session_state.edit_triggered_index = None

for i, message in enumerate(messages):
    role = message.get("role", "assistant")
    content = message.get("content", "")
    msg_index = message.get("index", i)

    with st.chat_message(role):
        col1, col2 = st.columns([0.9, 0.1])
        with col1:
            # Hide the original content if currently editing this message
            if not st.session_state.get(f"editing_{msg_index}"):
                st.markdown(content)

        # Only allow editing user messages for now
        if role == "user":
            with col2:
                if st.button("📝", key=f"edit_{msg_index}"):
                    st.session_state[f"editing_{msg_index}"] = True
                    st.rerun()

            if st.session_state.get(f"editing_{msg_index}"):
                new_content = st.text_area("Edit message:", value=content, key=f"area_{msg_index}")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Save & Resend", key=f"save_{msg_index}"):
                        # Update session state triggers
                        st.session_state.edit_triggered_prompt = new_content
                        st.session_state.edit_triggered_index = msg_index
                        st.session_state[f"editing_{msg_index}"] = False

                        # Refresh history in session state locally for immediate feedback before API call
                        # (The chat block below will then use the provided index to update backend)
                        st.rerun()
                with c2:
                    if st.button("Cancel", key=f"cancel_{msg_index}"):
                        st.session_state[f"editing_{msg_index}"] = False
                        st.rerun()

        if role == "assistant":
            reasoning_summary = message.get("reasoning_summary", "")
            tool_events = message.get("tool_events", [])
            debug_events = message.get("debug_events", [])

            if show_reasoning and reasoning_summary:
                with st.expander("Reasoning / Plan", expanded=False):
                    st.markdown(reasoning_summary)

            if show_tools and tool_events:
                with st.expander("Tools", expanded=False):
                    for ev in tool_events[-50:]:
                        line = f"[{ev.get('type')}] {ev.get('message', '')}"
                        if ev.get("tool"):
                            line += f" (tool={ev.get('tool')})"
                        st.write(line)
                        if ev.get("data"):
                            st.code(ev["data"], language="json")

            if show_debug and debug_events:
                with st.expander("Debug", expanded=False):
                    for ev in debug_events[-100:]:
                        st.write(f"[{ev.get('type')}] {ev.get('message', '')}")
                        if ev.get("data"):
                            st.code(ev["data"], language="json")


# -----------------------
# Chat input + streaming
# -----------------------
# Handle stop button during streaming
if "streaming" not in st.session_state:
    st.session_state.streaming = False

prompt = st.chat_input("Type your message...", key="chat_input_prompt")

edit_triggered_prompt = st.session_state.edit_triggered_prompt
edit_triggered_index = st.session_state.edit_triggered_index

if prompt or edit_triggered_prompt:
    current_prompt = prompt or edit_triggered_prompt
    current_index = edit_triggered_index

    # Clear the triggers so they don't run again on next rerun
    st.session_state.edit_triggered_prompt = None
    st.session_state.edit_triggered_index = None

    # Optimistic UI update: add user message (if not from edit)
    if prompt:
        messages.append({"role": "user", "content": current_prompt})
        st.session_state[key] = messages

    if prompt:
        with st.chat_message("user"):
            st.markdown(current_prompt)

    with st.chat_message("assistant"):
        payload = {
            "user_id": user_id,
            "chat_id": chat_id,
            "message": current_prompt,
            "model_name": model_name,
        }
        if current_index is not None:
            payload["message_index"] = current_index

        # Dedicated placeholders for panels
        reasoning_box = st.empty()
        tools_box = st.empty()
        debug_box = st.empty()
        answer_box = st.empty()
        stop_button_placeholder = st.empty()

        acc_text = ""
        reasoning_summary = ""
        tool_events: list[dict] = []
        debug_events: list[dict] = []

        def render_panels_local():
            if show_reasoning and reasoning_summary:
                with reasoning_box.container():
                    with st.expander("Reasoning / Plan", expanded=True):
                        st.markdown(reasoning_summary)

            if show_tools and tool_events:
                with tools_box.container():
                    with st.expander("Tools", expanded=False):
                        for ev in tool_events[-50:]:
                            line = f"[{ev.get('type')}] {ev.get('message', '')}"
                            if ev.get("tool"):
                                line += f" (tool={ev.get('tool')})"
                            st.write(line)
                            if ev.get("data"):
                                st.code(ev["data"], language="json")

            if show_debug and debug_events:
                with debug_box.container():
                    with st.expander("Debug", expanded=False):
                        for ev in debug_events[-100:]:
                            st.write(f"[{ev.get('type')}] {ev.get('message', '')}")
                            if ev.get("data"):
                                st.code(ev["data"], language="json")

        st.session_state.streaming = True
        stop_pressed = False

        try:
            if use_streaming:
                with requests.post(
                    f"{API_BASE}/agent/chat/stream",
                    json=payload,
                    stream=True,
                    timeout=300,
                    headers={"Accept": "text/event-stream"},
                ) as resp:
                    resp.raise_for_status()

                    for raw_line in resp.iter_lines(decode_unicode=True):
                        # Check for stop button
                        if stop_button_placeholder.button("Stop Generation", key=f"stop_{uuid.uuid4()}"):
                            stop_pressed = True
                            break

                        if not raw_line:
                            continue
                        if not raw_line.startswith("data: "):
                            continue

                        data_str = raw_line[len("data: "):].strip()
                        try:
                            ev = json.loads(data_str)
                        except Exception:
                            continue

                        ev_type = ev.get("type")

                        if ev_type == "reasoning":
                            summary = (ev.get("data") or {}).get("summary", "")
                            if summary:
                                reasoning_summary = summary
                                render_panels_local()

                        elif ev_type in ("tool_call", "tool_result"):
                            tool_events.append(
                                {
                                    "type": ev_type,
                                    "message": ev.get("message", ""),
                                    "tool": ev.get("tool"),
                                    "data": ev.get("data"),
                                }
                            )
                            render_panels_local()

                        elif ev_type == "assistant_delta":
                            delta = ev.get("delta", "")
                            acc_text += delta
                            answer_box.markdown(acc_text)

                        elif ev_type in ("thinking", "status", "done", "error"):
                            debug_events.append(
                                {
                                    "type": ev_type,
                                    "message": ev.get("message", ""),
                                    "data": ev.get("data"),
                                }
                            )
                            render_panels_local()

                            if ev_type in ("done", "error"):
                                break

                stop_button_placeholder.empty()
                if stop_pressed:
                    st.warning("Generation stopped by user.")
                    # Even if stopped, we might want to save what we have
                    if acc_text:
                        # Optional: persist partial message or not?
                        # User said "durdurup daha sonra yazdığı soruyu devam ettirme"
                        # This implies we can stop and then edit.
                        pass

                # Persist assistant message + panels in session history
                messages.append(
                    {
                        "role": "assistant",
                        "content": acc_text + (" (Stopped)" if stop_pressed else ""),
                        "reasoning_summary": reasoning_summary,
                        "tool_events": tool_events,
                        "debug_events": debug_events,
                    }
                )
                st.session_state[key] = messages
                st.session_state.streaming = False
                st.rerun()

            else:
                # Fallback sync endpoint
                with st.spinner("Thinking..."):
                    r = requests.post(f"{API_BASE}/agent/chat", json=payload, timeout=300)
                r.raise_for_status()
                data = r.json()

                acc_text = data.get("response", "")
                answer_box.markdown(acc_text)

                # If backend returns ui_events, map them into our panels best-effort
                for ev in data.get("ui_events", []):
                    t = ev.get("type")
                    if t == "reasoning":
                        reasoning_summary = (ev.get("data") or {}).get("summary", reasoning_summary)
                    elif t in ("tool_call", "tool_result"):
                        tool_events.append(ev)
                    else:
                        debug_events.append(ev)

                render_panels_local()

                messages.append(
                    {
                        "role": "assistant",
                        "content": acc_text,
                        "reasoning_summary": reasoning_summary,
                        "tool_events": tool_events,
                        "debug_events": debug_events,
                    }
                )
                st.session_state[key] = messages

        except Exception as e:
            st.error(f"Request failed: {e}")