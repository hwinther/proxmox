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
#
# Updates: Dependabot bumps the debian and distroless digests; .github/workflows/
# bump-pbs-client.yml opens a PR when Proxmox publishes a newer proxmox-backup-client-static (it
# links OpenSSL statically, so its CVE fixes only arrive with a new package). Either change touches
# this directory, so build-proxmox-pbs-backup-client.yml rebuilds the image on merge.

# proxmox-backup-client-static from the pbs-client trixie repo, pinned so a rebuild is reproducible
# and a new upstream version is a reviewed PR.
ARG PBS_CLIENT_VERSION=4.2.8-1

FROM debian:trixie-slim@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2 AS builder
ENV DEBIAN_FRONTEND=noninteractive
ARG PBS_CLIENT_VERSION

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
    apt-get install -y --no-install-recommends "proxmox-backup-client-static=${PBS_CLIENT_VERSION}"; \
    install -D /usr/bin/proxmox-backup-client /out/proxmox-backup-client; \
    apt-get purge -y wget; \
    apt-get autoremove -y; \
    rm -rf /var/lib/apt/lists/*

# Distroless static runtime: ships /etc/ssl/certs/ca-certificates.crt + minimal
# /etc/passwd, no shell, no package manager. The :nonroot tag runs as UID 65532;
# override with `--user 0` (or USER 0 in a downstream image) if you need to read
# host-mounted paths that aren't world-readable. Multi-arch is not configured
# because pbs-client trixie ships binary-amd64 only (see builder-stage comment).
FROM gcr.io/distroless/static-debian13:nonroot@sha256:25ac8f0c3b2334a9eb05452266bd4697864a8c8ef0ef71e5e6480d7f92868329 AS final

COPY --from=builder /out/proxmox-backup-client /usr/bin/proxmox-backup-client

ENTRYPOINT ["/usr/bin/proxmox-backup-client"]
CMD []
