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
# Updates: Dependabot bumps both digests; .github/workflows/build-esp-poller.yml builds and scans the
# PR, and an esp-poller-v* tag publishes the image.
# The free tier only publishes `latest`, so the Python minor can move with a digest bump. The
# builder is `latest-dev` (same Python plus pip and a shell), and the two images have to be bumped
# together so the packages pip installs match the runtime's Python.

FROM cgr.dev/chainguard/python:latest-dev@sha256:c047e6d1e47b09144a771bfde6595a00c49dc8571caa7dd62df88634e84304ae AS builder
ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# The -dev image runs as nonroot (65532); root is only needed to write /deps.
USER root
WORKDIR /build
COPY requirements.txt .
# --target gives a plain directory that the runtime picks up through PYTHONPATH. Not
# --only-binary: `latest` can be a Python that PyYAML has no wheel for yet (3.15 at the switch),
# and its sdist then builds the pure-Python fallback, fine for reading devices.yaml once.
RUN pip install --target=/deps --prefer-binary -r requirements.txt

FROM cgr.dev/chainguard/python:latest@sha256:f6e5c2e056393d48fa8afa1ea58a1394db4cd5de1a8f0f48105c8e88fcd4f9d3 AS final
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
