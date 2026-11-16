# Plan: secrets from OpenBao through External Secrets Operator

**State on 2026-11-16:** not started. Nothing is deployed (no OpenBao, no ESO, no SOPS decryption in Flux). This is the next platform item: the two items ahead of it, per-app Flux service accounts and the Gateway API move, are done.

**Before any work starts, the owner must make the three decisions in "Decisions".** Do not pick for them. Everything under "Phases" depends on the answers.

## Problem

Secrets are created by hand with `kubectl create secret`, documented per app in `*-secrets.md`. There is no central source and no audit trail, and disaster recovery means restoring etcd from backup or redoing every command.

The repo is public, so encrypted-in-git (SOPS) would put ciphertext in public history for good. That is why OpenBao plus ESO is preferred, and why SOPS and Sealed Secrets are out of scope.

## Target

- **OpenBao** (the MPL-licensed Vault fork) as the source. KV v2 first. Later, maybe the database engine for dynamic CNPG credentials, and PKI.
- **External Secrets Operator** on both clusters: one `ClusterSecretStore` pointing at OpenBao, and one `ExternalSecret` per Secret, replacing the CLI step in each `*-secrets.md`.
- Running apps must survive an OpenBao outage. ESO keeps the existing Secret when a refresh fails, so an outage blocks changes, not workloads. Confirm the `creationPolicy` and `deletionPolicy` defaults of the ESO version in use.

## Decisions (owner)

### 1. Where OpenBao runs

| Option | For | Against |
|---|---|---|
| In the production cluster (Flux HelmRelease, raft, 3 replicas, Ceph PVCs) | Same GitOps pattern as everything else; reuses netpol, Kyverno and PBS backup | Tied to cluster recovery: a rebuilt cluster needs OpenBao before its apps |
| A dedicated LXC on Proxmox | Independent of Kubernetes | Outside Flux, one more box to patch, HA needs three |

Earlier leaning: in-cluster, provided the unseal keys and root token are kept offline and raft snapshots go to PBS.

### 2. How it unseals

Every pod restart starts sealed, and pods restart on node reboots, k0s upgrades and rebalancing.

| Option | Notes |
|---|---|
| Manual Shamir keys | Safest. Painful with Autopilot upgrades and post-reboot rebalancing |
| Static-key seal | Check the OpenBao docs for the current version. The key then has to live somewhere, and a Kubernetes Secret is weak |
| Transit auto-unseal from a second small OpenBao (an LXC) | The classic pattern. The small one unseals by hand but rarely restarts |
| PKCS#11 / HSM | Strongest. Hardware and setup work |

Cloud KMS is out of scope.

### 3. How each cluster authenticates

- **Production:** the Kubernetes auth method, with token review against the local API.
- **edge-sdr:** OpenBao must be reachable from the Pis, including in away mode. Either Kubernetes auth with a reviewer token for the edge API, or JWT auth against the edge cluster's service-account issuer.
- **People:** OIDC through Authelia.

## Phases

Each phase is one PR, or a small group, and ends with its check passing.

1. **Record the decisions** in this file, including where the unseal keys and root token are kept offline. The values themselves never go in git.
2. **OpenBao in production.** Use the `new-cluster-app` skill. HelmRelease with raft HA, the netpol baseline plus the peer and API rules it needs, a PrometheusRule for `sealed` and "no leader", and a raft snapshot CronJob to PBS that follows the existing backup pattern.
   - *Check:* three pods Ready and unsealed, a snapshot in PBS, the sealed alert fires when one pod is restarted and left sealed.
3. **Disaster-recovery test, before anything real is migrated.** Restore a raft snapshot into a fresh OpenBao, unseal it with the offline keys, and confirm ESO resyncs.
   - *Check:* done once on a throwaway instance and written up as a runbook next to the manifests.
4. **ESO in production** with the `ClusterSecretStore`. Pilot one low-risk Secret in a test namespace, side by side with the hand-made one.
   - *Check:* the `ExternalSecret` is `SecretSynced`, and the Secret survives OpenBao being scaled to zero.
5. **Migrate app by app.** Each `*-secrets.md` becomes "lives in OpenBao at path X". The owner enters the values. Decide which Kyverno secret-clone policies ESO replaces, and note the open upstream issue about cloned Secrets and owner references in [`../backlog.md`](../backlog.md) item 1.
6. **edge-sdr:** ESO plus a store, using the auth path from decision 3.
7. **Later:** dynamic CNPG credentials, PKI.

## Rules while doing this

- Secret values are entered by the owner. Prepare commands and paths with placeholders.
- No Secret manifests in git, as today.
- A step that could lock the cluster out of its own secrets (changing the seal, rotating the root token) is done by the owner with the runbook open.
