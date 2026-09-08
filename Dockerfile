# ==============================================================================
# PromptJoust - Autonomous LLM Tactical Arena
# Multi-stage lightweight Python 3.12 container
# ==============================================================================

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and content
COPY core/ ./core/
COPY content/ ./content/
COPY interfaces/ ./interfaces/
COPY providers/ ./providers/
COPY README.md LICENSE ./

# Create non-privileged user for container security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/bosses')" || exit 1

ENTRYPOINT ["uvicorn", "interfaces.web.server:app", "--host", "0.0.0.0", "--port", "8000"]
