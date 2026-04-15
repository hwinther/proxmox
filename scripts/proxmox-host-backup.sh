#!/usr/bin/env bash
# Full Proxmox/PVE host backup to Proxmox Backup Server (root filesystem, with excludes).
#
# Credentials: same as k0s-pbs-backup.sh — use a root-only env file, then source it
# (do not run the file as /path/to/.pbs-env; use `. /path/to/.pbs-env`).
#
#   PBS_REPOSITORY  — required unless set after sourcing PBS_ENV_FILE
#   PBS_PASSWORD    — required
#   PBS_FINGERPRINT — optional
#
# Optional:
#   PBS_ENV_FILE — default /root/.pbs-env
#
set -euo pipefail

PBS_ENV_FILE="${PBS_ENV_FILE:-/root/.pbs-env}"
if [[ -f "$PBS_ENV_FILE" ]]; then
	# shellcheck disable=SC1090
	. "$PBS_ENV_FILE"
fi

: "${PBS_REPOSITORY:?Set PBS_REPOSITORY or create $PBS_ENV_FILE (see header)}"
: "${PBS_PASSWORD:?Set PBS_PASSWORD or create $PBS_ENV_FILE (see header)}"

export PBS_REPOSITORY PBS_PASSWORD
if [[ -n "${PBS_FINGERPRINT:-}" ]]; then
	export PBS_FINGERPRINT
fi

proxmox-backup-client backup \
	root.pxar:/ \
	--exclude /var/lib/vz/ \
	--exclude /var/log/journal \
	--exclude /mnt \
	--exclude /tmp \
	--exclude /var/tmp
