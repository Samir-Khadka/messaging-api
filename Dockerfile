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
# Patch OS packages for the Trivy gate (Debian security updates) and upgrade
# the bundled Python toolchain — python:3.11.18-slim ships wheel@0.45.1,
# jaraco.context@5.3.0 and setuptools@70.3.0 with HIGH CVEs, which Trivy
# flags in the final image. Explicit minimum pins (not bare --upgrade) so
# pip cannot consider the vulnerable versions "already satisfied"; the pip
# self-upgrade runs separately to avoid upgrade-in-one-command quirks. Then
# create the non-root user and prepare /data (SQLite home, owned by appuser)
# for the case where no volume is mounted.
RUN useradd --create-home --uid 10001 appuser \
    && apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "setuptools>=78.1.1" "wheel>=0.46.2" "jaraco.context>=6.1.0" \
    && mkdir -p /data && chown appuser:appuser /data
WORKDIR /app
COPY --from=builder /install /usr/local
COPY app/ ./app/
USER appuser
EXPOSE 8000
ENV DATABASE_PATH=/data/messaging.db
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
