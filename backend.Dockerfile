FROM ghcr.io/astral-sh/uv:0.9.1 AS uv
FROM python:3.12.13-slim-bookworm

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

# Install the exact resolver output used by local and CI environments.
COPY requirements.lock .
RUN uv pip install --system --require-hashes -r requirements.lock

# Copy source code
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Run Uvicorn (bind to PORT environment variable for cloud platforms like Render/Cloud Run)
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
