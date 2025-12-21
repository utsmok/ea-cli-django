# ---- Builder Stage ----
FROM python:3.13-slim as builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install system dependencies required for building some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create a virtual environment
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy the project's dependency files and install them
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# ---- Runtime Stage ----
FROM python:3.13-slim as runtime

# Install system dependencies required for the runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy the application code
COPY . .

# Make the entrypoint script executable
RUN chmod +x /app/docker/entrypoint.sh

# Run the entrypoint script
ENTRYPOINT ["/app/docker/entrypoint.sh"]
