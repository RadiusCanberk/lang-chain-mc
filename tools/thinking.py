from langchain_tavily import TavilySearch
from langchain_core.tools import tool

from utils.settings import TAVILY_API_KEY
from tools.python_executor import run_python_code, list_workspace_files, read_workspace_file, get_execution_history

web_search_tool = TavilySearch(
    max_results=3,
    description="Search the web for current events or facts.",
    api_key=TAVILY_API_KEY,
)


@tool
def reasoning_tool(reasoning_summary: str):
    """
    User-visible reasoning summary / plan.

    Keep it short (2-6 bullets). No hidden chain-of-thought. No sensitive content.
    """
    return reasoning_summary


def get_tools():
    return [
        web_search_tool,
        reasoning_tool,
        run_python_code,
        list_workspace_files,
        read_workspace_file,
        get_execution_history,
    ]