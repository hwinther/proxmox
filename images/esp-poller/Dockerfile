# syntax=docker/dockerfile:1
#
# Polls DIY ESP devices over HTTP, republishes to MQTT (HA Discovery) and exposes /metrics.
# See clusters/production/apps/esp-poller-production/ for the deployment.
#
# Runtime is distroless Python: Debian's python3.13 with no shell, apt, util-linux, perl, tar or
# ncurses. Those userland packages were almost every Grype finding on the old python:3.13-slim
# image, all "won't fix" in Debian and none used by the poller.
#
# Updates: Dependabot bumps both digests; .github/workflows/build-esp-poller.yml rebuilds on merge.
# The builder must stay on the same Python minor as the runtime (3.13), because the wheels
# pip resolves (PyYAML has a compiled one) are cp313-specific.

FROM python:3.13-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90 AS builder
ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY requirements.txt .
# --target gives a plain directory that the runtime picks up through PYTHONPATH; distroless's
# python3.13 doesn't look in /usr/local/lib/python3.13/site-packages.
RUN pip install --target=/deps --only-binary=:all: -r requirements.txt

FROM gcr.io/distroless/python3-debian13:nonroot@sha256:c3ed2b61f3c4e410685565ceb3c818197b552832521b39d53eca5d2d9d0dc1e1 AS final
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/deps

COPY --from=builder /deps /app/deps
COPY poller.py /app/poller.py

# Non-root uid/gid baked in so the deployment can drop:[ALL] capabilities. Distroless has no
# useradd; Python doesn't need a passwd entry for the uid.
USER 1888:1888
WORKDIR /app
EXPOSE 9100
ENTRYPOINT ["/usr/bin/python3.13", "/app/poller.py"]
