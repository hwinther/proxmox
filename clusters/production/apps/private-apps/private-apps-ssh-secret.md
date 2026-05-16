# private-apps SSH deploy key (`flux-system`)

The `GitRepository/private-apps` source authenticates to a separate **private** GitHub repo
with a read-only SSH **deploy key**, stored in the Kubernetes Secret **`private-apps-ssh`**
in namespace **`flux-system`**.

This (public) repo only ever contains the source _pointer_ — the repo URL and this secret's
_name_. The key material and the private repo's manifests are never committed here.
**Do not commit the key or a `*.secret.example.yaml`.**

## Create the deploy key + Secret

```bash
# 1. Generate a dedicated read-only key (no passphrase — Flux runs unattended)
ssh-keygen -t ed25519 -N '' -C 'flux-private-apps' -f ./private-apps-deploy-key

# 2. Add the PUBLIC key to GitHub:
#    private repo -> Settings -> Deploy keys -> Add deploy key
#    Title: flux-private-apps  |  Key: contents of ./private-apps-deploy-key.pub
#    Leave "Allow write access" UNCHECKED (Flux only reads).

# 3. Create the Flux source secret (the flux CLI auto-populates known_hosts).
#    SSH over 443 — port 22 egress is blocked from the cluster nodes. The URL must
#    match spec.url in gitrepository.yaml (host ssh.github.com, port 443).
flux create secret git private-apps-ssh \
  --namespace flux-system \
  --url=ssh://git@ssh.github.com:443/hwinther/private-apps.git \
  --private-key-file=./private-apps-deploy-key

# 4. Delete the local key copies once the Secret exists.
rm ./private-apps-deploy-key ./private-apps-deploy-key.pub
```

`kubectl` equivalent (if not using the flux CLI): a generic Secret with keys `identity`
(private key), `identity.pub` (public key), and `known_hosts`
(`ssh-keyscan -p 443 ssh.github.com`).

## Rotate

Generate a new key, add it as a second deploy key, recreate the Secret
(`flux create secret git ... --private-key-file=...`), then remove the old deploy key from
GitHub.

## Verify (without printing the key)

```bash
kubectl -n flux-system describe secret private-apps-ssh
flux get sources git private-apps        # expect Ready=True with a fetched revision
flux get kustomizations private-apps     # expect Ready=True with an applied revision
```
