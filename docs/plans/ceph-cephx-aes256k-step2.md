# Plan: Ceph cephx aes256k, step 2

**State on 2026-11-16:** parked since 2026-11-08, and still blocked. Every k0s node and both Pis run kernel 6.18; step 2 needs Linux 7.0 or newer on all of them. Earliest expected around 2027-05, when Alpine stable and Debian ship a 7.0+ kernel. Do not use backports or testing kernels to get there sooner.

All Ceph and secret commands here are run by the owner on a Proxmox host.

## Where we are (step 1, done 2026-11-07)

- `pve-cephx-rotate-service-keys --rotate-cluster-keys --apply` (run once from office-pve-amd) moved
  mon., mgr.*, osd.0-2, bootstrap-*, crash and the 3 osd-lockbox keys to `aes256k` and set
  `auth_service_cipher aes256k`. `auth_preferred_cipher` is still `aes`.
- Canary passed: all 19 active pbs-backup jobs succeeded after the rotation (2026-11-07).
- Still `aes` on purpose:
  - `client.csi-k8s` (production) and `client.csi-k8s-edge-sdr` (edge-sdr): ceph-csi maps RBD with
    krbd, and kernel aes256k support needs Linux 7.0+. k0s nodes (Alpine 3.24) and the Pis (Debian
    trixie) run 6.18.
  - `client.admin`.
- Expected health warnings until step 2: `AUTH_INSECURE_CLIENT_KEY_TYPE`,
  `AUTH_INSECURE_KEYS_ALLOWED`, `AUTH_INSECURE_KEYS_CREATABLE` (may be muted with
  `ceph health mute <code> --sticky`).
- Keep `/etc/pve/priv/cephx-key-migration.json` until step 2 is complete.

## Do NOT run before the prerequisites below

- `pve-cephx-rotate-service-keys --restrict-ciphers`
- `--wipe-rotating-keys`
- `ceph config set ... auth_allowed_ciphers aes256k`

Any of these before the CSI keys are aes256k and every node runs 7.0+ breaks every PVC mount.

## Prerequisites (check all)

- [ ] Every k0s node on both clusters runs kernel 7.0+ (`kubectl get nodes -o wide`, KERNEL-VERSION
      column): production k0s-prod01..05 (Alpine) and the edge-sdr Pis (Debian) plus edge workers.
- [ ] The kernel upgrade did not leave a module mismatch (nfs/rbd modules for the running kernel;
      see "Node OS issues" in the `k0s-node-maintenance` skill). `rbd` module loads on every node.
- [ ] ceph-csi still uses krbd and is >= 3.17.1 (3.18.2 on 2026-11-16; 3.19 moves to the operator, chart gone).
- [ ] PVE hosts' own Ceph clients (pve kernel already 7.0) are fine; any other Ceph clients (LXC
      bind mounts, PBS, scripts) inventoried and on aes256k-capable versions.

## Steps (user runs the PVE/Ceph and secret commands)

1. Rotate `client.csi-k8s-edge-sdr` to an aes256k key first (smaller blast radius), update the
   ceph-csi secret in the edge-sdr cluster, restart the nodeplugin pods, verify PVC mounts.
   Exact rotation command: check the pve-cephx-rotate-service-keys help / Ceph docs at that time.
2. Same for `client.csi-k8s` in production; canary = nightly pbs-backup jobs + CNPG pods mounting.
3. Rotate `client.admin` (`--rotate-admin-key`).
4. Then `--restrict-ciphers` / `auth_allowed_ciphers aes256k`, and `--wipe-rotating-keys`.
5. Confirm `ceph health` has no AUTH_INSECURE_* left; unmute any sticky mutes; remove
   `/etc/pve/priv/cephx-key-migration.json` only after everything has run a few days.

## Why aes256k service tickets were already safe in step 1

Session key = min(client key type, service key type) = aes for old kernel clients; the ticket blob is
opaque to the client (Rook docs + Ceph CephxKeyServer.cc). Only restricting ciphers breaks them.
