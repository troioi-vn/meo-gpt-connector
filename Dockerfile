# ---- builder ----
FROM python:3.12-slim AS builder

RUN pip install uv

WORKDIR /app

COPY pyproject.toml ./
# Install production deps into /app/.venv
RUN uv venv .venv && \
    uv pip install --python .venv/bin/python \
    fastapi "uvicorn[standard]" pydantic "pydantic-settings" httpx \
    "python-jose[cryptography]" cryptography "redis[hiredis]" structlog \
    python-multipart

# ---- final ----
FROM python:3.12-slim AS final

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY pyproject.toml ./
COPY src/ ./src/

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
