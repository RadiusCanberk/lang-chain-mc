from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime

from database.models import Base


class CodeExecution(Base):
    """Store code execution history"""
    __tablename__ = "code_executions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), index=True, nullable=False)
    user_id = Column(String(255), index=True, nullable=True)
    code = Column(Text, nullable=False)
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    returncode = Column(Integer, nullable=False)
    created_files = Column(JSON, default=list)  # List of filenames
    execution_time = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationship
    workspace_files = relationship("WorkspaceFileMetadata", back_populates="execution")


class WorkspaceFileMetadata(Base):
    """Store workspace file metadata"""
    __tablename__ = "workspace_files"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), index=True, nullable=False)
    filename = Column(String(512), nullable=False)
    file_path = Column(String(1024), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    execution_id = Column(Integer, ForeignKey("code_executions.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationship
    execution = relationship("CodeExecution", back_populates="workspace_files")