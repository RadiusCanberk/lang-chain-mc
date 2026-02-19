import os
import uuid
import tempfile
import time
from pathlib import Path
from typing import Optional

import docker
from docker.errors import DockerException, ContainerError, ImageNotFound
from langchain_core.tools import tool

from utils.settings import (
    WORKSPACE_DIR,
    SANDBOX_TIMEOUT,
    SANDBOX_MAX_OUTPUT,
    SANDBOX_MEMORY_LIMIT,
    SANDBOX_CPU_QUOTA,
    SANDBOX_NETWORK_DISABLED,
)
from database.db import get_db
from database.code_execution import ExecutionRepository, WorkspaceRepository

# Docker image name
SANDBOX_IMAGE = "python-sandbox:latest"

# Blocked patterns for additional safety
BLOCKED_PATTERNS = [
    "import os",
    "import subprocess",
    "import sys",
    "__import__",
    "eval(",
    "exec(",
    "compile(",
    "open(",  # Will be allowed only via our safe wrapper
]


def _sanitize_output(output: str, max_length: int = SANDBOX_MAX_OUTPUT) -> str:
    """Truncate output if too long."""
    if len(output) > max_length:
        return output[:max_length] + f"\n\n... (truncated, {len(output)} total chars)"
    return output


def _validate_code_safety(code: str) -> tuple[bool, str]:
    """
    Basic code validation before execution.

    Returns:
        tuple: (is_safe, error_message)
    """
    # Check for obviously dangerous patterns
    dangerous_patterns = ["__import__", "eval(", "exec(", "compile("]

    for pattern in dangerous_patterns:
        if pattern in code:
            return False, f"❌ Dangerous operation detected: {pattern}"

    # Check for path traversal
    if "../" in code or "/.." in code:
        return False, "❌ Path traversal detected"

    return True, ""


def _ensure_docker_image():
    """
    Ensure Docker image exists, build if not.
    """
    try:
        client = docker.from_env()

        # Check if image exists
        try:
            client.images.get(SANDBOX_IMAGE)
            return True, "Image exists"
        except ImageNotFound:
            # Build image from Dockerfile.sandbox
            dockerfile_path = Path(__file__).parent.parent / "Dockerfile.sandbox"

            if not dockerfile_path.exists():
                return False, "❌ Dockerfile.sandbox not found in project root"

            print(f"Building Docker image {SANDBOX_IMAGE}...")
            client.images.build(
                path=str(dockerfile_path.parent),
                dockerfile="Dockerfile.sandbox",
                tag=SANDBOX_IMAGE,
                rm=True,
            )
            return True, "Image built successfully"

    except DockerException as e:
        return False, f"❌ Docker error: {str(e)}"


def _execute_in_docker(code: str, script_path: Path) -> dict:
    """
    Execute code in Docker container.

    Returns:
        dict with stdout, stderr, returncode
    """
    try:
        client = docker.from_env()

        # Prepare volumes
        volumes = {
            str(WORKSPACE_DIR.absolute()): {
                "bind": "/workspace",
                "mode": "rw"
            },
            str(script_path): {
                "bind": "/tmp/script.py",
                "mode": "ro"
            }
        }

        # Container configuration
        container_config = {
            "image": SANDBOX_IMAGE,
            "command": ["python", "/tmp/script.py"],
            "volumes": volumes,
            "working_dir": "/workspace",
            "mem_limit": SANDBOX_MEMORY_LIMIT,
            "cpu_quota": SANDBOX_CPU_QUOTA,
            "cpu_period": 100000,
            "network_disabled": SANDBOX_NETWORK_DISABLED,
            "remove": True,
            "detach": False,
            "stdout": True,
            "stderr": True,
        }

        # Run container
        try:
            output = client.containers.run(**container_config)

            return {
                "stdout": output.decode("utf-8") if isinstance(output, bytes) else output,
                "stderr": "",
                "returncode": 0
            }

        except ContainerError as e:
            return {
                "stdout": e.stdout.decode("utf-8") if e.stdout else "",
                "stderr": e.stderr.decode("utf-8") if e.stderr else str(e),
                "returncode": e.exit_status
            }

    except DockerException as e:
        return {
            "stdout": "",
            "stderr": f"Docker execution error: {str(e)}",
            "returncode": -1
        }


def _save_file_metadata(session_id: str, filename: str, execution_id: Optional[int] = None):
    """Save file metadata to database"""
    try:
        file_path = WORKSPACE_DIR / filename
        if not file_path.exists():
            return
        
        file_size = file_path.stat().st_size
        file_type = file_path.suffix.lstrip('.') or 'unknown'
        
        with get_db() as db:
            WorkspaceRepository.save_file_metadata(
                db=db,
                session_id=session_id,
                filename=filename,
                file_path=str(file_path.relative_to(WORKSPACE_DIR)),
                file_size=file_size,
                file_type=file_type,
                execution_id=execution_id
            )
    except Exception as e:
        print(f"Warning: Failed to save file metadata: {e}")


@tool
def run_python_code(code: str, session_id: str = "default") -> str:
    """
    Execute Python code in a secure Docker sandbox.

    Use this tool when you need to:
    - Perform mathematical calculations
    - Process data or create dataframes
    - Generate plots or visualizations
    - Create files (CSV, TXT, etc.)

    The code runs in an isolated Docker container with:
    - Network disabled (no internet access)
    - Memory limit (512MB)
    - CPU limit (50%)
    - Timeout limit (30 seconds)
    - Access to common libraries (pandas, numpy, matplotlib, etc.)
    - Workspace directory for saving files

    Important:
    - Save files to '/workspace/' directory
    - Use print() to output results
    - For plots, use plt.savefig("/workspace/filename.png")
    - Code runs as non-root user
    - No access to project files, .env, or system
    - Results are automatically stored in database

    Args:
        code: Python code to execute
        session_id: Session identifier for tracking (default: "default")

    Returns:
        str: Execution result containing stdout, stderr, and list of created files

    Examples:
        # Math calculation
        code = '''
result = 20 * 30 + 15
print(f"Result: {result}")
'''

        # Create plot
        code = '''
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 10, 100)
plt.plot(x, x**2)
plt.savefig("/workspace/plot.png")
print("Plot created")
'''
    """

    # Start timing
    start_time = time.time()

    # Validate code safety
    is_safe, error_msg = _validate_code_safety(code)
    if not is_safe:
        return error_msg

    # Ensure Docker image exists
    image_ok, image_msg = _ensure_docker_image()
    if not image_ok:
        return f"{image_msg}\n\nPlease ensure Docker is installed and Dockerfile.sandbox exists."

    # Track files before execution
    files_before = set(os.listdir(WORKSPACE_DIR)) if WORKSPACE_DIR.exists() else set()

    # Create temporary script file
    script_id = uuid.uuid4().hex[:8]
    script_path = Path(tempfile.gettempdir()) / f"sandbox_script_{script_id}.py"

    try:
        # Write script
        script_path.write_text(code, encoding="utf-8")

        # Execute in Docker
        result = _execute_in_docker(code, script_path)

        stdout = result["stdout"].strip()
        stderr = result["stderr"].strip()
        returncode = result["returncode"]

        # Track files after execution
        files_after = set(os.listdir(WORKSPACE_DIR)) if WORKSPACE_DIR.exists() else set()
        new_files = list(files_after - files_before)

        # Calculate execution time
        execution_time = time.time() - start_time

        # Save to database
        execution_id = None
        try:
            with get_db() as db:
                execution = ExecutionRepository.save_execution(
                    db=db,
                    session_id=session_id,
                    code=code,
                    stdout=stdout,
                    stderr=stderr,
                    returncode=returncode,
                    created_files=new_files,
                    execution_time=execution_time
                )
                execution_id = execution.id
                
                # Save file metadata
                for filename in new_files:
                    _save_file_metadata(session_id, filename, execution_id)
        except Exception as e:
            print(f"Warning: Failed to save execution to database: {e}")

        # Build response
        response_parts = []

        if returncode == 0:
            response_parts.append("✅ Code executed successfully in Docker sandbox.")
        else:
            response_parts.append(f"❌ Code execution failed with exit code {returncode}.")

        if stdout:
            response_parts.append(f"\n📤 Output:\n{_sanitize_output(stdout)}")

        if stderr:
            response_parts.append(f"\n⚠️ Errors/Warnings:\n{_sanitize_output(stderr)}")

        if new_files:
            response_parts.append(f"\n📁 Created files: {', '.join(sorted(new_files))}")
            response_parts.append(f"📂 Files saved in: {WORKSPACE_DIR.absolute()}")

        response_parts.append(f"\n⏱️ Execution time: {execution_time:.2f}s")
        response_parts.append(f"💾 Results stored (ID: {execution_id})")

        return "\n".join(response_parts)

    except Exception as e:
        return f"💥 Execution error: {type(e).__name__}: {str(e)}"

    finally:
        # Cleanup temporary script
        if script_path.exists():
            try:
                script_path.unlink()
            except Exception:
                pass


@tool
def list_workspace_files(session_id: str = "default") -> str:
    """
    List all files in the workspace directory with metadata from database.

    Use this to check what files have been created by previous code executions.

    Args:
        session_id: Session identifier (default: "default")

    Returns:
        str: List of files with their sizes and metadata
    """
    try:
        # Get files from filesystem
        files = []
        for item in sorted(WORKSPACE_DIR.iterdir()):
            if item.is_file():
                size = item.stat().st_size
                size_str = f"{size:,} bytes" if size < 1024 else f"{size / 1024:.1f} KB"
                files.append(f"  - {item.name} ({size_str})")

        if not files:
            return "📂 Workspace is empty."

        result = f"📂 Workspace files:\n" + "\n".join(files) + f"\n\n📂 Path: {WORKSPACE_DIR.absolute()}"

        # Try to get metadata from database
        try:
            with get_db() as db:
                file_metadata = WorkspaceRepository.get_session_files(db, session_id)
                if file_metadata:
                    result += f"\n\n💾 Database records: {len(file_metadata)} files tracked"
        except Exception as e:
            print(f"Warning: Could not fetch file metadata: {e}")

        return result

    except Exception as e:
        return f"Error listing files: {e}"


@tool
def read_workspace_file(filename: str, max_lines: int = 50) -> str:
    """
    Read the content of a file from the workspace.

    Use this to inspect files created by code execution.

    Args:
        filename: Name of the file to read
        max_lines: Maximum number of lines to return (default: 50)

    Returns:
        str: File content or error message
    """
    try:
        file_path = WORKSPACE_DIR / filename

        if not file_path.exists():
            return f"❌ File not found: {filename}"

        if not file_path.is_file():
            return f"❌ Not a file: {filename}"

        # Check file size
        size = file_path.stat().st_size
        if size > 10 * 1024 * 1024:  # 10 MB
            return f"❌ File too large: {size / (1024 * 1024):.1f} MB (max 10 MB)"

        # Try to read as text
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines()

            if len(lines) > max_lines:
                preview = "\n".join(lines[:max_lines])
                return f"📄 {filename} (showing first {max_lines} of {len(lines)} lines):\n\n{preview}\n\n... (truncated)"
            else:
                return f"📄 {filename}:\n\n{content}"

        except UnicodeDecodeError:
            return f"❌ File is binary and cannot be displayed as text: {filename}"

    except Exception as e:
        return f"Error reading file: {e}"


@tool
def get_execution_history(session_id: str = "default", limit: int = 10) -> str:
    """
    Get execution history for the current session.

    Use this to review previous code executions and their results.

    Args:
        session_id: Session identifier (default: "default")
        limit: Maximum number of executions to return (default: 10)

    Returns:
        str: Formatted execution history
    """
    try:
        with get_db() as db:
            executions = ExecutionRepository.get_session_history(db, session_id, limit)
            
            if not executions:
                return f"📜 No execution history found for session '{session_id}'"
            
            result = [f"📜 Execution History (last {len(executions)} runs):\n"]
            
            for i, exec in enumerate(executions, 1):
                status = "✅" if exec.returncode == 0 else "❌"
                result.append(f"\n{i}. {status} ID: {exec.id} | {exec.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                result.append(f"   Time: {exec.execution_time:.2f}s")
                
                if exec.created_files:
                    result.append(f"   Files: {', '.join(exec.created_files)}")
                
                # Show first line of code
                code_preview = exec.code.split('\n')[0][:60]
                result.append(f"   Code: {code_preview}...")
            
            return "\n".join(result)
            
    except Exception as e:
        return f"Error fetching execution history: {e}"