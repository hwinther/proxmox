FROM debian:bookworm AS base
LABEL maintainer="Hans Christian Winther-Sørensen <docker@wsh.no>"
ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-x", "-o", "pipefail", "-c"]
RUN apt-get update && \
    apt-get -y full-upgrade

FROM base AS runtime
RUN apt-get -y install curl gettext-base nano net-tools procps socat wget xz-utils && \
    apt-get clean
ENV S6_OVERLAY_VERSION="3.2.0.2"
ARG ARCH="x86_64"
ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz /tmp
ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${ARCH}.tar.xz /tmp
RUN tar -C / -Jxpf /tmp/s6-overlay-noarch.tar.xz && \
    tar -C / -Jxpf /tmp/s6-overlay-${ARCH}.tar.xz && \
    rm -f /tmp/*.tar.xz

FROM runtime AS install-flightradar24
ARG FR24FEED_VERSION="1.0.48-0"
RUN mkdir /tmp/fr24feed && \
    if [ "$ARCH" = "x86_64" ]; then \
    wget -O /tmp/fr24feed/fr24feed.tgz https://repo-feed.flightradar24.com/linux_binaries/fr24feed_${FR24FEED_VERSION}_amd64.tgz && \
    cd /tmp/fr24feed && \
    tar -zxvf fr24feed.tgz && \
    rm -f fr24feed.tgz && \
    mv fr24feed_amd64 /opt/fr24feed; \
    elif [ "$ARCH" = "aarch64" ]; then \
    wget -O /tmp/fr24feed/fr24feed.tgz https://repo-feed.flightradar24.com/rpi_binaries/fr24feed_${FR24FEED_VERSION}_armhf.tgz && \
    cd /tmp/fr24feed && \
    tar -zxvf fr24feed.tgz && \
    rm -f fr24feed.tgz && \
    mv fr24feed_armhf /opt/fr24feed; \
    else \
    echo "Unsupported architecture: $ARCH" && exit 1; \
    fi && \
    /opt/fr24feed/fr24feed --version

FROM install-flightradar24 AS final
COPY --chmod=755 start-fr24feed.sh /srv/start-fr24feed.sh

ENV RECEIVER_TYPE="avr-tcp"
ENV RECEIVER_HOST="dump1090-fa"
ENV RECEIVER_PORT="30002"

HEALTHCHECK --start-period=10s --interval=30s --timeout=5s --retries=3 CMD ["bash", "-c", "fr24feed-status | grep 'FR24 Link: connected' || exit 1"]
ENTRYPOINT [ "/init" ]
CMD [ "/srv/start-fr24feed.sh" ]