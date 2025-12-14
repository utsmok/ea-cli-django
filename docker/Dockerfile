FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl git netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV UV_PROJECT_ENVIRONMENT="/opt/venv"
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

COPY pyproject.toml ./
RUN uv sync --all-groups

COPY . .
RUN mkdir -p media documents/downloads documents/processed logs static_files \
    && chmod +x /app/docker/entrypoint.sh

ENTRYPOINT ["/app/docker/entrypoint.sh"]
