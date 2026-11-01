# Lia — chat de atendimento da Empório da Música (Chainlit na porta 8000).
FROM python:3.13-slim

# Same uv minor as the lockfile was produced with; the binary is copied, not installed.
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first (cached layer), then the project itself.
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

COPY data ./data
COPY .chainlit/config.toml ./.chainlit/config.toml
COPY chainlit.md docker-entrypoint.sh ./

# Paths are explicit: the defaults in emporio.db assume a source checkout.
# The database lives in its own directory (a named volume), never on top of
# the CSVs in /app/data. litellm uses its bundled model cost map instead of
# downloading it at startup.
ENV PATH=/app/.venv/bin:$PATH \
    DATA_DIR=/app/data \
    DB_PATH=/app/var/emporio.db \
    LOG_PATH=/app/logs/audit.jsonl \
    LITELLM_LOCAL_MODEL_COST_MAP=True

# Unprivileged user. Chainlit creates and removes /app/.files and copies its
# translations into /app/.chainlit at runtime, so it owns those directories and
# /app itself (not recursively: code, data and the venv stay root-owned).
# Accepted trade-off: owning /app lets `lia` rename or add top-level entries
# there (contents of src/ and data/ remain read-only); without it Chainlit
# fails with PermissionError when it removes /app/.files on shutdown.
RUN useradd --create-home --uid 10001 lia \
    && mkdir -p /app/var /app/logs /app/.chainlit/translations \
    && chown lia:lia /app \
    && chown -R lia:lia /app/var /app/logs /app/.chainlit \
    && chmod +x /app/docker-entrypoint.sh
USER lia

EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["chainlit", "run", "src/emporio/chat.py", "--host", "0.0.0.0", "--port", "8000", "--headless"]
