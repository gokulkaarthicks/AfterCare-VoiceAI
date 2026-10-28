FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
RUN uv pip install --system -e "."

COPY app/ app/
COPY scripts/ scripts/
COPY alembic.ini .

ARG SERVICE_MODULE=app.api.db:app
ARG SERVICE_PORT=8000

ENV SERVICE_MODULE=${SERVICE_MODULE}
ENV SERVICE_PORT=${SERVICE_PORT}

EXPOSE ${SERVICE_PORT}

CMD uvicorn ${SERVICE_MODULE} --host 0.0.0.0 --port ${SERVICE_PORT}
