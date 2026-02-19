"""
File management agents for creating and editing files in the workspace.
"""
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langsmith import traceable
from tools.file_tools import get_file_tools
from utils.settings import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    SYSTEM_PROMPTS,
)


@traceable(name="file_creation_agent", tags=["file-agent", "file-creation", "lang-chain-mc"])
def get_file_creation_agent(model_name: str = "gpt-4o-mini"):
    """
    Creates and returns a LangGraph agent specialized for file creation.
    
    This agent is designed to create markdown files and other text files
    in the workspace based on user requests.
    
    Args:
        model_name: The model name to use for the LLM (default: "gpt-4o-mini")
    
    Returns:
        The agent executor with file creation tools
    """
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is missing!")
    if not OPENROUTER_BASE_URL:
        raise ValueError("OPENROUTER_BASE_URL is missing!")

    llm = ChatOpenAI(
        model=model_name,
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        temperature=0,
        metadata={
            "langsmith_project": "lang-chain-mc",
            "model_name": model_name,
            "agent_type": "file_creation",
        }
    )

    tools = get_file_tools()

    # Get system prompt for file creator
    system_prompt = SYSTEM_PROMPTS.get("file_creator", SYSTEM_PROMPTS["general_assistant"])

    # Create agent
    agent = create_agent(
        llm,
        tools,
        system_prompt=system_prompt,
    )

    return agent


@traceable(name="file_editing_agent", tags=["file-agent", "file-editing", "lang-chain-mc"])
def get_file_editing_agent(model_name: str = "gpt-4o-mini"):
    """
    Creates and returns a LangGraph agent specialized for file editing.
    
    This agent is designed to read existing files from the workspace,
    analyze them, and update them according to user instructions.
    
    Args:
        model_name: The model name to use for the LLM (default: "gpt-4o-mini")
    
    Returns:
        The agent executor with file editing tools
    """
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is missing!")
    if not OPENROUTER_BASE_URL:
        raise ValueError("OPENROUTER_BASE_URL is missing!")

    llm = ChatOpenAI(
        model=model_name,
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        temperature=0,
        metadata={
            "langsmith_project": "lang-chain-mc",
            "model_name": model_name,
            "agent_type": "file_editing",
        }
    )

    tools = get_file_tools()

    # Get system prompt for file editor
    system_prompt = SYSTEM_PROMPTS.get("file_editor", SYSTEM_PROMPTS["general_assistant"])

    # Create agent
    agent = create_agent(
        llm,
        tools,
        system_prompt=system_prompt,
    )

    return agent


# Pre-configured agent instances (for LangGraph Studio)
file_creation_agent_executor = get_file_creation_agent("gpt-4o-mini")
file_editing_agent_executor = get_file_editing_agent("gpt-4o-mini")
