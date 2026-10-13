# openHop SpamGuard in a container, for openHop installs that run in Docker (or on Unraid).
# SpamGuard talks to openHop only through openHop's web API, so it needs no access to openHop's files.
ARG BASE=python:3.12-slim
FROM ${BASE}

# The two libraries SpamGuard needs. Some platforms (32-bit Pi) have no ready-made builds, so a
# compiler is installed just for this step and removed again.
RUN set -e; \
    if ! python3 -c "import yaml, sys, importlib.util as u; sys.exit(0 if u.find_spec('Crypto') or u.find_spec('Cryptodome') else 1)" 2>/dev/null; then \
      if ! pip install --no-cache-dir --only-binary=:all: pycryptodome==3.21.0 pyyaml==6.0.2 2>/dev/null; then \
        apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev; \
        pip install --no-cache-dir pycryptodome==3.21.0 pyyaml==6.0.2; \
        apt-get purge -y gcc libc6-dev && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*; \
      fi; \
    fi; \
    useradd --system --uid 1000 --home /data spamguard; \
    mkdir -p /app /data && chown spamguard /data

COPY spamguard.py ui.html replay.py docker-entrypoint.sh /app/

ENV SPAMGUARD_DOCKER=1 \
    SPAMGUARD_DATA=/data \
    PYTHONUNBUFFERED=1

WORKDIR /app
VOLUME /data
EXPOSE 8091

HEALTHCHECK --interval=60s --timeout=10s --start-period=60s --retries=3 \
  CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8091/health', timeout=8).status == 200 else 1)"

LABEL org.opencontainers.image.source="https://github.com/flackrat/openhop-spamguard" \
      org.opencontainers.image.description="Spam protection for openHop MeshCore repeaters" \
      org.opencontainers.image.licenses="MIT"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python3", "spamguard.py", "--config", "/data/config.yaml"]
