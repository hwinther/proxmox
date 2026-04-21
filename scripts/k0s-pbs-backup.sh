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
#   PBS_FINGERPRINT — optional; only when the system CA store cannot validate the PBS
#                     cert (see PBS docs). The client reads this from the environment.
#                     If PBS uses a public CA (e.g. ACME / Let's Encrypt) and the host
#                     trusts it, leave PBS_FINGERPRINT unset.
#
# Fingerprint cache (often the real issue when PBS_FINGERPRINT is not set):
#   After you approve a server once, proxmox-backup-client stores the fingerprint under
#   ~/.config/proxmox-backup/fingerprints (see PBS pbs-client http_client.rs: one line per
#   server, "hostname sha256:..."). On ACME renewal the live fingerprint changes but the
#   cache still has the old one → mismatch prompts. Keeping ca-certificates current can
#   avoid the fingerprint path entirely when the client’s OpenSSL validates the chain.
#
#   PBS_SYNC_TLS_FINGERPRINT=1 — before upload, connect with openssl s_client using the
#   system trust store (-verify_return_error; optional -verify_hostname when supported).
#   Only if TLS verifies, take the leaf SHA256 fingerprint and merge it into
#   ~/.config/proxmox-backup/fingerprints for the repository hostname, then unset
#   PBS_FINGERPRINT so the client uses the refreshed file. Same MITM resistance as a
#   normal HTTPS client: you trust public CAs + correct hostname, not a blind "y".
#   Requires openssl. For cron as root, set HOME=/root or XDG_CONFIG_HOME if needed.
#   PBS_TLS_SERVERNAME — optional SNI override (default: hostname from PBS_REPOSITORY).
#
# Client-side encryption (PBS AES-256-GCM; see Backup Client docs § Encryption):
#   PBS_KEYFILE — if set, passed as --keyfile to proxmox-backup-client (path to the key
#                 created with `proxmox-backup-client key create ...`). If unset, the client
#                 still uses ~/.config/proxmox-backup/encryption-key.json when present.
#   PBS_ENCRYPTION_PASSWORD — unlocks a password-protected key (read by the client from env).
#   PBS_ENCRYPTION_PASSWORD_FILE / _FD / _CMD — same as PBS docs (preferred for cron).
#
# Optional:
#   K0S_BIN              — path to k0s (default: k0s)
#   ARCHIVE_NAME         — pxar archive basename for the k0s tarball (default: k0s-cluster)
#   PBS_NAMESPACE        — PBS datastore namespace (not Kubernetes): passed as --ns, e.g.
#                          `prod/k0s` or `a/b/c`. Create/locate namespaces in the PBS UI;
#                          restores and `snapshot list` need the same --ns. See PBS docs.
#   PBS_BACKUP_ID        — passed to proxmox-backup-client --backup-id (default: host name)
#   LOCK_FILE            — flock lock path (default: /var/lock/k0s-pbs-backup.lock)
#   SKIP_USR_LOCAL_BIN   — if set to 1, do not add usr-local-bin.pxar:/usr/local/bin
#   PBS_AUTO_ACCEPT_FINGERPRINT — if set to 1, pipe "y" into proxmox-backup-client so
#                     interactive fingerprint prompts auto-accept (stale cache, cron).
#                     Insecure if you rely on it instead of fixing trust/cache; clearing
#                     ~/.config/proxmox-backup/ or updating the CA bundle is safer.
#   PBS_DEBUG=1 — bash trace (`set -x`); do not enable in routine cron logs.
#
# Load credentials into the same shell (do not run the env file as a program):
#   Wrong:  /root/.pbs-env; script.sh   # exports apply only to a subshell, script.sh sees nothing
#   Right:  . /root/.pbs-env            # or: source /root/.pbs-env
# Cron / periodic example (ACME PBS: refresh pinned fingerprint each run after LE renews):
#   0 3 * * * . /root/.pbs-env; PBS_SYNC_TLS_FINGERPRINT=1 HOME=/root /path/to/k0s-pbs-backup.sh >>/var/log/k0s-pbs-backup.log 2>&1

set -euo pipefail

if [[ "${PBS_DEBUG:-0}" == "1" ]]; then
	set -x
fi

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

# Parse PBS_REPOSITORY suffix user@realm!token@host:port:datastore (hostname must not
# contain ':'; IPv6 in repository is not supported here).
pbs_parse_repo_host_port() {
	local suffix rest
	suffix="${PBS_REPOSITORY##*@}"
	PBS_REPO_DATASTORE="${suffix##*:}"
	rest="${suffix%:$PBS_REPO_DATASTORE}"
	PBS_REPO_PORT="${rest##*:}"
	PBS_REPO_HOST="${rest%:$PBS_REPO_PORT}"
	[[ -n "${PBS_REPO_HOST:-}" && -n "${PBS_REPO_PORT:-}" ]] ||
		die "cannot parse host:port from PBS_REPOSITORY (expected ...@host:port:datastore)"
}

# Merge one line into proxmox-backup-client fingerprints file (same layout as PBS).
pbs_merge_fingerprints_file() {
	local server="$1" fp="$2"
	local home="${HOME:-/root}"
	local cfg="${XDG_CONFIG_HOME:-$home/.config}/proxmox-backup"
	local path="$cfg/fingerprints"
	local tmp line a b

	mkdir -p "$cfg"
	tmp=$(mktemp "$WORKDIR/fingerprints-merge.XXXXXX")
	if [[ -f "$path" ]]; then
		while IFS= read -r line || [[ -n "$line" ]]; do
			[[ -z "$line" ]] && continue
			read -r a b <<<"$line"
			if [[ -n "$a" && -n "$b" && "$a" == "$server" ]]; then
				continue
			fi
			printf '%s\n' "$line" >>"$tmp"
		done <"$path"
	fi
	printf '%s %s\n' "$server" "$fp" >>"$tmp"
	mv "$tmp" "$path"
	chmod 600 "$path" 2>/dev/null || true
}

pbs_fetch_verified_tls_fingerprint() {
	local host="$1" port="$2" sni="$3"
	local errf certf capath_args=() vhost=() fp_line

	errf="$WORKDIR/openssl-verify.err"
	certf="$WORKDIR/openssl-cert.pem"
	if [[ -d /etc/ssl/certs ]] && [[ -n "$(ls -A /etc/ssl/certs 2>/dev/null)" ]]; then
		capath_args=(-CApath /etc/ssl/certs)
	elif [[ -f /etc/ssl/certs/ca-certificates.crt ]]; then
		capath_args=(-CAfile /etc/ssl/certs/ca-certificates.crt)
	fi
	if openssl s_client -help 2>&1 | grep -q -- '-verify_hostname'; then
		vhost=(-verify_hostname "$sni")
	fi

	set +e
	echo | openssl s_client -connect "${host}:${port}" -servername "$sni" \
		-verify_return_error "${vhost[@]}" "${capath_args[@]}" 2>"$errf" 1>"$certf"
	set -e

	# OpenSSL puts chain progress on stderr but often prints "Verify return code: 0 (ok)"
	# on stdout after the PEM — grepping stderr alone falsely fails despite a good TLS verify.
	if ! grep -q 'Verify return code: 0 (ok)' "$errf" "$certf" 2>/dev/null; then
		log "openssl s_client stderr:"
		sed 's/^/  /' "$errf" >&2 || true
		log "openssl s_client verify lines (stdout):"
		grep -E '^(Verify return code|Verification:|Verified peername:)' "$certf" 2>/dev/null |
			sed 's/^/  /' >&2 || true
		die "TLS verification failed for ${host}:${port} (SNI $sni); not updating fingerprint"
	fi

	fp_line=$(openssl x509 -in "$certf" -noout -fingerprint -sha256 2>/dev/null) ||
		die "could not read server certificate from openssl output"
	fp_line=${fp_line#SHA256 Fingerprint=}
	fp_line=${fp_line#sha256 Fingerprint=}
	printf '%s' "$fp_line" | tr 'A-F' 'a-f'
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

pbs_cmd=(proxmox-backup-client backup)
if [[ -n "${PBS_BACKUP_ID:-}" ]]; then
	pbs_cmd+=(--backup-id "$PBS_BACKUP_ID")
fi
if [[ -n "${PBS_NAMESPACE:-}" ]]; then
	pbs_cmd+=(--ns "$PBS_NAMESPACE")
fi
if [[ -n "${PBS_KEYFILE:-}" ]]; then
	[[ -f "$PBS_KEYFILE" ]] || die "PBS_KEYFILE is not a readable file: $PBS_KEYFILE"
	pbs_cmd+=(--keyfile "$PBS_KEYFILE")
fi
pbs_cmd+=("${ARCHIVE_NAME}.pxar:${STAGE}")
if [[ "${SKIP_USR_LOCAL_BIN:-0}" != "1" ]]; then
	if [[ -d /usr/local/bin ]]; then
		pbs_cmd+=(usr-local-bin.pxar:/usr/local/bin)
	else
		log "SKIP /usr/local/bin (not a directory)"
	fi
fi

if [[ "${PBS_SYNC_TLS_FINGERPRINT:-0}" == "1" ]]; then
	command -v openssl >/dev/null 2>&1 || die "openssl not found (install or unset PBS_SYNC_TLS_FINGERPRINT)"
	pbs_parse_repo_host_port
	sni="${PBS_TLS_SERVERNAME:-$PBS_REPO_HOST}"
	log "sync TLS fingerprint for ${PBS_REPO_HOST}:${PBS_REPO_PORT} (SNI ${sni}, openssl verify)"
	fp="$(pbs_fetch_verified_tls_fingerprint "$PBS_REPO_HOST" "$PBS_REPO_PORT" "$sni")"
	[[ -n "$fp" ]] || die "empty fingerprint from openssl"
	pbs_merge_fingerprints_file "$PBS_REPO_HOST" "$fp"
	unset PBS_FINGERPRINT
	log "updated ~/.config/proxmox-backup/fingerprints for ${PBS_REPO_HOST}"
fi

log "uploading pxar archive(s) to PBS"
if [[ "${PBS_AUTO_ACCEPT_FINGERPRINT:-0}" == "1" ]]; then
	# proxmox-backup-client may prompt repeatedly on mismatch; `yes` keeps stdin open.
	# With pipefail, `yes` often exits 141 (SIGPIPE) after the client closes stdin — use
	# PIPESTATUS[1] for the real proxmox-backup-client exit code.
	set +e
	yes y | "${pbs_cmd[@]}"
	pbs_rc=${PIPESTATUS[1]}
	set -e
	[[ "$pbs_rc" -eq 0 ]] || exit "$pbs_rc"
else
	"${pbs_cmd[@]}"
fi
log "finished OK (k0s: $(basename "$STAGE/k0s_backup.tar.gz"))"
