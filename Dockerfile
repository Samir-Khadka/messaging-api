# Messaging API — production image for ShipIt (k8s/services/messaging).
#
# Build:  docker build -t ghcr.io/samir-khadka/messaging-api:<sha> .
# Run:    docker run -p 8000:8000 \
#           -e DEV_MODE=false \
#           -e DATABASE_PATH=/data/messaging.db \
#           -e MESSAGING_API_KEYS='<key>' \
#           -e OTP_PEPPER='<pepper>' \
#           ghcr.io/samir-khadka/messaging-api:<sha>
# NOTE: SQLite lives at /data; that directory is ephemeral unless a volume
# is mounted. Kubernetes manifest mounts an emptyDir there and documents
# the limitation (production needs Postgres — see ShipIt onboarding doc).

# ---- builder: install deps into /install ----
# Base: python:3.12.16-slim-bookworm (pinned 2026-11-03 for reproducible
# builds; matches suraksha's proven-green image).
FROM python:3.12.16-slim-bookworm AS builder
WORKDIR /app
COPY requirements.txt .
# Upgrade the installer first so the install uses the latest resolver.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- runtime: non-root, minimal ----
FROM python:3.12.16-slim-bookworm AS runtime
# Patch OS packages for the Trivy gate (Debian security updates), upgrade
# pip, create the non-root user and prepare /data (SQLite home, owned by
# appuser) for the case where no volume is mounted.
RUN useradd --create-home --uid 10001 appuser \
    && apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip \
    && mkdir -p /data && chown appuser:appuser /data
# Remove CPython's ensurepip bundled wheels (defense in depth): the stdlib
# can ship setuptools/wheel there; they are never installed or imported at
# container runtime (venv/ensurepip are unused). See .trivyignore for the
# CVE-2025-47273 false-positive analysis.
RUN rm -rf /usr/local/lib/python*/ensurepip/_bundled
WORKDIR /app
COPY --from=builder /install /usr/local
COPY app/ ./app/
USER appuser
EXPOSE 8000
ENV DATABASE_PATH=/data/messaging.db
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
