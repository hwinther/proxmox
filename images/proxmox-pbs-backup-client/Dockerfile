# syntax=docker/dockerfile:1
#
# Proxmox helper crates (proxmox-auth-api, …) are NOT on crates.io; upstream expects either
# Debian’s /usr/share/cargo/registry (see .cargo/config in the tree) or their full packaging stack.
#
# - linux/amd64: official proxmox-backup-client-static from pbs-client (Trixie) — fast, small.
# - linux/arm64: Proxmox devel repo (trixie) + mk-build-deps + Debian cargo prepare-debian + cargo build.
#   First arm64 build pulls large Build-Depends (incl. docs/tooling); expect a long CI step.
#
# Source reference: https://github.com/proxmox/proxmox-backup
# Devel APT: http://download.proxmox.com/debian/devel (trixie)

ARG PBS_GITREF=v3.2.2

FROM debian:trixie-slim AS builder
ARG TARGETARCH
ARG PBS_GITREF
ENV DEBIAN_FRONTEND=noninteractive

RUN set -eux; \
    keyring=/usr/share/keyrings/proxmox-archive-keyring.gpg; \
    if [ "${TARGETARCH}" = "amd64" ]; then \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates wget; \
    wget -qO "${keyring}" https://enterprise.proxmox.com/debian/proxmox-archive-keyring-trixie.gpg; \
    printf '%s\n' \
    'Types: deb' \
    'URIs: http://download.proxmox.com/debian/pbs-client' \
    'Suites: trixie' \
    'Components: main' \
    "Signed-By: ${keyring}" \
    > /etc/apt/sources.list.d/pbs-client.sources; \
    apt-get update; \
    apt-get install -y --no-install-recommends proxmox-backup-client-static; \
    install -D /usr/bin/proxmox-backup-client /out/proxmox-backup-client; \
    apt-get purge -y wget; \
    apt-get autoremove -y; \
    elif [ "${TARGETARCH}" = "arm64" ]; then \
    apt-get update; \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    devscripts \
    equivs \
    fakeroot \
    git \
    wget; \
    wget -qO "${keyring}" https://enterprise.proxmox.com/debian/proxmox-archive-keyring-trixie.gpg; \
    printf '%s\n' \
    'Types: deb' \
    'URIs: http://download.proxmox.com/debian/devel' \
    'Suites: trixie' \
    'Components: main' \
    "Signed-By: ${keyring}" \
    > /etc/apt/sources.list.d/proxmox-devel.sources; \
    apt-get update; \
    git clone --depth 1 --branch "${PBS_GITREF}" \
    https://github.com/proxmox/proxmox-backup.git /src; \
    cd /src; \
    mk-build-deps -i -t 'apt-get -y -o Debug::pkgProblemResolver=yes --no-install-recommends' debian/control; \
    rm -rf .cargo; \
    mkdir -p debian/cargo_home debian/cargo_registry; \
    export CARGO_HOME=/src/debian/cargo_home; \
    if [ -x /usr/share/cargo/bin/cargo ]; then CARGO=/usr/share/cargo/bin/cargo; else CARGO=cargo; fi; \
    ${CARGO} --version; \
    ${CARGO} prepare-debian /src/debian/cargo_registry --link-from-system; \
    ${CARGO} build -p proxmox-backup-client --release; \
    install -D /src/target/release/proxmox-backup-client /out/proxmox-backup-client; \
    apt-get purge -y wget git; \
    apt-get autoremove -y; \
    else \
    echo "Unsupported TARGETARCH=${TARGETARCH} (only amd64 and arm64)"; \
    exit 1; \
    fi; \
    rm -rf /var/lib/apt/lists/*

FROM debian:trixie-slim
ENV DEBIAN_FRONTEND=noninteractive

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    libacl1 \
    libfuse3-4 \
    libssl3t64 \
    libsystemd0 \
    libudev1 \
    libuuid1 \
    libzstd1; \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /out/proxmox-backup-client /usr/bin/proxmox-backup-client

ENTRYPOINT ["/usr/bin/proxmox-backup-client"]
CMD []
