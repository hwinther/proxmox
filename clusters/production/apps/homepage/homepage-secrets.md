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
  --from-literal=HOMEPAGE_VAR_PBS_KS_TOKEN='<pbs-ks-token-secret>' \
  --from-literal=HOMEPAGE_VAR_GRAFANA_USER='homepage' \
  --from-literal=HOMEPAGE_VAR_GRAFANA_PASSWORD='<grafana-viewer-password>' \
  --from-literal=HOMEPAGE_VAR_RABBITMQ_USER='homepage' \
  --from-literal=HOMEPAGE_VAR_RABBITMQ_PASSWORD='<rabbitmq-monitoring-password>' \
  --from-literal=HOMEPAGE_VAR_HASS_TOKEN='<home-assistant-long-lived-token>'
# then: kubectl -n platform-production rollout restart deployment/homepage
```

> **TLS note:** PVE/PBS usually serve self-signed certs. If the widget shows a TLS error, either give
> those hosts a cert homepage trusts, or front them with a trusted endpoint. There is no per-widget
> skip-verify for the proxmox widgets.

## In-cluster widgets (Grafana / Alertmanager / RabbitMQ / Home Assistant)

These are wired (static tiles in `services.yaml`; their Ingresses set `gethomepage.dev/enabled:"false"`
to avoid duplicates). Reachability: the homepage pod's `0.0.0.0/0` egress does **not** cover
cluster-internal pods (Cilium can't match cluster identities by CIDR — same limit as the
mosquitto/cert-manager scrape work), so `homepage/networkpolicies.yaml` adds an egress CNP to each
target; RabbitMQ + Home Assistant also get `allow-homepage-*` ingress CNPs in their namespaces
(Grafana/Alertmanager are unrestricted in observability-production). **Alertmanager** needs no
credential — its widget is set via Ingress annotations and isn't in the Secret.

| Widget | In-cluster URL | Credential vars |
|---|---|---|
| Alertmanager | `…alertmanager.observability-production:9093` | none |
| Grafana | `obs-kps-grafana.observability-production:80` | `HOMEPAGE_VAR_GRAFANA_USER` / `…_PASSWORD` |
| RabbitMQ | `rabbitmq.rabbitmq-production:15672` | `HOMEPAGE_VAR_RABBITMQ_USER` / `…_PASSWORD` |
| Home Assistant | `home-assistant.home-assistant-production:8123` | `HOMEPAGE_VAR_HASS_TOKEN` |

### Creating the credentials (read-only where possible)

- **Grafana** — basic-auth works on the API even with the login form disabled (`auth.basic` is on by
  default). Create a Viewer user named `homepage` (Administration → Users, or via the admin API) and use
  its password. Avoid using the admin account.
- **RabbitMQ** — create a `monitoring`-tag user (read-only management):
  ```bash
  kubectl -n rabbitmq-production exec sts/rabbitmq-server -c rabbitmq -- \
    rabbitmqctl add_user homepage '<password>'
  kubectl -n rabbitmq-production exec sts/rabbitmq-server -c rabbitmq -- \
    rabbitmqctl set_user_tags homepage monitoring
  kubectl -n rabbitmq-production exec sts/rabbitmq-server -c rabbitmq -- \
    rabbitmqctl set_permissions -p / homepage '' '' '.*'   # read-only
  ```
- **Home Assistant** — Profile → Security → Long-lived access tokens → Create Token.
