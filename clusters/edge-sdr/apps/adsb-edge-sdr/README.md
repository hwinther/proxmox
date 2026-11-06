# ADSB stack (edge-sdr)

GitOps manifests for the ADS-B decoder (**readsb**, still deployed under the **dump1090-fa** Deployment/Service name until the rename refactor), **tar1090**, and feeders (**piaware**, **fr24**, **adsbexchange**, **opensky**) on Raspberry Pi workers. Baseline values are in ConfigMap **`adsb-env`**. Sensitive values and optional **position overrides** go in **`adsb-secret`**, which you create in the cluster (not from this repo).

Each workload that needs config uses **`envFrom`**: ConfigMap **`adsb-env`** first, then Secret **`adsb-secret`** (`optional: true`). If the same variable exists in both, the **Secret** value wins.

## Scheduling (hardware)

Pods schedule only on edge workers with **`role=sdr-edge`**, toleration for taint **`node-type=edge-sdr:NoSchedule`**, and node label **`edge-sdr/adsb-antenna=true`** on the Pi that actually has the ADS-B antenna/SDR. See [raspberry-pi-worker.md](../../../../infra/k0s/raspberry-pi-worker.md) for the full join, label, and taint steps.

```bash
kubectl label node <pi-hostname> edge-sdr/adsb-antenna=true --overwrite
```

The readsb dongle (serial `00001090`) is the extended resource **`sdr.wsh.no/rtlsdr-adsb`** from
[sdr-device-plugin-edge-sdr](../sdr-device-plugin-edge-sdr/), so readsb runs as uid 65532 without
`privileged` or a USB hostPath (needs containerd's `device_ownership_from_security_context`, see
[raspberry-pi-worker.md](../../../../infra/k0s/raspberry-pi-worker.md) § SDR dongles). An init container
chowns the shared JSON hostPath to 65532. `Pending` with `Insufficient sdr.wsh.no/rtlsdr-adsb` means
the plugin does not see the dongle.

## Secret: `adsb-secret`

Namespace: **`adsb-edge-sdr`**. piaware, opensky, fr24 and adsbexchange wait for their keys (`piaware.conf`, `opensky.conf`, `FR24_KEY`, `ADSBX_UUID`).

### Keys you can set

| Key                     | Used by                                     | Notes                                                                            |
| ----------------------- | ------------------------------------------- | -------------------------------------------------------------------------------- |
| `LAT`                   | (source for `opensky.conf`)                 | Exact position, kept out of Git.                                                 |
| `LON`                   | (source for `opensky.conf`)                 | Same as `LAT`.                                                                   |
| `READSB_LAT`, `READSB_LON` | readsb (dump1090-fa Deployment), adsbexchange, dump1090-exporter | The position **rounded to 2 decimals**. readsb prints its command line at startup, so it never gets the exact `LAT`/`LON`; 2 decimals is what `receiver.json` publishes anyway. Overrides the ConfigMap's placeholders. |
| `ALT`                   | (source for `opensky.conf`)                 | Antenna altitude.                                                                |
| `FEEDER_ID`             | (source for `piaware.conf`)                 | FlightAware feeder ID.                                                           |
| `piaware.conf`          | piaware                                     | **Required.** piaware's `/etc/piaware.conf` (`key value` lines, not `key=value`), mounted from here. Generate it from `FEEDER_ID`, see below. piaware takes its position from FlightAware. |
| `FR24_KEY`              | FR24                                        | Flightradar24 sharing key.                                                       |
| `ADSBX_UUID`            | adsbexchange                                | ADSB Exchange feeder UUID. Mounted as a file and sent with `beast_reduce_plus_out`; without the key the pod waits. |
| `OPENSKY_USERNAME`      | (source for `opensky.conf`)                 | OpenSky account username.                                                        |
| `OPENSKY_SERIAL`        | (source for `opensky.conf`)                 | Device serial.                                                                   |
| `opensky.conf`          | OpenSky                                     | **Required.** openskyd's config file, mounted into `/etc/openskyd/conf.d` (the image has no start script). Generate it from the keys above, see below. |
| `HEYWHATSTHAT_ID`       | tar1090                                     | HeyWhatsThat panorama id for tar1090.                                            |
| Any other ConfigMap key | All pods that `envFrom` the ConfigMap       | Same name overrides the Git-tracked default (e.g. `DEVICE_INDEX`). The decoder (readsb) takes its command line from the Deployment's `args`, with `$(VAR)` from this env. |

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

### Generating `opensky.conf`

openskyd (0.12.0+, static on distroless) reads its settings from a config file, built here from the
existing keys without printing them. Exact position: OpenSky needs it, and fluent-bit drops the
daemon's "Sending position" log line.

```bash
get() { kubectl --context EdgeSDR -n adsb-edge-sdr get secret adsb-secret -o "jsonpath={.data.$1}" | base64 -d; }
conf=$(printf '[GPS]\nLatitude=%s\nLongitude=%s\nAltitude=%s\n\n[DEVICE]\nType=default\nserial=%s\n\n[IDENT]\nUsername=%s\n\n[INPUT]\nHost=dump1090-fa\nPort=30005\n' \
  "$(get LAT)" "$(get LON)" "$(get ALT)" "$(get OPENSKY_SERIAL)" "$(get OPENSKY_USERNAME)")
kubectl --context EdgeSDR -n adsb-edge-sdr patch secret adsb-secret --type merge \
  -p "{\"data\":{\"opensky.conf\":\"$(printf '%s\n' "$conf" | base64 -w0)\"}}"
unset conf
kubectl --context EdgeSDR -n adsb-edge-sdr rollout restart deployment/opensky
```

### Generating `piaware.conf`

piaware (0.13.0+, no start script) reads `/etc/piaware.conf`. `receiver-type other` makes faup1090
and fa-mlat-client connect to `receiver-host`/`receiver-port` directly (`relay` would mean a local
beast-splitter on localhost); MLAT results go back to readsb on 30104.

```bash
fid=$(kubectl --context EdgeSDR -n adsb-edge-sdr get secret adsb-secret -o 'jsonpath={.data.FEEDER_ID}' | base64 -d)
conf=$(printf 'allow-auto-updates no\nallow-manual-updates no\nallow-mlat yes\nmlat-results yes\nfeeder-id %s\nreceiver-type other\nreceiver-host dump1090-fa\nreceiver-port 30005\nmlat-results-format beast,connect,dump1090-fa:30104\nuse-gpsd no\n' "$fid")
kubectl --context EdgeSDR -n adsb-edge-sdr patch secret adsb-secret --type merge \
  -p "{\"data\":{\"piaware.conf\":\"$(printf '%s' "$conf" | base64 -w0)\"}}"
unset fid conf
kubectl --context EdgeSDR -n adsb-edge-sdr rollout restart deployment/piaware
```

### Operational notes

- Shared JSON for tar1090 uses hostPath **`/var/lib/k8s-edge-sdr/dump1090-fa`** on the node; **tar1090** is scheduled on the same node as **dump1090-fa** (`podAffinity`).
- Put **API keys and precise LAT/LON/ALT** in **`adsb-secret`**; keep **non-identifying defaults** in `configmap-adsb-env.yaml` if you want the repo to apply without a Secret.

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
