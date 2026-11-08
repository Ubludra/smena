# =============================================================================
# Smena API — Python 3.12 (slim), runs as a non-root user
# =============================================================================
# Two final targets share the same base:
#
#   runtime — production image: runtime dependencies only, no pytest/ruff/mypy
#             (compose.prod.yml selects `target: runtime`).
#   dev     — default target: adds the [dev] extras so `make test/lint/mypy`
#             keep running inside the same container (Docker-first workflow).
#
# Selecting `dev` (no --target) preserves every existing compose/Make behavior.
# =============================================================================
FROM docker.io/library/python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Unprivileged runtime user (product requirement: no root in final image).
RUN useradd --create-home --uid 10001 smena

# Upload directory with correct ownership up front: an empty named volume is
# initialized from image content, so the volume mount inherits this owner.
RUN mkdir -p /data/uploads && chown -R smena:smena /data

WORKDIR /app

# Install the package (runtime deps only) before copying volatile files.
COPY pyproject.toml ./
COPY src ./src
RUN pip install .

# Migration framework and startup.
COPY alembic.ini ./
COPY alembic ./alembic
COPY entrypoint.sh healthcheck.py ./
RUN chmod +x entrypoint.sh && chown -R smena:smena /app

USER smena

EXPOSE 8000

# CMD (not ENTRYPOINT) so `docker compose run api <cmd>` can override it
# for one-off commands without bypassing anything.
CMD ["./entrypoint.sh"]

# --- Development image (default target) --------------------------------------
# Same layers plus test/lint/type tooling; used by compose.yaml and the
# Makefile's `make test/lint/mypy` without any extra flags.
FROM runtime AS dev

USER root
COPY pyproject.toml ./
RUN pip install ".[dev]"
USER smena
