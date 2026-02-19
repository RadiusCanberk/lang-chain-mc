from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional, Generator
from datetime import datetime, timedelta

from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker, Session

from database.models import Base
from database.models.code_execution_models import CodeExecution, WorkspaceFileMetadata
from database.models.chat_models import Chat

from utils.settings import DATABASE_URL


def _connect_args(db_url: Optional[str]) -> dict:
    """Get connection arguments based on database type"""
    if db_url and db_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


class DatabaseManager:
    """
    Unified database manager for connection, initialization, and operations.

    Handles both connection management and repository-level operations.
    """

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database manager.

        Args:
            database_url: Database connection URL (defaults to DATABASE_URL from settings, or SQLite if not set)
        """
        # Use provided URL, or DATABASE_URL from settings, or default to SQLite
        if database_url is None:
            database_url = DATABASE_URL
        
        # If still None, use default SQLite database
        if database_url is None:
            db_path = Path(__file__).parent.parent / "database.db"
            database_url = f"sqlite:///{db_path}"
        
        self.database_url = database_url
        self.engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args=_connect_args(database_url),
            echo=False  # Set to True for SQL query logging
        )

        Base.metadata.bind = self.engine
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False
        )

    def init_db(self):
        """Initialize all database tables"""
        Base.metadata.create_all(bind=self.engine)

        if self.database_url.startswith("sqlite"):
            db_path = Path(self.database_url.replace("sqlite:///", ""))
            print(f"✅ Database initialized at {db_path}")
        else:
            print("✅ Database initialized")

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions.

        Usage:
            with db_manager.get_session() as session:
                # Use session
                session.add(obj)
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_session_instance(self) -> Session:
        """
        Get a database session instance (for dependency injection).

        Note: Caller is responsible for closing the session.
        """
        return self.SessionLocal()

    # ==================== Helper Methods ====================
    
    def get_user_id_from_chat(self, chat_id: str) -> Optional[str]:
        """
        Get user_id from chats table by chat_id.
        
        Args:
            chat_id: Chat identifier (session_id)
        
        Returns:
            str: user_id or None if not found
        """
        with self.get_session() as session:
            chat = session.query(Chat)\
                .filter(Chat.chat_id == chat_id)\
                .first()
            
            return chat.user_id if chat else None

    # ==================== Execution Repository Methods ====================

    def save_execution(
            self,
            session_id: str,
            code: str,
            stdout: str,
            stderr: str,
            returncode: int,
            created_files: List[str],
            execution_time: float,
            user_id: Optional[str] = None
    ) -> int:
        """
        Save code execution result to database.
        
        Automatically fetches user_id from chats table if not provided.

        Args:
            session_id: Chat session identifier (chat_id)
            code: Executed Python code
            stdout: Standard output
            stderr: Standard error
            returncode: Exit code
            created_files: List of created file names
            execution_time: Execution time in seconds
            user_id: Optional user identifier (auto-fetched if not provided)

        Returns:
            int: Execution ID
        """
        # Auto-fetch user_id from chats table if not provided
        if user_id is None:
            user_id = self.get_user_id_from_chat(session_id)
        
        with self.get_session() as session:
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
            session.add(execution)
            session.flush()
            return execution.id

    def get_session_history(
            self,
            session_id: str,
            limit: int = 50
    ) -> List[CodeExecution]:
        """
        Get execution history for a session.

        Args:
            session_id: Session identifier
            limit: Maximum number of results

        Returns:
            List of CodeExecution objects
        """
        with self.get_session() as session:
            return session.query(CodeExecution) \
                .filter(CodeExecution.session_id == session_id) \
                .order_by(desc(CodeExecution.created_at)) \
                .limit(limit) \
                .all()

    def get_recent_executions(
            self,
            hours: int = 24,
            limit: int = 100
    ) -> List[CodeExecution]:
        """
        Get recent executions across all sessions.

        Args:
            hours: Time window in hours
            limit: Maximum number of results

        Returns:
            List of CodeExecution objects
        """
        since = datetime.utcnow() - timedelta(hours=hours)

        with self.get_session() as session:
            return session.query(CodeExecution) \
                .filter(CodeExecution.created_at >= since) \
                .order_by(desc(CodeExecution.created_at)) \
                .limit(limit) \
                .all()
    
    def get_user_executions(
            self,
            user_id: str,
            limit: int = 50
    ) -> List[CodeExecution]:
        """
        Get execution history for a specific user.
        
        Args:
            user_id: User identifier
            limit: Maximum number of results
        
        Returns:
            List of CodeExecution objects
        """
        with self.get_session() as session:
            return session.query(CodeExecution)\
                .filter(CodeExecution.user_id == user_id)\
                .order_by(desc(CodeExecution.created_at))\
                .limit(limit)\
                .all()

    def get_execution_by_id(self, execution_id: int) -> Optional[CodeExecution]:
        """
        Get execution by ID.

        Args:
            execution_id: Execution identifier

        Returns:
            CodeExecution object or None
        """
        with self.get_session() as session:
            return session.query(CodeExecution) \
                .filter(CodeExecution.id == execution_id) \
                .first()

    # ==================== Workspace Repository Methods ====================

    def save_file_metadata(
            self,
            session_id: str,
            filename: str,
            file_path: str,
            file_size: int,
            file_type: str,
            description: Optional[str] = None,
            execution_id: Optional[int] = None
    ) -> int:
        """
        Save workspace file metadata.

        Args:
            session_id: Session identifier
            filename: File name
            file_path: Relative path in workspace
            file_size: File size in bytes
            file_type: File extension/type
            description: Optional file description
            execution_id: Related execution ID

        Returns:
            int: File metadata ID
        """
        with self.get_session() as session:
            file_meta = WorkspaceFileMetadata(
                session_id=session_id,
                filename=filename,
                file_path=file_path,
                file_size=file_size,
                file_type=file_type,
                description=description,
                execution_id=execution_id
            )
            session.add(file_meta)
            session.flush()
            return file_meta.id

    def get_session_files(self, session_id: str) -> List[WorkspaceFileMetadata]:
        """
        Get all files for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of WorkspaceFileMetadata objects
        """
        with self.get_session() as session:
            return session.query(WorkspaceFileMetadata) \
                .filter(WorkspaceFileMetadata.session_id == session_id) \
                .order_by(desc(WorkspaceFileMetadata.created_at)) \
                .all()
    
    def get_user_files(self, user_id: str) -> List[WorkspaceFileMetadata]:
        """
        Get all files for a user across all sessions.
        
        Args:
            user_id: User identifier
        
        Returns:
            List of WorkspaceFileMetadata objects
        """
        with self.get_session() as session:
            # Get all chat_ids for this user
            chats = session.query(Chat.chat_id)\
                .filter(Chat.user_id == user_id)\
                .all()
            
            chat_ids = [chat.chat_id for chat in chats]
            
            if not chat_ids:
                return []
            
            return session.query(WorkspaceFileMetadata)\
                .filter(WorkspaceFileMetadata.session_id.in_(chat_ids))\
                .order_by(desc(WorkspaceFileMetadata.created_at))\
                .all()

    def get_file_by_name(
            self,
            session_id: str,
            filename: str
    ) -> Optional[WorkspaceFileMetadata]:
        """
        Get file metadata by name.

        Args:
            session_id: Session identifier
            filename: File name

        Returns:
            WorkspaceFileMetadata object or None
        """
        with self.get_session() as session:
            return session.query(WorkspaceFileMetadata) \
                .filter(
                WorkspaceFileMetadata.session_id == session_id,
                WorkspaceFileMetadata.filename == filename
            ) \
                .first()

    def update_file_description(
            self,
            session_id: str,
            filename: str,
            description: str
    ) -> bool:
        """
        Update file description.

        Args:
            session_id: Session identifier
            filename: File name
            description: New description

        Returns:
            bool: Success status
        """
        with self.get_session() as session:
            file_meta = session.query(WorkspaceFileMetadata) \
                .filter(
                WorkspaceFileMetadata.session_id == session_id,
                WorkspaceFileMetadata.filename == filename
            ) \
                .first()

            if file_meta:
                file_meta.description = description
                return True
            return False

    def delete_file_metadata(
            self,
            session_id: str,
            filename: str
    ) -> bool:
        """
        Delete file metadata.

        Args:
            session_id: Session identifier
            filename: File name

        Returns:
            bool: Success status
        """
        with self.get_session() as session:
            file_meta = session.query(WorkspaceFileMetadata) \
                .filter(
                WorkspaceFileMetadata.session_id == session_id,
                WorkspaceFileMetadata.filename == filename
            ) \
                .first()

            if file_meta:
                session.delete(file_meta)
                return True
            return False

    def get_workspace_stats(self, session_id: str) -> dict:
        """
        Get workspace statistics for a session.

        Args:
            session_id: Session identifier

        Returns:
            dict: Statistics including file count, total size, and breakdown by type
        """
        files = self.get_session_files(session_id)

        if not files:
            return {
                "session_id": session_id,
                "total_files": 0,
                "total_size": 0,
                "total_size_mb": 0,
                "by_type": {}
            }

        total_size = sum(f.file_size for f in files)

        # Group by file type
        by_type = {}
        for file_meta in files:
            file_type = file_meta.file_type or "unknown"
            if file_type not in by_type:
                by_type[file_type] = {"count": 0, "size": 0}
            by_type[file_type]["count"] += 1
            by_type[file_type]["size"] += file_meta.file_size

        return {
            "session_id": session_id,
            "total_files": len(files),
            "total_size": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "by_type": by_type
        }
    
    def get_user_workspace_stats(self, user_id: str) -> dict:
        """
        Get workspace statistics for a user across all sessions.
        
        Args:
            user_id: User identifier
        
        Returns:
            dict: Statistics including file count, total size, and breakdown by type
        """
        files = self.get_user_files(user_id)
        
        if not files:
            return {
                "user_id": user_id,
                "total_files": 0,
                "total_size": 0,
                "total_size_mb": 0,
                "by_type": {},
                "by_session": {}
            }
        
        total_size = sum(f.file_size for f in files)
        
        # Group by file type
        by_type = {}
        for file_meta in files:
            file_type = file_meta.file_type or "unknown"
            if file_type not in by_type:
                by_type[file_type] = {"count": 0, "size": 0}
            by_type[file_type]["count"] += 1
            by_type[file_type]["size"] += file_meta.file_size
        
        # Group by session
        by_session = {}
        for file_meta in files:
            session_id = file_meta.session_id
            if session_id not in by_session:
                by_session[session_id] = {"count": 0, "size": 0}
            by_session[session_id]["count"] += 1
            by_session[session_id]["size"] += file_meta.file_size
        
        return {
            "user_id": user_id,
            "total_files": len(files),
            "total_size": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "by_type": by_type,
            "by_session": by_session
        }

    def cleanup_old_files(
            self,
            session_id: str,
            older_than_hours: int = 24
    ) -> int:
        """
        Clean up old file metadata.

        Args:
            session_id: Session identifier
            older_than_hours: Delete files older than X hours

        Returns:
            int: Number of deleted records
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)

        with self.get_session() as session:
            deleted = session.query(WorkspaceFileMetadata) \
                .filter(
                WorkspaceFileMetadata.session_id == session_id,
                WorkspaceFileMetadata.created_at < cutoff_time
            ) \
                .delete()

            return deleted


# ==================== Global Instance ====================

# Create global database manager instance
db_manager = DatabaseManager()

# Legacy compatibility - keep old names
core_engine = db_manager.engine
SessionLocal = db_manager.SessionLocal
Base.metadata.bind = core_engine


def init_db():
    """Initialize database (legacy compatibility)"""
    db_manager.init_db()


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Get database session context manager (legacy compatibility)"""
    with db_manager.get_session() as session:
        yield session


def get_db_session() -> Session:
    """Get database session instance (legacy compatibility)"""
    return db_manager.get_session_instance()


init_db()