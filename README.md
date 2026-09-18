README.md

Markdown
# GridWise Energy Optimizer

An intelligent, production-ready grid energy optimization pipeline that converts natural language operator notes and hourly demand forecasts into a cost-optimal 24-hour battery schedule using Linear Programming (LP).

## System Architecture

[ Natural Language / Raw Input ]
│
▼
[ LLM Interpreter Layer ]     ──► Converts unstructured operator notes into schema directives
│
▼
[ Guardrail Safety Layer ]    ──► Sanitizes boundaries, overrides, and array constraints
│
▼
[ SciPy HighS MILP Core ]    ──► Formulates LP matrices & computes optimal schedule
│
▼
[ Verified Plan Output ]    ──► Returns BDT cost breakdown, hourly plan & peak usage


## Core Components

| Module | Primary Responsibility |
| :--- | :--- |
| `main.py` | FastAPI application serving `/health`, `/optimize-energy`, and `/optimize-text`. |
| `models.py` | Strictly typed Pydantic v2 schemas for request validation and structured output. |
| `optimizer.py` | SciPy HighS linear solver enforcing battery capacity, C-rates, and reserve overrides. |
| `guardrails.py` | Deterministic validation layer filtering halluncinated or invalid LLM output directives. |
| `llm_interpreter.py` | Dual-mode parser supporting `openai`, `anthropic`, and zero-dependency `mock` modes. |
| `test_optimizer.py` | Full test suite covering LP mathematical precision, guardrails, and API endpoints. |

## Quick Start

### 1. Local Setup

# Install dependencies
pip install -r requirements.txt

# Launch FastAPI server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
2. Docker Deployment

# Build and containerize
docker build -t gridwise-optimizer .
docker run -p 8000:8000 gridwise-optimizer
Environment Variables
Configure LLM_PROVIDER in your environment to change processing backends:

# Default (No API key needed for testing)
export LLM_PROVIDER="mock"

# Production Providers
export LLM_PROVIDER="openai"
export LLM_API_KEY="sk-..."

# or
export LLM_PROVIDER="anthropic"
export LLM_API_KEY="sk-ant-..."
Running the Test Suite
Run the full integration and unit test suite via pytest:

pytest test_optimizer.py -v
Sample Curl Request (/optimize-text)

curl -X POST "http://localhost:8000/optimize-text" \
     -H "Content-Type: text/plain" \
     -d "Battery capacity 100kWh sitting at 50kWh. Do not discharge between 5 PM and 8 PM."