from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timedelta

from database.models.code_execution_models import CodeExecution, WorkspaceFileMetadata
from schemas.code_execution_schemas import CodeExecutionResult, WorkspaceFile


class ExecutionRepository:
    """Repository for code execution operations"""
    
    @staticmethod
    def save_execution(
        db: Session,
        session_id: str,
        code: str,
        stdout: str,
        stderr: str,
        returncode: int,
        created_files: List[str],
        execution_time: float,
        user_id: Optional[str] = None
    ) -> CodeExecution:
        """Save code execution result to database"""
        execution = CodeExecution(
            session_id=session_id,
            user_id=user_id,
            code=code,
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
            created_files=created_files,
            execution_time=execution_time
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        return execution
    
    @staticmethod
    def get_session_history(
        db: Session,
        session_id: str,
        limit: int = 50
    ) -> List[CodeExecution]:
        """Get execution history for a session"""
        result = db.query(CodeExecution)\
            .filter(CodeExecution.session_id == session_id)\
            .order_by(desc(CodeExecution.created_at))\
            .limit(limit)\
            .all()
        return result
    
    @staticmethod
    def get_recent_executions(
        db: Session,
        hours: int = 24,
        limit: int = 100
    ) -> List[CodeExecution]:
        """Get recent executions across all sessions"""
        since = datetime.utcnow() - timedelta(hours=hours)
        result = db.query(CodeExecution)\
            .filter(CodeExecution.created_at >= since)\
            .order_by(desc(CodeExecution.created_at))\
            .limit(limit)\
            .all()
        return result


class WorkspaceRepository:
    """Repository for workspace file operations"""
    
    @staticmethod
    def save_file_metadata(
        db: Session,
        session_id: str,
        filename: str,
        file_path: str,
        file_size: int,
        file_type: str,
        description: Optional[str] = None,
        execution_id: Optional[int] = None
    ) -> WorkspaceFileMetadata:
        """Save workspace file metadata"""
        file_meta = WorkspaceFileMetadata(
            session_id=session_id,
            filename=filename,
            file_path=file_path,
            file_size=file_size,
            file_type=file_type,
            description=description,
            execution_id=execution_id
        )
        db.add(file_meta)
        db.commit()
        db.refresh(file_meta)
        return file_meta
    
    @staticmethod
    def get_session_files(
        db: Session,
        session_id: str
    ) -> List[WorkspaceFileMetadata]:
        """Get all files for a session"""
        result = db.query(WorkspaceFileMetadata)\
            .filter(WorkspaceFileMetadata.session_id == session_id)\
            .order_by(desc(WorkspaceFileMetadata.created_at))\
            .all()
        return result
    
    @staticmethod
    def get_file_by_name(
        db: Session,
        session_id: str,
        filename: str
    ) -> Optional[WorkspaceFileMetadata]:
        """Get file metadata by name"""
        result = db.query(WorkspaceFileMetadata)\
            .filter(
                WorkspaceFileMetadata.session_id == session_id,
                WorkspaceFileMetadata.filename == filename
            )\
            .first()
        return result