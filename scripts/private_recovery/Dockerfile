# syntax=docker/dockerfile:1
# Build from the repository root, on Linux amd64. No secrets are build inputs.
FROM --platform=linux/amd64 node:22.16.0-bookworm-slim AS frontend
WORKDIR /build/frontend
RUN npm install --global yarn@1.22.22 --force --ignore-scripts --no-audit --no-fund
COPY frontend/package.json frontend/yarn.lock ./
RUN yarn install --frozen-lockfile --non-interactive
COPY frontend/ ./
ENV REACT_APP_BACKEND_URL="" PUBLIC_URL="" GENERATE_SOURCEMAP=false CI=true
RUN yarn build

FROM --platform=linux/amd64 ubuntu:24.04 AS runtime
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_CONFIG_FILE=/dev/null \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright LANG=C.UTF-8

# MongoDB's published Ubuntu 24.04 tarball prerequisites, Python, and an init.
# Browser libraries are installed by the pinned Playwright version below.
RUN apt-get update && apt-get install --yes --no-install-recommends \
      ca-certificates curl python3.12 python3.12-venv tini \
      libcurl4t64 libgssapi-krb5-2 libldap2 libwrap0 libsasl2-2 \
      libsasl2-modules libsasl2-modules-gssapi-mit openssl liblzma5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
COPY scripts/private_recovery/requirements.txt scripts/private_recovery/requirements.txt
COPY scripts/private_recovery/requirements-app.txt scripts/private_recovery/requirements-app.txt
RUN python3.12 -m venv /opt/cashout-app \
    && /opt/cashout-app/bin/python -m pip install --no-cache-dir --no-input \
      --only-binary=:all: --index-url https://pypi.org/simple \
      -r scripts/private_recovery/requirements-app.txt \
    && /opt/cashout-app/bin/python -m pip check \
    && python3.12 -m venv /opt/cashout-workflow \
    && /opt/cashout-workflow/bin/python -m pip install --no-cache-dir --no-input \
      --only-binary=:all: --index-url https://pypi.org/simple \
      -r scripts/private_recovery/requirements.txt \
    && /opt/cashout-workflow/bin/python -m pip check \
    && /opt/cashout-app/bin/python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# 8.0.39 is Atlas-only. Atlas documents restore compatibility between any
# patches of the same major/minor; the importer also verifies actual FCV 8.0.
# This is the same official binary and SHA-256 as the passing synthetic CI.
RUN curl --fail --silent --show-error --location --proto '=https' \
      --connect-timeout 15 --max-time 180 --retry 2 \
      --output /tmp/mongodb.tgz \
      https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-ubuntu2404-8.0.38.tgz \
    && printf '%s  %s\n' \
      '2885d4382bd47b96bfaf3edc7dec0ef44463e3e2a79479f584d20deb6182cda9' \
      /tmp/mongodb.tgz | sha256sum --check --status \
    && mkdir -p /opt/mongodb \
    && tar --extract --gzip --file /tmp/mongodb.tgz --directory /opt/mongodb \
      --strip-components=1 --no-same-owner --no-same-permissions \
    && rm /tmp/mongodb.tgz \
    && /opt/mongodb/bin/mongod --version

COPY backend/ backend/
COPY scripts/test_recovery_browser.py scripts/test_recovery_browser.py
COPY scripts/private_recovery/ scripts/private_recovery/
COPY --from=frontend /build/frontend/build/ frontend/build/

ARG CASHOUT_SOURCE_REVISION=unspecified
LABEL org.opencontainers.image.title="CashOutAI private recovery rehearsal" \
      org.opencontainers.image.revision=$CASHOUT_SOURCE_REVISION
ENV CASHOUT_REHEARSAL_SOURCE_REVISION=$CASHOUT_SOURCE_REVISION
RUN groupadd --gid 10001 rehearsal \
    && useradd --uid 10001 --gid rehearsal --create-home --shell /usr/sbin/nologin rehearsal \
    && chmod 0755 scripts/private_recovery/start_workflow.sh \
    && chmod -R a+rX /app /opt/playwright /opt/mongodb
USER 10001:10001
STOPSIGNAL SIGTERM
# No EXPOSE, public listener, persistent disk, cloud database URI, or API key.
# Render Dashboard also requires this explicit Docker start command:
# /app/scripts/private_recovery/start_workflow.sh
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/scripts/private_recovery/start_workflow.sh"]
