#!/usr/bin/env bash
# Shared helpers for create-k0s-*-template.sh (sourced, not executed directly).
# shellcheck shell=bash

# Resize VM scsi0 by the delta between DISK_TARGET and the source image virtual size
# (qemu-img). Uses +NM so we only grow by what is missing. Proxmox/qemu: G/M/K/T = binary
# (GiB, MiB, ...), same as numfmt --from=iec.
#
# Args: vmid, path_to_source_qcow2, target_spec (e.g. 64G)
k0s_resize_scsi0_to_target() {
  local vmid="$1"
  local image_path="$2"
  local target_spec="$3"
  local mib src_bytes tgt_bytes

  if [[ ! -f "${image_path}" ]]; then
    echo "k0s_resize_scsi0_to_target: missing image ${image_path}" >&2
    return 1
  fi

  read -r mib src_bytes tgt_bytes < <(python3 - "${image_path}" "${target_spec}" <<'PY'
import json, re, subprocess, sys

path, spec = sys.argv[1], sys.argv[2]
out = subprocess.check_output(["qemu-img", "info", "--output", "json", path])
src = json.loads(out.decode())["virtual-size"]


def parse_target(s):
    s = str(s).strip().upper().replace("IB", "").rstrip("B")
    m = re.match(r"^(\d+(?:\.\d+)?)\s*([KMGT])?$", s)
    if not m:
        sys.exit("Invalid DISK_TARGET: {!r}".format(spec))
    n, u = float(m.group(1)), (m.group(2) or "G")
    mult = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    return int(n * mult[u])


tgt = parse_target(spec)
delta = tgt - src
if delta <= 0:
    print("0 {} {}".format(src, tgt))
else:
    mib = (delta + (1 << 20) - 1) // (1 << 20)
    print("{} {} {}".format(mib, src, tgt))
PY
  )

  if [[ "${mib}" == "0" ]]; then
    echo "scsi0: source virtual size ${src_bytes} bytes already >= target (${target_spec} -> ${tgt_bytes} bytes); skipping resize."
    return 0
  fi

  echo "scsi0: source ${src_bytes} bytes -> target ${tgt_bytes} bytes; growing by +${mib}M"
  qm resize "${vmid}" scsi0 "+${mib}M"
}
