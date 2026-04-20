#!/usr/bin/env bash
# Creates an Alpine Linux generic-cloud (cloud-init) VM template on Proxmox with vendor
# vendor-k0s-alpine-node.yaml (k0s binary, sysctl, bpffs, OpenRC services, etc.).
#
# Run this ON the Proxmox host. Snippet sources default to ../snippets/ (this repo).
# Override with SNIPPETS_DIR if you keep snippets elsewhere.
#
# Image index: https://dl-cdn.alpinelinux.org/alpine/latest-stable/releases/cloud/
# Pick a **generic** *bios-cloudinit* **qcow2** for SeaBIOS VMs (default below), or a UEFI
# variant if your template uses OVMF.
#
# Usage:
#   ./create-k0s-alpine-template.sh
#   IMAGENAME=... IMAGEURL=... VMID=10011 ./create-k0s-alpine-template.sh
#   DISK_TARGET=128G ./create-k0s-alpine-template.sh
#   NETWORK_SOURCE="${SNIPPETS_DIR}/network-example-static.yaml" ./create-k0s-alpine-template.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/k0s-template-common.sh
source "${SCRIPT_DIR}/lib/k0s-template-common.sh"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SNIPPETS_DIR="${SNIPPETS_DIR:-${SCRIPT_DIR}/snippets}"

# See https://dl-cdn.alpinelinux.org/alpine/latest-stable/releases/cloud/ — bump IMAGENAME when Alpine releases.
export IMAGENAME="${IMAGENAME:-generic_alpine-3.23.3-x86_64-bios-cloudinit-r0.qcow2}"
export IMAGEURL="${IMAGEURL:-https://dl-cdn.alpinelinux.org/alpine/latest-stable/releases/cloud/}"

export IMAGEFOLDER="${IMAGEFOLDER:-/tmp}"
export STORAGE="${STORAGE:-local}"
export VMNAME="${VMNAME:-k0s-alpine-cloudinit-template}"
export VMID="${VMID:-10011}"
export VMMEM="${VMMEM:-8196}"
export VMCORES="${VMCORES:-2}"
export VMSETTINGS="${VMSETTINGS:---net0 virtio,bridge=vmbr0,tag=10,firewall=1 --net1 virtio,bridge=vmbr0,tag=20,firewall=1}"
# Total virtual disk size for scsi0 (GiB-style G/M/K/T). Only the delta from the cloud image is added.
export DISK_TARGET="${DISK_TARGET:-64G}"

USER_SNIPPET_NAME="${USER_SNIPPET_NAME:-cloud-init-k0s-user.yaml}"
VENDOR_SNIPPET_NAME="${VENDOR_SNIPPET_NAME:-vendor-k0s-alpine-node.yaml}"

USER_YAML="/var/lib/vz/snippets/${USER_SNIPPET_NAME}"
VENDOR_YAML="/var/lib/vz/snippets/${VENDOR_SNIPPET_NAME}"

USER_SOURCE="${USER_SOURCE:-${SNIPPETS_DIR}/cloud-init-user.yaml}"
VENDOR_SOURCE="${VENDOR_SOURCE:-${SNIPPETS_DIR}/vendor-k0s-alpine-node.yaml}"

SSH_KEYS_FILE="${SSH_KEYS_FILE:-${REPO_ROOT}/scripts/cloud-init/ci-ssh-keys}"

for f in "${USER_SOURCE}" "${VENDOR_SOURCE}"; do
  if [[ ! -f "${f}" ]]; then
    echo "Missing snippet file: ${f}" >&2
    exit 1
  fi
done

echo "Using snippets from: ${SNIPPETS_DIR}"
echo "Image: ${IMAGEURL}${IMAGENAME}"
echo "DISK_TARGET (scsi0 total): ${DISK_TARGET}"

wget -O "${IMAGEFOLDER}/${IMAGENAME}" --continue "${IMAGEURL}${IMAGENAME}"
qm create "${VMID}" --name "${VMNAME}" --memory "${VMMEM}" --cores "${VMCORES}" --cpu host --ostype l26 ${VMSETTINGS}
qm set "${VMID}" --scsi0 "${STORAGE}:0,import-from=${IMAGEFOLDER}/${IMAGENAME},discard=on"
k0s_resize_scsi0_to_target "${VMID}" "${IMAGEFOLDER}/${IMAGENAME}" "${DISK_TARGET}"
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
