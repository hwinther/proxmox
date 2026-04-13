# syntax=docker/dockerfile:1
# Build proxmox-backup-client from source (official read-only mirror):
# https://github.com/proxmox/proxmox-backup
#
# Upstream expects Debian-packaged Rust crates via .cargo/config (see README). For Docker we
# remove .cargo so dependencies resolve from crates.io instead.
#
# Pin PBS_GITREF to a tag from the mirror (tags lag git.proxmox.com occasionally).
# Bump when you need a newer client protocol / fixes.

ARG PBS_GITREF=v3.2.2

FROM debian:trixie-slim AS builder
ARG PBS_GITREF
ENV DEBIAN_FRONTEND=noninteractive

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        clang \
        cmake \
        curl \
        git \
        libacl1-dev \
        libclang-dev \
        libfuse3-dev \
        libssl-dev \
        libsystemd-dev \
        libudev-dev \
        pkg-config \
        uuid-dev; \
    rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /build
RUN git clone --depth 1 --branch "${PBS_GITREF}" https://github.com/proxmox/proxmox-backup.git .
# Use crates.io (not /usr/share/cargo/registry); see upstream README "Local cargo config".
RUN rm -rf .cargo

RUN cargo build -p proxmox-backup-client --release

FROM debian:trixie-slim
ENV DEBIAN_FRONTEND=noninteractive

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        libacl1 \
        libfuse3-3 \
        libssl3t64 \
        libsystemd0 \
        libudev1 \
        libuuid1 \
        libzstd1; \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/target/release/proxmox-backup-client /usr/bin/proxmox-backup-client

ENTRYPOINT ["/usr/bin/proxmox-backup-client"]
CMD []
