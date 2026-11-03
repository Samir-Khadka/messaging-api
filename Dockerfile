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
# Base: python:3.12.16-slim-bookworm (2026-11-03) — the 3.11.18-slim base
# carries a phantom setuptools 70.3.0 reference that Trivy flags as HIGH
# (CVE-2025-47273) even after the dist-infos are purged and setuptools
# 84.x is installed; the 3.12 base scans clean (proven by suraksha).
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
# Remove CPython's ensurepip bundled wheels: the stdlib ships a setuptools
# wheel there that Trivy flags as HIGH (CVE-2025-47273) even though it is
# never installed or imported (no setuptools dist-info exists in
# site-packages). venv/ensurepip are not used at container runtime.
RUN rm -rf /usr/local/lib/python*/ensurepip/_bundled
WORKDIR /app
COPY --from=builder /install /usr/local
COPY app/ ./app/
USER appuser
EXPOSE 8000
ENV DATABASE_PATH=/data/messaging.db
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
# diag-trigger
