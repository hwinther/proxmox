# Proxmox Backup client on Debian 13 (Trixie).
# PBS client-only APT repo (not Proxmox VE):
# https://pbs.proxmox.com/docs/installation.html#apt-based-proxmox-backup-client-repository
#
# amd64: proxmox-backup-client-static (statically linked; smaller dependency set).
# arm64: proxmox-backup-client (dynamic); upstream static build is x86-64-only.
#
# Single-stage image keeps multi-arch builds reliable; amd64 still avoids pulling
# the full dynamic client and most shared libs.

FROM debian:trixie-slim
ARG TARGETARCH
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
    if [ "$TARGETARCH" = "amd64" ]; then \
        apt-get install -y --no-install-recommends proxmox-backup-client-static; \
    else \
        apt-get install -y --no-install-recommends proxmox-backup-client; \
    fi; \
    apt-get purge -y wget; \
    apt-get autoremove -y; \
    rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["/usr/bin/proxmox-backup-client"]
CMD []
