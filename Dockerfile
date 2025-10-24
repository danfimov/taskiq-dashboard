FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.12 \
    UV_PROJECT_ENVIRONMENT="/app/.venv"

# Install dependencies
COPY ./pyproject.toml ./uv.lock ./
RUN uv sync --no-dev --locked --no-install-project

FROM python:3.12-slim

ENV PATH="/app/.venv/bin:$PATH"

COPY --from=builder --chown=app:app /app/.venv /app/.venv

COPY . /app

WORKDIR /app

EXPOSE 8000

ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["docker/start.sh"]
