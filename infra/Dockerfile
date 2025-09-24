FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install uv (PEP 723/pyproject resolver)
RUN pip install --no-cache-dir uv

# Leverage layer caching: copy only lock/manifest first
COPY pyproject.toml uv.lock ./

# Install dependencies (frozen to lock)
RUN uv sync --frozen

# Copy application
COPY app ./app

# Static assets directory inside container
ENV STATIC_DIR=/app/app/static

# Non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Start API server
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
