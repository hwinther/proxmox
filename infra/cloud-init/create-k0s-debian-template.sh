#!/usr/bin/env bash
# Creates a Debian 13 (trixie) generic-cloud VM template on Proxmox with cloud-init
# pointing at vendor-k0s-debian-node.yaml (k0s binary, sysctl, bpffs, etc.).
#
# Run this ON the Proxmox host from any cwd. Snippet sources default to this script's
# ../snippets/ directory (this repo). Override with SNIPPETS_DIR if you keep snippets elsewhere.
#
# Prerequisites: wget, pvesm/qm available; edit cloud-init-user.example.yaml (or your user
# snippet) with a real SSH key before first boot, or omit user data and pass --sshkeys instead.
#
# Usage:
#   ./create-k0s-debian-template.sh
#   IMAGENAME=... IMAGEURL=... VMID=10010 ./create-k0s-debian-template.sh
#   NETWORK_SOURCE="${SNIPPETS_DIR}/network-example-static.yaml" ./create-k0s-debian-template.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SNIPPETS_DIR="${SNIPPETS_DIR:-${SCRIPT_DIR}/snippets}"

# Debian 13 generic cloud (amd64). See https://cdimage.debian.org/images/cloud/trixie/latest/
export IMAGENAME="${IMAGENAME:-debian-13-genericcloud-amd64.qcow2}"
export IMAGEURL="${IMAGEURL:-https://cdimage.debian.org/images/cloud/trixie/latest/}"

export IMAGEFOLDER="${IMAGEFOLDER:-/tmp}"
export STORAGE="${STORAGE:-local}"
export VMNAME="${VMNAME:-k0s-debian13-trixie-cloudinit-template}"
export VMID="${VMID:-10010}"
export VMMEM="${VMMEM:-8196}"
export VMCORES="${VMCORES:-2}"
export VMSETTINGS="${VMSETTINGS:---net0 virtio,bridge=vmbr0,tag=10,firewall=1 --net1 virtio,bridge=vmbr0,tag=20,firewall=1}"
export DISK_RESIZE="${DISK_RESIZE:-32G}"

# Proxmox expects snippet names under local:snippets/ (files in /var/lib/vz/snippets/)
USER_SNIPPET_NAME="${USER_SNIPPET_NAME:-cloud-init-k0s-user.yaml}"
VENDOR_SNIPPET_NAME="${VENDOR_SNIPPET_NAME:-vendor-k0s-debian-node.yaml}"

USER_YAML="/var/lib/vz/snippets/${USER_SNIPPET_NAME}"
VENDOR_YAML="/var/lib/vz/snippets/${VENDOR_SNIPPET_NAME}"

USER_SOURCE="${USER_SOURCE:-${SNIPPETS_DIR}/cloud-init-user.example.yaml}"
VENDOR_SOURCE="${SNIPPETS_DIR}/vendor-k0s-debian-node.yaml"

SSH_KEYS_FILE="${SSH_KEYS_FILE:-${REPO_ROOT}/scripts/cloud-init/ci-ssh-keys}"

for f in "${USER_SOURCE}" "${VENDOR_SOURCE}"; do
  if [[ ! -f "${f}" ]]; then
    echo "Missing snippet file: ${f}" >&2
    exit 1
  fi
done

echo "Using snippets from: ${SNIPPETS_DIR}"
echo "Image: ${IMAGEURL}${IMAGENAME}"

wget -O "${IMAGEFOLDER}/${IMAGENAME}" --continue "${IMAGEURL}${IMAGENAME}"
qm create "${VMID}" --name "${VMNAME}" --memory "${VMMEM}" --cores "${VMCORES}" --cpu host --ostype l26 ${VMSETTINGS}
qm set "${VMID}" --scsi0 "${STORAGE}:0,import-from=${IMAGEFOLDER}/${IMAGENAME},discard=on"
qm resize "${VMID}" scsi0 "+${DISK_RESIZE}"
qm set "${VMID}" --scsi2 "${STORAGE}:cloudinit"
qm set "${VMID}" --boot='order=scsi0;scsi2' --scsihw virtio-scsi-single
qm set "${VMID}" --serial0 socket --vga serial0
qm set "${VMID}" --agent enabled=1,fstrim_cloned_disks=1

CICUSTOM_PARTS=()

mkdir -p /var/lib/vz/snippets

USE_CUSTOM_USER="${USE_CUSTOM_USER:-1}"
if [[ "${USE_CUSTOM_USER}" == "1" ]]; then
  ln -sf "${USER_SOURCE}" "${USER_YAML}"
  ln -sf "${VENDOR_SOURCE}" "${VENDOR_YAML}"
  CICUSTOM_PARTS+=("user=local:snippets/${USER_SNIPPET_NAME}")
  CICUSTOM_PARTS+=("vendor=local:snippets/${VENDOR_SNIPPET_NAME}")
else
  echo "USE_CUSTOM_USER=0: using built-in ciuser / sshkeys only (no user-data)."
  if [[ -f "${SSH_KEYS_FILE}" ]]; then
    qm set "${VMID}" --sshkeys "${SSH_KEYS_FILE}"
  else
    echo "Warning: SSH keys file not found at ${SSH_KEYS_FILE}" >&2
  fi
  qm set "${VMID}" --ciupgrade 1
  ln -sf "${VENDOR_SOURCE}" "${VENDOR_YAML}"
  CICUSTOM_PARTS+=("vendor=local:snippets/${VENDOR_SNIPPET_NAME}")
fi

# Optional static network: same pattern as user/vendor — symlink repo file into /var/lib/vz/snippets/.
# Example: NETWORK_SOURCE="${SNIPPETS_DIR}/network-example-static.yaml"
# Optional: NETWORK_SNIPPET_NAME=my-node.yaml (defaults to basename of NETWORK_SOURCE)
if [[ -n "${NETWORK_SOURCE:-}" ]]; then
  if [[ ! -f "${NETWORK_SOURCE}" ]]; then
    echo "NETWORK_SOURCE is not a file: ${NETWORK_SOURCE}" >&2
    exit 1
  fi
  NETWORK_SNIPPET_NAME="${NETWORK_SNIPPET_NAME:-$(basename "${NETWORK_SOURCE}")}"
  NETWORK_YAML="/var/lib/vz/snippets/${NETWORK_SNIPPET_NAME}"
  ln -sf "$(readlink -f "${NETWORK_SOURCE}")" "${NETWORK_YAML}"
  CICUSTOM_PARTS+=("network=local:snippets/${NETWORK_SNIPPET_NAME}")
  echo "Linked network config: ${NETWORK_SOURCE} -> ${NETWORK_YAML}"
else
  echo "No NETWORK_SOURCE; using DHCP and SLAAC for ipconfig0."
  qm set "${VMID}" --ipconfig0 ip=dhcp,ip6=auto
fi

CICUSTOM=$(IFS=,; echo "${CICUSTOM_PARTS[*]}")
qm set "${VMID}" --cicustom "${CICUSTOM}"

qm template "${VMID}"
echo "TEMPLATE ${VMNAME} (VMID ${VMID}) created."
echo "Clone this template in the UI or with qm clone. Ensure ${USER_SOURCE} has a real SSH key before relying on it."
