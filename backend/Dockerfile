# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# libpq-dev + gcc are needed to build asyncpg/pgvector's C extensions.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies BEFORE copying real app code, as an editable install. This is the layer-
# ordering fix: previously `COPY app ./app` came before `pip install`, so editing ANY app file
# invalidated the pip-install layer too, forcing a full re-download of every dependency
# (pandas, numpy, ...) on every single rebuild even though the dependency list hadn't changed.
# An empty stub package is enough for `pip install -e .` to succeed and resolve dependencies;
# the real code copied in below is what actually gets imported at runtime (editable installs
# read from disk at import time, not from a frozen snapshot).
COPY pyproject.toml README.md ./
RUN mkdir -p app && touch app/__init__.py

# --default-timeout/--retries: PyPI's index can be slow to respond under network congestion --
# pip's default 15s timeout misreports that as a "ResolutionImpossible" dependency conflict
# instead of a clear network error, which is confusing to debug. Widen both.
# --mount=type=cache: persists pip's own download cache across builds on this machine even when
# this layer itself has to rebuild (e.g. pyproject.toml changes) -- a second, independent layer
# of caching on top of the layer-ordering fix above.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --default-timeout=100 --retries 10 -e .

# Only NOW copy the real code -- this layer (and only this one) is what invalidates on every
# code edit, and it doesn't force dependencies to reinstall.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
