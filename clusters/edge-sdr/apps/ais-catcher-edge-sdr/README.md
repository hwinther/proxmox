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
| `MQTT_PASSWORD`         | Password for the `ais-catcher` Mosquitto user (see [MQTT publishing](#mqtt-publishing)). Keep alphanumeric (goes in the broker URL). |
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

## Reciprocal feed sharing (AISHub, AIS-catcher community)

Share your decodes back to public aggregators the same way as ShipXplorer — extra AIS-catcher CLI flags in **`EXTRA_ARGS`** on the `ais-catcher-secret`. These are **user-side secret edits**, never committed: recreate the Secret with the pattern above (combine multiple outputs in one `EXTRA_ARGS` string).

| Service | Flag | Notes |
| --- | --- | --- |
| **ShipXplorer** | `-u <host> <port> <key>` | Three-part UDP feed: host, port, **and** the station key (as in the Secret examples above). |
| **AISHub** | `-u <assigned-host> <assigned-port>` | AISHub assigns you a **personal UDP host + port** after you register the station at [aishub.net](https://www.aishub.net/); there is **no key** in the `-u` line (unlike ShipXplorer). |
| **AIS-catcher community** | `-X <sharing-key>` | Community sharing to [aiscatcher.org](https://aiscatcher.org/); the sharing key comes from registering the station there. Use a bare `-X` to share **anonymously** (no key). |

Example — AISHub UDP output plus AIS-catcher community sharing, alongside the MQTT password (recreate to change these, then restart the Deployment so the new args are picked up):

```bash
kubectl create secret generic ais-catcher-secret -n ais-catcher-edge-sdr \
  --from-literal=EXTRA_ARGS='-u AISHUB_HOST AISHUB_PORT -X YOUR_SHARING_KEY' \
  --from-literal=MQTT_PASSWORD='YourAlphanumericPassword'
```

## MQTT publishing

AIS-catcher publishes each decoded message to the production **Mosquitto** broker so other apps can
consume the stream (not Home Assistant — generic data pipeline). The image's start script enables it
when `MQTT_HOST` is set; non-secret settings are in [`configmap-ais-catcher-env.yaml`](configmap-ais-catcher-env.yaml):

| Setting | Default | Notes |
| --- | --- | --- |
| `MQTT_HOST` | `10.20.13.100` | Mosquitto LoadBalancer VIP (reachable from the edge LAN). |
| `MQTT_PORT` | `1883` | Plain MQTT (no TLS listener yet). |
| `MQTT_USERNAME` | `ais-catcher` | Must exist in the mosquitto passwd file — see [mosquitto-secrets.md](../../../production/apps/mosquitto-production/mosquitto-secrets.md). |
| `MQTT_PASSWORD` | — | **Secret only** (`ais-catcher-secret`). Keep alphanumeric (embedded in the broker URL). |
| `MQTT_TOPIC` | `ais/data` | Supports templates, e.g. `ais/%mmsi%` or `ais/%type%/%mmsi%`. |
| `MQTT_MSGFORMAT` | `JSON_FULL` | One of NMEA, NMEA_TAG, FULL, JSON_NMEA, JSON_SPARSE, JSON_FULL. |

Prerequisites: (1) a new image build with MQTT support in the start script
(`hwinther/wsh-rtl-sdr`), then bump the tag/digest in [ais-catcher-deployment.yaml](ais-catcher-deployment.yaml);
(2) create the `ais-catcher` mosquitto user and put its password in `ais-catcher-secret`:

```bash
kubectl create secret generic ais-catcher-secret -n ais-catcher-edge-sdr \
  --from-literal=EXTRA_ARGS='-u hub.shipxplorer.com 37615 YOUR_API_KEY' \
  --from-literal=MQTT_PASSWORD='YourAlphanumericPassword'
```

Inspect the live stream with the `mqttui` web UI in `mosquitto-production`, or
`mosquitto_sub -h 10.20.13.100 -u ais-catcher -P '…' -t 'ais/#' -v`.
