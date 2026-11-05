# AIS-Catcher (edge-sdr)

GitOps manifests for **ais-catcher** on Raspberry Pi workers. Non-sensitive defaults live in ConfigMap **`ais-catcher-env`**; optional overrides and secrets live in **`ais-catcher-secret`**.

## Scheduling (hardware)

The Deployment requires **`role=sdr-edge`**, toleration for taint **`node-type=edge-sdr:NoSchedule`**, and node label **`edge-sdr/ais-antenna=true`** on the Pi that has the AIS antenna/SDR. See [raspberry-pi-worker.md](../../../../infra/k0s/raspberry-pi-worker.md) for the full join, label, and taint steps.

```bash
kubectl label node <pi-hostname> edge-sdr/ais-antenna=true --overwrite
```

## Secret: `ais-catcher-secret`

The image (0.7.0 and later) is one static AIS-catcher binary on distroless: no shell, no start
script. The command line is the Deployment's `args`, with `$(VAR)` taken from the env: ConfigMap
**`ais-catcher-env`** first, then Secret **`ais-catcher-secret`**, so a key in both takes the Secret's
value.

Kubernetes passes each `$(VAR)` as **one** argument, so a multi-word value such as the old
`EXTRA_ARGS` cannot go through env (AIS-catcher rejects `"-u host port -X key"` as one argument).
The feeds are a config file instead: key **`feeds.json`** in the Secret, mounted at
`/etc/ais-catcher/feeds.json` and read with `-C`, which merges it with the command line.

| Key | Purpose |
| --- | --- |
| `LAT`, `LON` | Exact station position (decimal degrees), so it is not committed; overrides the ConfigMap. |
| `feeds.json` | **Required** (the pod waits for it). The outputs that carry keys or passwords: the aiscatcher.org sharing key (`-X`), UDP hubs (`-u`, e.g. ShipXplorer's host/port/key, AISHub's assigned host/port) and MQTT (`-Q`, the broker URL holds the password). |

### Writing `feeds.json`

AIS-catcher writes the file from the same flags with `-J`: it prints a banner and then the JSON,
and exits. Build it locally and add it to the Secret; nothing is committed. The
`ais-catcher` Mosquitto user is in [mosquitto-secrets.md](../../../production/apps/mosquitto-production/mosquitto-secrets.md);
keep its password alphanumeric (it goes in the URL).

```bash
docker run --rm ghcr.io/hwinther/wsh-rtl-sdr/ais-catcher:0.7.0 -J     -X YOUR_SHARING_KEY     -u hub.shipxplorer.com 37615 YOUR_API_KEY     -u AISHUB_HOST AISHUB_PORT     -Q 'mqtt://ais-catcher:PASSWORD@10.20.13.100:1883' topic ais/data msgformat JSON_FULL client_id aiscatcher qos 0   | sed -n '/^{/,$p' > feeds.json

kubectl -n ais-catcher-edge-sdr patch secret ais-catcher-secret --type merge   -p "{\"data\":{\"feeds.json\":\"$(base64 -w0 feeds.json)\"}}"
rm feeds.json
kubectl -n ais-catcher-edge-sdr rollout restart deployment/ais-catcher
```

A bare `-X` shares anonymously. Check what the pod picked up in its log: one `Hub feed:`, `UDP:`
and `MQTT feed:` line per output (the MQTT URL is not printed).

Do **not** commit files that contain real credentials.

## Feeds

| Service | Flag | Notes |
| --- | --- | --- |
| **ShipXplorer** | `-u <host> <port> <key>` | Three-part UDP feed: host, port **and** the station key. |
| **AISHub** | `-u <assigned-host> <assigned-port>` | AISHub assigns a **personal UDP host + port** after registering the station at [aishub.net](https://www.aishub.net/); no key. |
| **AIS-catcher community** | `-X <sharing-key>` | Plain TCP to aiscatcher.org; the key comes from registering the station there. A bare `-X` shares anonymously. |
| **MQTT** | `-Q mqtt://user:pass@host:port topic … msgformat …` | Each decoded message to the production **Mosquitto** broker (LB VIP `10.20.13.100`, plain 1883). `topic` supports templates (`ais/%mmsi%`); `msgformat` is one of NMEA, NMEA_TAG, FULL, JSON_NMEA, JSON_SPARSE, JSON_FULL. |

`/metrics` has `ais_output_connected` per output (from the AIS-catcher commit of 2026-11-03 on).

Inspect the live MQTT stream with the `mqttui` web UI in `mosquitto-production`, or
`mosquitto_sub -h 10.20.13.100 -u ais-catcher -P '…' -t 'ais/#' -v`.
