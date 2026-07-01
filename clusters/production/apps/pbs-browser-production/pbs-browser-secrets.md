# pbs-browser secrets & prerequisites

`pbs-browser` browses and restores files from **client-side-encrypted** PBS snapshots. It needs PBS
credentials, the keyfile passphrase, and the encryption keyfile. None of these are committed to git.

## 1. `pbs-browser-pbs` Secret (create out-of-band)

Holds the PBS connection + decryption config, consumed via `envFrom` in `deployment.yaml`. Use a
**read-only / restore-scoped PBS API token** (a `DatastoreReader`-style role on the relevant
datastore) — this app never writes to PBS.

```bash
kubectl -n pbs-browser-production create secret generic pbs-browser-pbs \
  --from-literal=PBS_REPOSITORY='user@pbs!tokenid@pbs.example.com:8007:datastore' \
  --from-literal=PBS_PASSWORD='<api-token-secret>' \
  --from-literal=PBS_ENCRYPTION_PASSWORD='<keyfile-passphrase>'
# optional:
#   --from-literal=PBS_NAMESPACE='Production/k0s'
#   --from-literal=PBS_FINGERPRINT='<sha256-cert-fingerprint>'   # for self-signed PBS
```

| Key | Required | Notes |
| --- | -------- | ----- |
| `PBS_REPOSITORY` | yes | `user@realm!tokenid@host:8007:datastore` |
| `PBS_PASSWORD` | yes | API token secret value |
| `PBS_ENCRYPTION_PASSWORD` | yes | passphrase that unlocks the keyfile (cluster convention) |
| `PBS_NAMESPACE` | optional | datastore namespace, e.g. `Production/k0s` |
| `PBS_FINGERPRINT` | optional | server cert fingerprint, for self-signed PBS |

## 2. Encryption keyfile (automatic)

The namespace carries the label `pbs.wsh.no/encryption-keyfile: "true"`, so the Kyverno
`clone-pbs-encryption-keyfile` ClusterPolicy (in `platform-production`) clones the cluster-wide
`pbs-encryption-keyfile` Secret into this namespace. The deployment mounts it read-only at
`/etc/pbs/keyfile`. If the source Secret is missing, the mount is empty and the app runs without
`--keyfile` (it then can only browse unencrypted snapshots).

Verify:

```bash
kubectl -n pbs-browser-production get secret pbs-encryption-keyfile
```

## 3. Container image visibility

`deployment.yaml` references `ghcr.io/hwinther/pbs-browser/app` with **no `imagePullSecrets`**,
matching clutterstock's public-package convention. Make that GHCR package **public**, or — if you
keep it private — add a `ghcr-pull` clone policy + `imagePullSecrets` (copy the pattern in
`../ddnsadmin/kyverno-clusterpolicies.yaml` and add a `…/ghcr-pull: "true"` namespace label).

## 4. Access

The app is internal-only on `https://pbs-browser.mgmt.wsh.no`, gated by Authelia forward-auth
(`ingress.yaml`). It reads the `Remote-User` / `Remote-Email` headers Authelia injects purely to log
who restored which file. Keep it off the public internet.
