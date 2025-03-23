FROM debian:bullseye AS base
LABEL maintainer="Hans Christian Winther-Sørensen <docker@wsh.no>"
ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-x", "-o", "pipefail", "-c"]
RUN apt-get update && \
    apt-get -y full-upgrade

FROM base AS runtime
ARG TARGETPLATFORM
ARG TARGETARCH
ARG TARGETVARIANT
RUN echo ${TARGETPLATFORM} > /srv/target.platform && \
    echo ${TARGETARCH} > /srv/target.arch && \
    echo ${TARGETVARIANT} > /srv/target.variant && \
    apt-get -y install curl gettext-base nano net-tools procps socat wget xz-utils && \
    apt-get clean
ENV S6_OVERLAY_VERSION="3.2.0.2"
ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz /tmp
RUN case "${TARGETARCH}" in \
    amd64) ARCH="x86_64" ;; \
    arm64) ARCH="aarch64" ;; \
    *) echo "Unsupported TARGETARCH: $TARGETARCH" && exit 1 ;; \
    esac && \
    wget -q https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${ARCH}.tar.xz -O /tmp/s6-overlay-${ARCH}.tar.xz && \
    tar -C / -Jxpf /tmp/s6-overlay-noarch.tar.xz && \
    tar -C / -Jxpf /tmp/s6-overlay-${ARCH}.tar.xz && \
    rm -f /tmp/*.tar.xz

FROM runtime AS install-build-deps
RUN apt-get -y install \
    autoconf \
    build-essential \
    cmake \
    debhelper \
    devscripts \
    fakeroot \
    git \
    libbladerf-dev \
    libboost-filesystem-dev \
    libboost-program-options-dev \
    libboost-regex-dev \
    libboost-system-dev \
    libhackrf-dev \
    liblimesuite-dev \
    libncurses5-dev \
    librtlsdr-dev \
    libusb-dev \
    libz-dev \
    openssl \
    patchelf \
    pkg-config \
    python3-build \
    python3-dev \
    python3-pip \
    python3-setuptools \
    python3-venv \
    python3-wheel \
    tcl8.6-dev && \
    apt-get clean

FROM install-build-deps AS build-rtl-sdr
WORKDIR /src
RUN git clone https://github.com/osmocom/rtl-sdr.git
WORKDIR /src/rtl-sdr
RUN mkdir build && \
    cd build && \
    cmake ../ && \
    make && \
    make install && \
    ldconfig && \
    rm -rf /src/rtl-sdr

ENTRYPOINT [ "bash" ]