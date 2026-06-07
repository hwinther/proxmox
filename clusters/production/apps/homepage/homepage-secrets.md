# Homepage widget credentials

Homepage reads `{{HOMEPAGE_VAR_*}}` placeholders in its config files (e.g. `services.yaml`) from
environment variables. The `homepage` Deployment pulls them from a Secret named `homepage-secrets`
via `envFrom` (marked `optional: true`, so the pod starts without it — widgets just stay empty until
it exists). **Substitution does NOT work in Ingress annotations**, which is why widgets needing a
credential are defined in `services.yaml`, not on the app's Ingress.

## Proxmox VE + PBS widgets (live now)

These hosts are on the LAN and reachable over the homepage pod's existing egress (no NetworkPolicy
needed). Create read-only API tokens so the dashboard can't change anything.

### Create read-only API tokens

**Proxmox VE** — Datacenter → Permissions → API Tokens → Add (or `pveum`):
```bash
# On a PVE node: create a token for an audit user, role PVEAuditor (read-only), no privilege separation.
pveum user add homepage@pve
pveum acl modify / --users homepage@pve --roles PVEAuditor
pveum user token add homepage@pve homepage --privsep 0
# -> prints the token value (the "secret"); note the full id homepage@pve!homepage
```

**Proxmox Backup Server** — Configuration → Access Control → API Token, role `Audit`. Run on **each**
PBS instance (OSL and KS); each yields its own token secret:
```bash
proxmox-backup-manager user create homepage@pbs
proxmox-backup-manager acl update / Audit --auth-id homepage@pbs
proxmox-backup-manager user generate-token homepage@pbs homepage   # -> prints the secret
# REQUIRED: PBS tokens are privilege-separated by default — the token has its own (empty) ACL and the
# effective permission is the intersection of the user's and the token's. Without this grant the widget
# fails with "permission check failed" on /nodes/localhost/status.
proxmox-backup-manager acl update / Audit --auth-id 'homepage@pbs!homepage'
```

### Create the Secret
```bash
kubectl create secret generic homepage-secrets \
  --namespace platform-production \
  --from-literal=HOMEPAGE_VAR_PROXMOX_URL='https://<pve-host-or-ip>:8006' \
  --from-literal=HOMEPAGE_VAR_PROXMOX_USER='homepage@pve!homepage' \
  --from-literal=HOMEPAGE_VAR_PROXMOX_TOKEN='<pve-token-secret>' \
  --from-literal=HOMEPAGE_VAR_PBS_OSL_URL='https://pbs.osl.wsh.no:8007' \
  --from-literal=HOMEPAGE_VAR_PBS_OSL_USER='homepage@pbs!homepage' \
  --from-literal=HOMEPAGE_VAR_PBS_OSL_TOKEN='<pbs-osl-token-secret>' \
  --from-literal=HOMEPAGE_VAR_PBS_KS_URL='https://pbs.ks.wsh.no:8007' \
  --from-literal=HOMEPAGE_VAR_PBS_KS_USER='homepage@pbs!homepage' \
  --from-literal=HOMEPAGE_VAR_PBS_KS_TOKEN='<pbs-ks-token-secret>'
# then: kubectl -n platform-production rollout restart deployment/homepage
```

> **TLS note:** PVE/PBS usually serve self-signed certs. If the widget shows a TLS error, either give
> those hosts a cert homepage trusts, or front them with a trusted endpoint. There is no per-widget
> skip-verify for the proxmox widgets.

## In-cluster widgets (follow-up: Grafana / Alertmanager / RabbitMQ / Home Assistant)

These need two things the LAN widgets don't, so they're a separate pass:

1. **Network**: the homepage pod must reach the service in-cluster. The pod's `0.0.0.0/0` egress does
   **not** cover cluster-internal pods (Cilium can't match cluster identities by CIDR — same limit as
   the mosquitto/cert-manager scrape work), so each needs a CiliumNetworkPolicy egress from homepage
   to the target, plus an ingress allowance on the target if it has a default-deny policy.
2. **Config**: the credential must live in `services.yaml` (not the annotation), so each tile is
   converted from auto-discovered to a static `services.yaml` entry with `gethomepage.dev/enabled:
   "false"` on its Ingress to avoid a duplicate tile.

Planned `HOMEPAGE_VAR_*` for that pass (add to the same Secret when wired):

| Widget | Type | In-cluster URL | Auth |
|---|---|---|---|
| Alertmanager | `alertmanager` | `http://obs-kps-kube-prometheus-st-alertmanager.observability-production:9093` | none |
| Grafana | `grafana` | `http://obs-kps-grafana.observability-production:80` | `HOMEPAGE_VAR_GRAFANA_USER/PASSWORD` (local admin; basic_auth API) |
| RabbitMQ | `rabbitmq` | `http://rabbitmq.rabbitmq-production:15672` | `HOMEPAGE_VAR_RABBITMQ_USER/PASSWORD` (mgmt user) |
| Home Assistant | `homeassistant` | `http://home-assistant.home-assistant-production:8123` | `HOMEPAGE_VAR_HASS_TOKEN` (long-lived token) |
