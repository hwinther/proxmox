# Web-based file viewer for client-side-encrypted PBS backups

Design notes for a future self-hosted web UI that browses and restores individual files from
Proxmox Backup Server (PBS) snapshots that are **client-side encrypted with our own keyfile**.
Status: **idea / spec — not built yet.**

## Why this is needed (the built-in browser can't do it)

PBS ships a web-based file browser in its own UI, but it has two encryption stories that behave
differently:

| Backup type | Encryption | GUI file restore? |
| ----------- | ---------- | ----------------- |
| VM / CT block-image backup | Key uploaded to PVE (Datacenter → Storage → PBS → Encryption) | ✅ Yes — PVE has the key |
| `proxmox-backup-client` host-type (pxar) backup | Client-side, passphrase-protected keyfile | ❌ **No GUI path at all** |

Our app/PVC backups (the `*-pbs-backup` CronJobs) are the second kind: host-type pxar archives,
client-side encrypted with a key **different from any key PBS/PVE itself holds**. The server only
ever sees ciphertext, so browsing/restoring them server-side is *structurally impossible* — it's not
a missing feature. The only official route is the CLI with `--keyfile`:

```bash
proxmox-backup-client catalog shell <snapshot> --keyfile key.json   # interactive browse
proxmox-backup-client restore <snapshot> <archive>.pxar <target> --keyfile key.json
```

No off-the-shelf project fills this gap (the community projects are backup *clients*, not
encrypted-snapshot browsers), so a small DIY web UI is justified.

## Core principle: wrap the official client, don't reimplement crypto

Let `proxmox-backup-client` do all of: auth to PBS, chunk fetch, AES-256-GCM decrypt, and pxar
parsing. The web app is a thin layer that shells out to it and renders the results. Reimplementing
chunk decryption + pxar parsing is possible but a large surface and an easy way to get crypto wrong.

## Two ways to drive the client

### Option A — FUSE mount (nicest browse UX, worst fit for k8s)

```bash
proxmox-backup-client mount <snapshot> <archive>.pxar /mnt/view --keyfile key.json
# then serve /mnt/view read-only with any file-browser backend; unmount when idle
```

Clean to browse, but FUSE in a container needs `/dev/fuse` + `SYS_ADMIN` → a privileged pod, which
fights our default-deny / no-privileged-workloads posture.

### Option B — catalog list + targeted restore (no privileges) — **recommended**

```bash
# cheap: downloads + decrypts only the catalog (metadata), NOT the data chunks
proxmox-backup-client catalog dump <snapshot> --keyfile key.json     # -> build the tree UI from this

# on a download click: fetch + decrypt only the chunks for the chosen path
proxmox-backup-client restore <snapshot> <archive>.pxar /tmp/out --pattern '<path>' --keyfile key.json
```

No FUSE, no privileged pod, REST-friendly. Browsing stays fast because data chunks are only pulled
on an actual extract. The cost is building the tree view from the catalog ourselves — a small price
for staying inside the security model.

## Secret / key handling (the sensitive part)

The viewer effectively holds the crown jewels, so treat it accordingly.

| Purpose | Mechanism |
| ------- | --------- |
| PBS auth | `PBS_REPOSITORY`, `PBS_PASSWORD` (or API token), `PBS_FINGERPRINT` |
| Decrypt | `--keyfile` + `PBS_ENCRYPTION_PASSWORD` (passphrase that unlocks the keyfile) |

Reuse plumbing we already have:
- Label the viewer's namespace `pbs.wsh.no/encryption-keyfile=true` so the existing Kyverno
  `clone-pbs-encryption-keyfile` ClusterPolicy clones the keyfile in.
- Mount the relevant `*-pbs-backup` Secret for the repo creds + `PBS_ENCRYPTION_PASSWORD`.

Hardening:
- **Gate behind OIDC (`auth.wsh.no`); keep strictly off the public internet** (standing constraint).
- Prefer requiring the passphrase at session time over baking it into the pod at rest, so a running
  pod doesn't hold the passphrase.
- Read-only restore target (scratch dir / emptyDir); stream the file to the user, then clean up.
- NetworkPolicy: egress only to the PBS endpoint(s); ingress only from the OIDC ingress.

## Where it lives

- The **generic mechanism** (client wrapper, UI, Helm/manifests) is publishable in this public repo.
- Anything naming the **specific datastores / snapshots / apps** stays in the private-apps repo so
  private names don't leak here.

## Open decisions before building

1. **Browse mechanism:** Option B (no-FUSE, recommended) vs Option A (FUSE, nicer UX, privileged pod).
2. **Manifests location:** this public repo (generic) vs private-apps (if it must reference real
   datastores/snapshots).
3. **Passphrase model:** mounted-at-rest vs supplied per session.

## MVP sketch (Option B)

1. List datastores + snapshots via the PBS REST API (`https://<pbs>:8007/api2/json/`, API token).
2. For a chosen snapshot, `catalog dump` → render a file tree (catalog only, cheap to decrypt).
3. On download, `restore … --pattern <path>` into a scratch dir, stream the file out, delete it.
4. OIDC in front, keyfile + passphrase from the cloned Secret, egress-restricted to PBS.

## References

- [Backup Client Usage — catalog shell / mount / restore / `--keyfile`](https://pbs.proxmox.com/docs/backup-client.html)
- [Is GUI support for restoring encrypted proxmox-backup-client backups planned? (forum — confirms CLI-only)](https://forum.proxmox.com/threads/is-gui-support-for-restoring-encrypted-proxmox-backup-client-backups-planned.168830/)
- [Restore file from PBS GUI from an encrypted backup (forum)](https://forum.proxmox.com/threads/restore-file-from-pbs-gui-from-a-encrypted-backup.131231/)
