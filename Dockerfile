# syntax=docker/dockerfile:1.7

# ── Stage 1: builder ──────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /build

RUN python -m venv /opt/venv

COPY requirements.txt .

RUN /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


# ── Stage 2: runtime ─────────────────────────
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="FIT4110 Lab05 – Access Gate Service"
LABEL org.opencontainers.image.version="0.5.0"
LABEL org.opencontainers.image.description="team-gate Docker image for FIT4110 Lab 05"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH=/app/src
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8000
ENV AUTH_TOKEN=local-dev-token
ENV SERVICE_NAME=access-gate
ENV SERVICE_VERSION=0.5.0
ENV AI_SERVICE_URL=http://ai-service:9000
ENV POSTGRES_HOST=db
ENV POSTGRES_PORT=5432
ENV POSTGRES_USER=lab05
ENV POSTGRES_PASSWORD=lab05pass
ENV POSTGRES_DB=gatedb

WORKDIR /app

# Non-root user
RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup --home /app appuser

COPY --from=builder /opt/venv /opt/venv
COPY src/ ./src/

RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).read()" || exit 1

CMD ["/opt/venv/bin/uvicorn", "gate_app.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]