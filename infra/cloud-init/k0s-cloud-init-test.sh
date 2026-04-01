#!/usr/bin/env bash
# Proxmox helper: clone the k0s Debian cloud-init template for a quick test VM, or tear it down.
# Run on the Proxmox host. Replaces the older split of create-debian-cloud-init-test.sh +
# destroy-debian-cloud-init-test.sh with one script and explicit commands.
#
# Environment (optional):
#   TEMPLATE_VMID   Template created by create-k0s-debian-template.sh (default: 10010)
#   CLONE_VMID      Test clone id (default: 20010)
#   CLONE_NAME      Clone name (default: k0s-cloudinit-test)
#   NO_TERMINAL=1   After `up` / `recreate`, do not run `qm terminal`
#   DESTROY_FIRST=1 With `up`, remove existing clone before cloning (same idea as --destroy-first)
#
# Examples:
#   ./k0s-cloud-init-test.sh up
#   ./k0s-cloud-init-test.sh up --destroy-first
#   DESTROY_FIRST=1 ./k0s-cloud-init-test.sh up
#   ./k0s-cloud-init-test.sh recreate
#   ./k0s-cloud-init-test.sh down
#   ./k0s-cloud-init-test.sh destroy-all

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CREATE_TEMPLATE_SCRIPT="${SCRIPT_DIR}/create-k0s-debian-template.sh"

TEMPLATE_VMID="${TEMPLATE_VMID:-10010}"
CLONE_VMID="${CLONE_VMID:-20010}"
CLONE_NAME="${CLONE_NAME:-k0s-cloudinit-test}"

vm_exists() {
  qm config "$1" &>/dev/null
}

destroy_clone() {
  if vm_exists "${CLONE_VMID}"; then
    echo "Stopping and destroying clone VM ${CLONE_VMID}..."
    qm stop "${CLONE_VMID}" 2>/dev/null || true
    qm destroy "${CLONE_VMID}"
  else
    echo "Clone VM ${CLONE_VMID} does not exist (nothing to destroy)."
  fi
}

destroy_template() {
  if vm_exists "${TEMPLATE_VMID}"; then
    echo "Stopping and destroying template VM ${TEMPLATE_VMID}..."
    qm stop "${TEMPLATE_VMID}" 2>/dev/null || true
    qm destroy "${TEMPLATE_VMID}"
  else
    echo "Template VM ${TEMPLATE_VMID} does not exist (nothing to destroy)."
  fi
}

ensure_template() {
  if vm_exists "${TEMPLATE_VMID}"; then
    echo "Using existing template VM ${TEMPLATE_VMID}."
    return 0
  fi
  echo "Template VM ${TEMPLATE_VMID} not found; running ${CREATE_TEMPLATE_SCRIPT}..."
  VMID="${TEMPLATE_VMID}" bash "${CREATE_TEMPLATE_SCRIPT}"
}

cmd_up() {
  local destroy_first="${1:-0}"
  if [[ "${destroy_first}" == 1 ]]; then
    destroy_clone
  fi
  if vm_exists "${CLONE_VMID}"; then
    echo "Clone ${CLONE_VMID} already exists. Use 'down', 'recreate', or 'up --destroy-first'." >&2
    exit 1
  fi
  ensure_template
  echo "Cloning ${TEMPLATE_VMID} -> ${CLONE_VMID} (${CLONE_NAME})..."
  qm clone "${TEMPLATE_VMID}" "${CLONE_VMID}" --full true --name "${CLONE_NAME}"
  qm start "${CLONE_VMID}"
  if [[ "${NO_TERMINAL:-0}" != 1 ]]; then
    qm terminal "${CLONE_VMID}"
  fi
}

cmd_down() {
  destroy_clone
}

cmd_recreate() {
  destroy_clone
  cmd_up 0
}

cmd_destroy_all() {
  destroy_clone
  destroy_template
}

cmd_template_only() {
  echo "Building template VM ${TEMPLATE_VMID} only (run destroy-all first if it already exists)."
  VMID="${TEMPLATE_VMID}" bash "${CREATE_TEMPLATE_SCRIPT}"
}

usage() {
  cat <<EOF
Proxmox k0s cloud-init test helper — clone template ${TEMPLATE_VMID} to ${CLONE_VMID}, or tear down.

Usage: $(basename "$0") <command> [options]

Commands:
  up [--destroy-first]   Create template if missing, full clone ${CLONE_VMID}, start, serial console
  down                   Stop and destroy clone ${CLONE_VMID} only (keep template)
  recreate               down + up (fresh clone; same as: up --destroy-first)
  destroy-all            down + destroy template ${TEMPLATE_VMID}
  template               Run create-k0s-debian-template.sh (needs free ${TEMPLATE_VMID}; see destroy-all)
  help                   Show this help

Flags:
  --destroy-first        Valid with \`up\`: remove existing clone before cloning
  --no-terminal          Before or after command: skip \`qm terminal\` on \`up\` / \`recreate\`

Env: TEMPLATE_VMID, CLONE_VMID, CLONE_NAME, NO_TERMINAL, DESTROY_FIRST
EOF
}

# Parse global flags
ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-terminal)
      export NO_TERMINAL=1
      shift
      ;;
    help|-h|--help)
      usage
      exit 0
      ;;
    *)
      ARGS+=("$1")
      shift
      ;;
  esac
done
set -- "${ARGS[@]}"

CMD="${1:-up}"
shift || true

DESTROY_FIRST_FLAG=0
case "${CMD}" in
  up)
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --destroy-first)
          DESTROY_FIRST_FLAG=1
          shift
          ;;
        --no-terminal)
          export NO_TERMINAL=1
          shift
          ;;
        *)
          echo "Unknown option for up: $1" >&2
          exit 1
          ;;
      esac
    done
    if [[ "${DESTROY_FIRST:-0}" == 1 ]] || [[ "${DESTROY_FIRST_FLAG}" == 1 ]]; then
      cmd_up 1
    else
      cmd_up 0
    fi
    ;;
  down)
    cmd_down
    ;;
  recreate)
    cmd_recreate
    ;;
  destroy-all)
    cmd_destroy_all
    ;;
  template)
    cmd_template_only
    ;;
  *)
    echo "Unknown command: ${CMD}" >&2
    usage >&2
    exit 1
    ;;
esac
