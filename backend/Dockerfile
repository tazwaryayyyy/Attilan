# Pinned builder stage: native wheels never enter the runtime image.
FROM python:3.12.8-alpine3.20 AS builder

WORKDIR /build
RUN apk add --no-cache gcc musl-dev libffi-dev openssl-dev cargo
COPY backend/requirements.txt ./requirements.txt
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip==24.3.1 \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Pinned, non-root production stage. No compiler, package manager cache, shell
# entrypoint, or autoreload command is present in the running service.
FROM python:3.12.8-alpine3.20 AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
RUN addgroup -S -g 10001 attilan \
    && adduser -S -D -H -u 10001 -G attilan attilan
COPY --from=builder /opt/venv /opt/venv
COPY --chown=10001:10001 backend ./backend

USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers"]
