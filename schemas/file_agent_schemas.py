"""
Pydantic schemas for file agent API endpoints.
"""
from pydantic import BaseModel, Field
from typing import Optional


class FileCreationRequest(BaseModel):
    """Request model for file creation agent."""
    task: str = Field(..., description="Task to give to the file creation agent (e.g., 'Create a project summary markdown file named summary.md')")


class FileEditingRequest(BaseModel):
    """Request model for file editing agent."""
    task: str = Field(..., description="Task to give to the file editing agent (e.g., 'Open summary.md and append a new section about risks')")


class FileAgentResponse(BaseModel):
    """Response model for file agent operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Status message")
    output: Optional[str] = Field(None, description="Agent output/response")


class FileReadResponse(BaseModel):
    """Response model for file reading operations."""
    success: bool = Field(..., description="Whether the file read was successful")
    content: Optional[str] = Field(None, description="File content")
    error: Optional[str] = Field(None, description="Error message if read failed")
