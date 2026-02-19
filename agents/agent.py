from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langsmith import traceable
from tools.thinking import get_tools
from utils.settings import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    LANGCHAIN_TRACING_V2,
    SYSTEM_PROMPTS,
)


@traceable(name="agent_executor", tags=["agent", "lang-chain-mc"])
def get_agent_executor(model_name: str, system_prompt_key: str = "code_interpreter", use_checkpointer: bool = False):
    """
    Creates and returns a LangGraph agent with LangSmith tracing enabled.

    Args:
        model_name: The model name to use for the LLM
        system_prompt_key: Key for system prompt from system_prompts.json
                          Options: "code_interpreter", "writer", "general_assistant"
        use_checkpointer: Whether to use a checkpointer (only for local FastAPI, not for LangGraph Studio)

    Returns:
        The agent executor with tools and optional checkpointer
    """
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is missing!")
    if not OPENROUTER_BASE_URL:
        raise ValueError("OPENROUTER_BASE_URL is missing!")

    llm = ChatOpenAI(
        model=model_name,
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        temperature=0.7,
        metadata={
            "langsmith_project": "lang-chain-mc",
            "model_name": model_name,
        }
    )

    tools = get_tools()

    # Get system prompt from JSON
    system_prompt = SYSTEM_PROMPTS.get(system_prompt_key, SYSTEM_PROMPTS["code_interpreter"])

    # Create agent without checkpointer by default (for LangGraph Studio compatibility)
    agent = create_agent(
        llm,
        tools,
        system_prompt=system_prompt,
    )

    return agent


# Dynamic agent instance (visible in LangSmith)
dynamic_agent_executor = get_agent_executor("gpt-4.1", "code_interpreter")
writer_executor_agent = get_agent_executor("gpt-4.1", "writer")
agent_executor = get_agent_executor("gpt-4.1", "general_assistant")