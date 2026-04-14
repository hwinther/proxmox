# AIS-Catcher (edge-sdr)

GitOps manifests for **ais-catcher** on Raspberry Pi workers. Non-sensitive defaults live in ConfigMap **`ais-catcher-env`**; optional overrides and secrets live in **`ais-catcher-secret`**.

## Scheduling (hardware)

The Deployment requires **`role=sdr-edge`**, toleration for taint **`node-type=edge-sdr:NoSchedule`**, and node label **`edge-sdr/ais-antenna=true`** on the Pi that has the AIS antenna/SDR. See [raspberry-pi-worker.md](../../../../infra/k0s/raspberry-pi-worker.md) for the full join, label, and taint steps.

```bash
kubectl label node <pi-hostname> edge-sdr/ais-antenna=true --overwrite
```

## Secret: `ais-catcher-secret`

The Deployment loads env in this order: ConfigMap **`ais-catcher-env`**, then Secret **`ais-catcher-secret`** (`secretRef.optional: true`). If the same variable exists in both, the **Secret** value wins. Keys you omit in the Secret keep their ConfigMap values.

Use the Secret for **exact positions** (`LAT`, `LON`) so coordinates are not committed in Git, and for hub/API material such as **`EXTRA_ARGS`**.

### Keys you can set

| Key                     | Purpose                                                                                                                           |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `LAT`                   | Station latitude (decimal degrees); overrides ConfigMap.                                                                          |
| `LON`                   | Station longitude (decimal degrees); overrides ConfigMap.                                                                         |
| `EXTRA_ARGS`            | Extra CLI flags for AIS-catcher (e.g. `-u host port key`, `-Q mqtt://...`).                                                       |
| Any other ConfigMap key | Same names as in **`ais-catcher-env`** (`DEVICE_INDEX`, `STATION_URL`, `BIASTEE`, …) if you need to override without editing Git. |

### Example: create the Secret

Position + hub flags (quote values as needed for your shell):

```bash
kubectl create secret generic ais-catcher-secret -n ais-catcher-edge-sdr \
  --from-literal=LAT='59.900000' \
  --from-literal=LON='10.500000' \
  --from-literal=EXTRA_ARGS='-u hub.example.com 12345 YOUR_KEY'
```

Hub flags only (keep `LAT`/`LON` in the ConfigMap until you add them here):

```bash
kubectl create secret generic ais-catcher-secret -n ais-catcher-edge-sdr \
  --from-literal=EXTRA_ARGS='-u hub.shipxplorer.com 37615 YOUR_API_KEY'
```

To rotate, replace the Secret (e.g. delete and recreate, or `kubectl create secret ... --dry-run=client -o yaml | kubectl apply -f -` with a manifest generated locally and **never** committed).

Do **not** commit files that contain real credentials. Use the commands above, Sealed Secrets, SOPS, or External Secrets instead.
