from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class CodeExecutionResult(BaseModel):
    """Schema for code execution results"""
    id: Optional[int] = None
    session_id: str = Field(..., description="Chat session identifier")
    user_id: Optional[str] = Field(None, description="User identifier")
    code: str = Field(..., description="Executed Python code")
    stdout: Optional[str] = Field(None, description="Standard output")
    stderr: Optional[str] = Field(None, description="Standard error")
    returncode: int = Field(..., description="Exit code")
    created_files: List[str] = Field(default_factory=list, description="List of created file names")
    execution_time: Optional[float] = Field(None, description="Execution time in seconds")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class WorkspaceFile(BaseModel):
    """Schema for workspace file metadata"""
    id: Optional[int] = None
    session_id: str = Field(..., description="Chat session identifier")
    filename: str = Field(..., description="File name")
    file_path: str = Field(..., description="Relative path in workspace")
    file_size: int = Field(..., description="File size in bytes")
    file_type: str = Field(..., description="File extension/type")
    description: Optional[str] = Field(None, description="File description/purpose")
    execution_id: Optional[int] = Field(None, description="Related execution ID")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class ExecutionHistoryResponse(BaseModel):
    """Response schema for execution history"""
    total_count: int
    executions: List[CodeExecutionResult]
    files: List[WorkspaceFile]