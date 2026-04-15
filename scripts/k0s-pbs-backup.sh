#!/usr/bin/env bash
# Create a k0s cluster backup and upload it to Proxmox Backup Server with
# proxmox-backup-client. Intended to run on a k0s controller (as root) via cron.
#
# k0s backup must run on the controller; see:
#   https://docs.k0sproject.io/main/backup/
#
# PBS client env (same as other tooling in this repo):
#   PBS_REPOSITORY  — required (user@host!token@pbs:port:datastore)
#   PBS_PASSWORD    — required (API token secret)
#   PBS_FINGERPRINT — optional (self-signed / pinned cert)
#
# Optional:
#   K0S_BIN         — path to k0s (default: k0s)
#   ARCHIVE_NAME    — pxar archive basename without .pxar (default: k0s-cluster)
#   PBS_BACKUP_ID   — passed to proxmox-backup-client --backup-id (default: host name)
#   LOCK_FILE       — flock lock path (default: /var/lock/k0s-pbs-backup.lock)
#
# Load credentials into the same shell (do not run the env file as a program):
#   Wrong:  /root/.pbs-env; script.sh   # exports apply only to a subshell, script.sh sees nothing
#   Right:  . /root/.pbs-env            # or: source /root/.pbs-env
# Cron / periodic example:
#   0 3 * * * . /root/.pbs-env; /path/to/k0s-pbs-backup.sh >>/var/log/k0s-pbs-backup.log 2>&1

set -euo pipefail

: "${PBS_REPOSITORY:?Set PBS_REPOSITORY (see script header)}"
: "${PBS_PASSWORD:?Set PBS_PASSWORD (see script header)}"

K0S_BIN="${K0S_BIN:-k0s}"
ARCHIVE_NAME="${ARCHIVE_NAME:-k0s-cluster}"
LOCK_FILE="${LOCK_FILE:-/var/lock/k0s-pbs-backup.lock}"

log() {
	printf '[%s] %s\n' "$(date -Iseconds)" "$*" >&2
}

die() {
	log "ERROR: $*"
	exit 1
}

command -v "$K0S_BIN" >/dev/null 2>&1 || die "k0s not found (set K0S_BIN)"
command -v proxmox-backup-client >/dev/null 2>&1 || die "proxmox-backup-client not found"
command -v flock >/dev/null 2>&1 || die "flock not found (install util-linux)"

exec 200>"$LOCK_FILE" || die "cannot open lock file $LOCK_FILE"
if ! flock -n 200; then
	log "another backup holds $LOCK_FILE; exiting"
	exit 0
fi

WORKDIR=$(mktemp -d -t k0s-pbs-backup.XXXXXX)
cleanup() {
	rm -rf "$WORKDIR"
}
trap cleanup EXIT

log "running k0s backup -> $WORKDIR"
"$K0S_BIN" backup --save-path "$WORKDIR"

shopt -s nullglob
created=( "$WORKDIR"/k0s_backup_*.tar.gz )
if ((${#created[@]} < 1)); then
	die "no k0s_backup_*.tar.gz under $WORKDIR"
fi
# If anything unexpected leaves multiple files, take the newest.
mapfile -t created < <(ls -t "${created[@]}")
BACKUP_TAR="${created[0]}"

STAGE="$WORKDIR/pxar-root"
mkdir -p "$STAGE"
# Stable name inside the archive for restores.
mv "$BACKUP_TAR" "$STAGE/k0s_backup.tar.gz"

pbs_cmd=(proxmox-backup-client backup "${ARCHIVE_NAME}.pxar:${STAGE}")
if [[ -n "${PBS_BACKUP_ID:-}" ]]; then
	pbs_cmd+=(--backup-id "$PBS_BACKUP_ID")
fi

log "uploading ${ARCHIVE_NAME}.pxar to PBS"
"${pbs_cmd[@]}"
log "finished OK ($(basename "$STAGE/k0s_backup.tar.gz"))"
