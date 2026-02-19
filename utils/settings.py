import os
from pathlib import Path
from dotenv import load_dotenv

from utils.helpers.read_json import load_system_prompts

load_dotenv()

DB_USER = os.getenv("DB_USER", "")
DB_PWD = os.getenv("DB_PWD", "")
DB_HOST = os.getenv("DB_HOST", "")
DB_DB_NAME = os.getenv("DB_DB_NAME", "")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DATABASE_URL = os.getenv("DATABASE_URL")

# LangSmith Configuration
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "lang-chain-mc")
LANGCHAIN_ENDPOINT = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")

# Set environment variables for LangSmith if tracing is enabled
if LANGCHAIN_TRACING_V2 and LANGCHAIN_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = LANGCHAIN_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = LANGCHAIN_PROJECT
    os.environ["LANGCHAIN_ENDPOINT"] = LANGCHAIN_ENDPOINT

# Load prompts at module import
SYSTEM_PROMPTS = load_system_prompts()

# Sandbox Configuration
SANDBOX_TIMEOUT = int(os.getenv("SANDBOX_TIMEOUT", "30"))
SANDBOX_MAX_OUTPUT = int(os.getenv("SANDBOX_MAX_OUTPUT", "5000"))
SANDBOX_MEMORY_LIMIT = os.getenv("SANDBOX_MEMORY_LIMIT", "512m")
SANDBOX_CPU_QUOTA = int(os.getenv("SANDBOX_CPU_QUOTA", "50000"))  # 50% CPU
SANDBOX_NETWORK_DISABLED = os.getenv("SANDBOX_NETWORK_DISABLED", "true").lower() == "true"

# Workspace
WORKSPACE_DIR = Path(__file__).parent.parent / "workspace"
WORKSPACE_DIR.mkdir(exist_ok=True)
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
