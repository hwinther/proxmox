# ADSB stack (edge-sdr)

GitOps manifests for **dump1090-fa**, **tar1090**, and feeders (**piaware**, **fr24**, **adsbexchange**, **opensky**) on Raspberry Pi workers. Baseline values are in ConfigMap **`adsb-env`**. Sensitive values and optional **position overrides** go in **`adsb-secret`**, which you create in the cluster (not from this repo).

Each workload that needs config uses **`envFrom`**: ConfigMap **`adsb-env`** first, then Secret **`adsb-secret`** (`optional: true`). If the same variable exists in both, the **Secret** value wins.

## Scheduling (hardware)

Pods schedule only on edge workers with **`role=sdr-edge`**, toleration for taint **`node-type=edge-sdr:NoSchedule`**, and node label **`edge-sdr/adsb-antenna=true`** on the Pi that actually has the ADS-B antenna/SDR. See [raspberry-pi-worker.md](../../../../infra/k0s/raspberry-pi-worker.md) for the full join, label, and taint steps.

```bash
kubectl label node <pi-hostname> edge-sdr/adsb-antenna=true --overwrite
```

## Secret: `adsb-secret`

Namespace: **`adsb-edge-sdr`**. **Piaware** still requires **`FEEDER_ID`** at runtime: without it, the container exits. Other feeders may stay unhealthy until their keys are set.

### Keys you can set

| Key                     | Used by                                     | Notes                                                                            |
| ----------------------- | ------------------------------------------- | -------------------------------------------------------------------------------- |
| `LAT`                   | dump1090-fa, piaware, adsbexchange, opensky | Overrides ConfigMap; use to avoid committing exact coordinates in Git.           |
| `LON`                   | dump1090-fa, piaware, adsbexchange, opensky | Same as `LAT`.                                                                   |
| `ALT`                   | opensky                                     | Antenna altitude; overrides ConfigMap if set.                                    |
| `FEEDER_ID`             | Piaware                                     | FlightAware feeder ID (required for Piaware to run).                             |
| `FR24_KEY`              | FR24                                        | Flightradar24 sharing key.                                                       |
| `ADSBX_UUID`            | adsbexchange                                | ADSB Exchange UUID.                                                              |
| `OPENSKY_USERNAME`      | OpenSky                                     | OpenSky account username.                                                        |
| `OPENSKY_SERIAL`        | OpenSky                                     | Device serial (optional after first registration).                               |
| `HEYWHATSTHAT_ID`       | tar1090                                     | HeyWhatsThat panorama id for tar1090.                                            |
| Any other ConfigMap key | All pods that `envFrom` the ConfigMap       | Same name overrides the Git-tracked default (e.g. `EXTRA_ARGS`, `DEVICE_INDEX`). |

**tar1090** `envFrom` loads the full ConfigMap; extra keys there are harmless. **FR24** only `envFrom` the Secret (for `FR24_KEY` and any future keys you add).

### Example: create the Secret

With **position** and feeder keys:

```bash
kubectl create secret generic adsb-secret -n adsb-edge-sdr \
  --from-literal=LAT='59.900000' \
  --from-literal=LON='10.500000' \
  --from-literal=ALT='50' \
  --from-literal=FEEDER_ID='YOUR_FLIGHTAWARE_FEEDER_ID' \
  --from-literal=FR24_KEY='YOUR_FR24_KEY' \
  --from-literal=ADSBX_UUID='YOUR_ADSBX_UUID' \
  --from-literal=OPENSKY_USERNAME='YOUR_OPENSKY_USER' \
  --from-literal=OPENSKY_SERIAL='YOUR_OPENSKY_SERIAL' \
  --from-literal=HEYWHATSTHAT_ID='YOUR_HEYWHATSTHAT_ID'
```

Include only the keys you actually use; omit others or replace the Secret when you add keys later, or use a GitOps-friendly secret manager.

Do **not** commit files that contain real credentials. Use the command above, Sealed Secrets, SOPS, or External Secrets instead.

### Operational notes

- Shared JSON for tar1090 uses hostPath **`/var/lib/k8s-edge-sdr/dump1090-fa`** on the node; **tar1090** is scheduled on the same node as **dump1090-fa** (`podAffinity`).
- Put **API keys and precise LAT/LON/ALT** in **`adsb-secret`**; keep **non-identifying defaults** in `configmap-adsb-env.yaml` if you want the repo to apply without a Secret (Secret still optional except for Piaware’s `FEEDER_ID` in practice).

## MQTT publishing

[`adsb-mqtt.yaml`](adsb-mqtt.yaml) runs a small publisher (`ghcr.io/hwinther/wsh-rtl-sdr/adsb-mqtt`,
built from `hwinther/wsh-rtl-sdr/images/adsb-mqtt`) that polls dump1090-fa's `aircraft.json` and
republishes the **full snapshot** (~1 Hz) to the production Mosquitto broker for downstream apps —
not Home Assistant. It co-locates with dump1090-fa (`podAffinity`) and reads the same shared
hostPath read-only; HTTP `/data/aircraft.json` isn't served by this dump1090-fa image.

Non-secret settings are env on the Deployment; the password is in `adsb-mqtt-secret`:

| Setting | Default | Notes |
| --- | --- | --- |
| `MQTT_HOST` | `10.20.13.100` | Mosquitto LoadBalancer VIP (reachable from the edge LAN). |
| `MQTT_PORT` | `1883` | Plain MQTT (no TLS listener yet). |
| `MQTT_USERNAME` | `adsb` | Must exist in the mosquitto passwd file — see [mosquitto-secrets.md](../../../production/apps/mosquitto-production/mosquitto-secrets.md). |
| `MQTT_PASSWORD` | — | **Secret only** (`adsb-mqtt-secret`). |
| `MQTT_TOPIC` | `adsb/aircraft` | Full aircraft.json blob per poll; consumer parses the `aircraft[]` array. |
| `POLL_INTERVAL` | `1` | Seconds between snapshots. Publisher skips republishing if the blob is unchanged. |

Prerequisites: (1) build the `adsb-mqtt` image in `hwinther/wsh-rtl-sdr`, then pin its tag/digest in
[adsb-mqtt.yaml](adsb-mqtt.yaml); (2) create the `adsb` mosquitto user and the Secret:

```bash
kubectl create secret generic adsb-mqtt-secret -n adsb-edge-sdr \
  --from-literal=MQTT_PASSWORD='YourAlphanumericPassword'
```

Inspect with the `mqttui` web UI in `mosquitto-production`, or
`mosquitto_sub -h 10.20.13.100 -u adsb -P '…' -t 'adsb/#' -v`.
