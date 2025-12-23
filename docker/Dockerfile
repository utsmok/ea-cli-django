# ---- Builder Stage ----
# Installs uv and builds dependencies
FROM python:3.13-slim-bookworm AS builder

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Configure uv for production
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_SYSTEM_PYTHON=1

WORKDIR /app

# Copy dependency files first for better caching
# These change less frequently than source code
COPY pyproject.toml uv.lock ./

# Install ONLY dependencies (not project itself yet)
# Uses BuildKit cache mounts for faster rebuilds
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copy source code AFTER dependencies
# This ensures dependency layer is cached unless deps change
COPY src/ ./src/

# Now install the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---- Runtime Stage ----
# Minimal image with only runtime dependencies
FROM python:3.13-slim-bookworm AS runtime

# Set Python environment
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install only runtime system dependencies
# Combine apt commands to reduce layers
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy source code (smaller than copying everything)
COPY --from=builder /app/src /app/src

# Copy entrypoint and make executable
COPY --from=builder /app/docker /app/docker
RUN chmod +x /app/docker/entrypoint.sh

# Create non-root user for running the application
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import django; django.setup()" || exit 1

ENTRYPOINT ["/app/docker/entrypoint.sh"]
