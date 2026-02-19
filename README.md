# lang-chain-mc
LangChain Agentic System, minimal but complete agentic system using Langchain 

## 🔒 Security Features

This project uses **Docker-based sandboxing** for code execution:

- ✅ Network isolation (no internet access)
- ✅ Memory limits (512MB)
- ✅ CPU limits (50%)
- ✅ Non-root user execution
- ✅ No access to project files or .env
- ✅ Timeout protection (30s)

## 🚀 Setup

### Prerequisites

- Python 3.12+
- Docker
- Docker daemon running

### Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Build the sandbox Docker image:
   ```bash
   docker build -f Dockerfile.sandbox -t python-sandbox:latest .
   ```

4. Configure environment variables in `.env`

5. Run the application:
   ```bash
   python main.py
   ```

## 🐳 Docker Sandbox

The code execution tool runs Python code in isolated Docker containers with:

- **Memory limit:** 512MB (configurable via `SANDBOX_MEMORY_LIMIT`)
- **CPU limit:** 50% (configurable via `SANDBOX_CPU_QUOTA`)
- **Timeout:** 30 seconds (configurable via `SANDBOX_TIMEOUT`)
- **Network:** Disabled by default (configurable via `SANDBOX_NETWORK_DISABLED`)

### Manual Docker Image Build 
