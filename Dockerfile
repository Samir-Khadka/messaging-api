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
FROM python:3.11.18-slim AS builder
WORKDIR /app
COPY requirements.txt .
# Upgrade the installer first: the base image's bundled pip/wheel carry HIGH
# CVEs (Trivy gate), and the install should use the latest resolver.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- runtime: non-root, minimal ----
FROM python:3.11.18-slim AS runtime
# Patch OS packages for the Trivy gate (Debian security updates), upgrade
# pip, create the non-root user and prepare /data (SQLite home, owned by
# appuser) for the case where no volume is mounted.
RUN useradd --create-home --uid 10001 appuser \
    && apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip \
    && mkdir -p /data && chown appuser:appuser /data
WORKDIR /app
COPY --from=builder /install /usr/local
COPY app/ ./app/
# Purge stale Python-toolchain dist-infos AFTER the builder copy, then
# install pinned-fixed versions. Root cause (2026-11-03): the base image
# carries leftover setuptools/wheel/jaraco.context .dist-info dirs that pip
# reports as "already satisfied" (it reads only the newest dist-info) while
# Trivy still flags the stale ones as HIGH CVEs (CVE-2025-47273,
# CVE-2026-24049, CVE-2026-23949). An upgrade-in-place leaves the stale
# dist-infos behind, so removing every copy first is the only reliable fix.
RUN SP=$(python -c "import site; print(site.getsitepackages()[0])") \
    && rm -rf "$SP"/setuptools* "$SP"/wheel* "$SP"/jaraco* "$SP"/backports* \
    && pip install --no-cache-dir "setuptools>=78.1.1" "wheel>=0.46.2" "jaraco.context>=6.1.0"
USER appuser
EXPOSE 8000
ENV DATABASE_PATH=/data/messaging.db
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
