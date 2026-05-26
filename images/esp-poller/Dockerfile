# syntax=docker/dockerfile:1
#
# Polls DIY ESP devices over HTTP, republishes to MQTT (HA Discovery) and exposes /metrics.
# See clusters/production/apps/esp-poller-production/ for the deployment.

FROM python:3.13-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

FROM python:3.13-slim AS final
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Non-root uid/gid baked in so the deployment can drop:[ALL] capabilities.
RUN groupadd --gid 1888 esppoller \
 && useradd  --uid 1888 --gid 1888 --no-create-home --shell /usr/sbin/nologin esppoller

COPY --from=builder /install /usr/local
COPY poller.py /app/poller.py

USER 1888:1888
WORKDIR /app
EXPOSE 9100
ENTRYPOINT ["python", "/app/poller.py"]
