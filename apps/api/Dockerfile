FROM docker.io/library/python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --create-home --uid 10001 smena

RUN mkdir -p /data/uploads && chown -R smena:smena /data

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install .

COPY alembic.ini ./
COPY alembic ./alembic
COPY entrypoint.sh healthcheck.py ./
RUN chmod +x entrypoint.sh && chown -R smena:smena /app

USER smena

EXPOSE 8000

CMD ["./entrypoint.sh"]

FROM runtime AS dev

USER root
COPY pyproject.toml ./
RUN pip install ".[dev]"
USER smena
