# ---- Stage 1: build dependencies into a virtualenv ----
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN python -m venv /venv \
    && /venv/bin/pip install --no-cache-dir --upgrade pip \
    && /venv/bin/pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: slim runtime image ----
FROM python:3.12-slim

# Run as a non-root user (good practice; also required by many K8s policies)
RUN useradd --create-home appuser
USER appuser
WORKDIR /home/appuser

COPY --from=builder /venv /venv
COPY app/ app/

ENV PATH="/venv/bin:$PATH" \
    DEVLOG_DB="/home/appuser/data/devlog.db"

RUN mkdir -p /home/appuser/data

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
