from fastapi import FastAPI
from dotenv import load_dotenv

from database.db import init_db
from routers import chat, file_agents
import uvicorn
import logging
from contextlib import asynccontextmanager
from utils.settings import LANGCHAIN_TRACING_V2, LANGCHAIN_PROJECT

# Load environment variables first
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting LangChain Agent API")
    if LANGCHAIN_TRACING_V2:
        logger.info(f"LangSmith Tracing: Enabled")
        logger.info(f"LangSmith Project: {LANGCHAIN_PROJECT}")
        logger.info(f"View traces at: https://smith.langchain.com/o/default/projects/p/{LANGCHAIN_PROJECT}")
    else:
        logger.warning("LangSmith Tracing: Disabled")

    yield

    # Shutdown
    logger.info("Shutting down LangChain Agent API")

app = FastAPI(
    title="LangChain Agent API",
    description="FastAPI-based Agent system with LangSmith integration",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(chat.router, prefix="/agent", tags=["Agent"])
app.include_router(file_agents.router, prefix="/file-agents", tags=["File Agents"])

@app.get("/")
def root():
    return {
        "message": "LangChain Agent System is Running 🚀",
        "langsmith_enabled": LANGCHAIN_TRACING_V2,
        "langsmith_project": LANGCHAIN_PROJECT if LANGCHAIN_TRACING_V2 else None
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "langsmith_tracing": LANGCHAIN_TRACING_V2
    }

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()
    print("🚀 Application started")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)