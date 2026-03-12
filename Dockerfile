# Stage 1: Builder — compile Python wheels
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip wheel --no-cache-dir --wheel-dir /build/wheels -r requirements.txt


# Stage 2: Runtime — minimal production image
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.source="https://github.com/benashkar/medicaid-provider-spending"
LABEL org.opencontainers.image.description="Medicaid Provider Spending Dashboard"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/wheels /tmp/wheels
RUN python -m pip install --no-cache-dir /tmp/wheels/* \
    && rm -rf /tmp/wheels

COPY app/ ./app/
COPY db/ ./db/

RUN groupadd --system appuser \
    && useradd --system --gid appuser --no-create-home appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:10000/health || exit 1

CMD ["gunicorn", "app:create_app()", "--bind", "0.0.0.0:10000", "--workers", "2"]
