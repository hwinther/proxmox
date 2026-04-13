# syntax=docker/dockerfile:1
#
# linux/amd64 only: official proxmox-backup-client-static from Proxmox pbs-client (Debian Trixie).
# https://pbs.proxmox.com/docs/installation.html#apt-based-proxmox-backup-client-repository
#
# Why not arm64 / from-source here:
# - pbs-client trixie ships binary-amd64 only (no arm64 .debs).
# - Building from git needs Proxmox devel librust-* packages; rust-proxmox-backup Build-Depends on
#   librust-apt-pkg-native, which is not available for arm64 on trixie devel (mk-build-deps fails).
# - Proxmox crates are not on crates.io, so a plain cargo + crates.io build does not work.
#
# Upstream source mirror (for reference): https://github.com/proxmox/proxmox-backup

FROM debian:trixie-slim AS builder
ENV DEBIAN_FRONTEND=noninteractive

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates wget; \
    wget -qO /usr/share/keyrings/proxmox-archive-keyring.gpg \
        https://enterprise.proxmox.com/debian/proxmox-archive-keyring-trixie.gpg; \
    printf '%s\n' \
        'Types: deb' \
        'URIs: http://download.proxmox.com/debian/pbs-client' \
        'Suites: trixie' \
        'Components: main' \
        'Signed-By: /usr/share/keyrings/proxmox-archive-keyring.gpg' \
        > /etc/apt/sources.list.d/pbs-client.sources; \
    apt-get update; \
    apt-get install -y --no-install-recommends proxmox-backup-client-static; \
    install -D /usr/bin/proxmox-backup-client /out/proxmox-backup-client; \
    apt-get purge -y wget; \
    apt-get autoremove -y; \
    rm -rf /var/lib/apt/lists/*

# Static client: only CA bundle required at runtime for TLS to PBS.
FROM debian:trixie-slim
ENV DEBIAN_FRONTEND=noninteractive

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates; \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /out/proxmox-backup-client /usr/bin/proxmox-backup-client

ENTRYPOINT ["/usr/bin/proxmox-backup-client"]
CMD []
