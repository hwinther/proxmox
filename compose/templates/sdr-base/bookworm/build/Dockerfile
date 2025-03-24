FROM debian:bookworm AS base
LABEL maintainer="Hans Christian Winther-Sørensen <docker@wsh.no>"
ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-x", "-o", "pipefail", "-c"]
RUN apt-get update && \
    apt-get -y full-upgrade

FROM base AS install-build-deps
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