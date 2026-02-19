"""
FastAPI router for file agent endpoints.
"""
from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage
from langsmith import traceable

from agents.file_agents import get_file_creation_agent, get_file_editing_agent
from schemas.file_agent_schemas import (
    FileCreationRequest,
    FileEditingRequest,
    FileAgentResponse,
    FileReadResponse,
)
from tools.file_tools import read_file_func
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/create", response_model=FileAgentResponse)
@traceable(
    name="file_creation_endpoint",
    tags=["file-agents", "file-creation", "lang-chain-mc"],
    metadata={"endpoint": "/file-agents/create"}
)
async def trigger_file_creation(request: FileCreationRequest):
    """
    Triggers the file creation agent (Agent1).
    
    This agent creates markdown files and other text files in the workspace
    based on user requests.
    """
    try:
        agent = get_file_creation_agent()
        
        # Invoke agent with user task
        result = agent.invoke({
            "messages": [HumanMessage(content=request.task)]
        })
        
        # Extract result
        output = None
        if isinstance(result, dict) and "messages" in result:
            last_message = result["messages"][-1]
            output = last_message.content if hasattr(last_message, "content") else str(last_message)
        else:
            output = str(result)
        
        logger.info(f"File creation agent executed successfully. Output: {output[:200]}...")
        
        return FileAgentResponse(
            success=True,
            message="File creation agent executed successfully",
            output=output
        )
    except Exception as e:
        logger.exception("Error occurred while executing file creation agent")
        raise HTTPException(
            status_code=500,
            detail=f"Error occurred while executing file creation agent: {str(e)}"
        )


@router.post("/edit", response_model=FileAgentResponse)
@traceable(
    name="file_editing_endpoint",
    tags=["file-agents", "file-editing", "lang-chain-mc"],
    metadata={"endpoint": "/file-agents/edit"}
)
async def trigger_file_editing(request: FileEditingRequest):
    """
    Triggers the file editing agent (Agent2).
    
    This agent reads existing files from the workspace, analyzes them,
    and updates them according to user instructions.
    """
    try:
        agent = get_file_editing_agent()
        
        # Invoke agent with user task
        result = agent.invoke({
            "messages": [HumanMessage(content=request.task)]
        })
        
        # Extract result
        output = None
        if isinstance(result, dict) and "messages" in result:
            last_message = result["messages"][-1]
            output = last_message.content if hasattr(last_message, "content") else str(last_message)
        else:
            output = str(result)
        
        logger.info(f"File editing agent executed successfully. Output: {output[:200]}...")
        
        return FileAgentResponse(
            success=True,
            message="File editing agent executed successfully",
            output=output
        )
    except Exception as e:
        logger.exception("Error occurred while executing file editing agent")
        raise HTTPException(
            status_code=500,
            detail=f"Error occurred while executing file editing agent: {str(e)}"
        )


@router.get("/files/{filename}", response_model=FileReadResponse)
@traceable(
    name="file_read_endpoint",
    tags=["file-agents", "file-read", "lang-chain-mc"],
    metadata={"endpoint": "/file-agents/files/{filename}"}
)
async def read_file(filename: str):
    """
    Reads a file from the workspace.
    
    Args:
        filename: Name of the file to read (e.g., "summary.md")
    """
    try:
        content = read_file_func(filename)
        
        # Check if read_file_func returned an error message
        if content.startswith("Error:"):
            return FileReadResponse(
                success=False,
                content=None,
                error=content
            )
        
        logger.info(f"File read successfully: {filename}")
        
        return FileReadResponse(
            success=True,
            content=content,
            error=None
        )
    except Exception as e:
        logger.exception(f"Error occurred while reading file: {filename}")
        return FileReadResponse(
            success=False,
            content=None,
            error=f"Error occurred while reading file: {str(e)}"
        )
