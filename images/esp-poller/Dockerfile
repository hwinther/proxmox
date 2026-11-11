# syntax=docker/dockerfile:1
#
# Polls DIY ESP devices over HTTP, republishes to MQTT (HA Discovery) and exposes /metrics.
# See clusters/production/apps/esp-poller-production/ for the deployment.
#
# Runtime is Chainguard's Wolfi-based python: no shell or package manager, rebuilt daily on the
# current upstream CPython. Both Debian-based options carried long lists of "won't fix" CVEs:
# python:3.13-slim in unused userland (util-linux, perl, tar, ncurses), and distroless python in
# Debian's older python3.13 and krb5.
#
# Updates: Dependabot bumps both digests; .github/workflows/build-esp-poller.yml rebuilds on merge.
# The free tier only publishes `latest`, so the Python minor can move with a digest bump. The
# builder is `latest-dev` (same Python plus pip and a shell), and the two images have to be bumped
# together so the wheels pip resolves (PyYAML has a compiled one) match the runtime's Python.

FROM cgr.dev/chainguard/python:latest-dev@sha256:9f76d277ca81d3079eb3be24c742de3b6598f032fc9943fed6951ff99e581d02 AS builder
ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# The -dev image runs as nonroot (65532); root is only needed to write /deps.
USER root
WORKDIR /build
COPY requirements.txt .
# --target gives a plain directory that the runtime picks up through PYTHONPATH.
RUN pip install --target=/deps --only-binary=:all: -r requirements.txt

FROM cgr.dev/chainguard/python:latest@sha256:e5322b9d32064a645225b8b2419f11127bcf2d8b9927f9514f0acee1e1d25751 AS final
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/deps

COPY --from=builder /deps /app/deps
COPY poller.py /app/poller.py

# Non-root uid/gid baked in so the deployment can drop:[ALL] capabilities. The image has no
# useradd; Python doesn't need a passwd entry for the uid.
USER 1888:1888
WORKDIR /app
EXPOSE 9100
ENTRYPOINT ["/usr/bin/python", "/app/poller.py"]
