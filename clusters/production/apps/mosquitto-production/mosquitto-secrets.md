# Mosquitto credentials

The broker runs `allow_anonymous false` + `password_file`. The password file is
**not** in this repo — it lives only in the `mosquitto-auth` Secret in
`mosquitto-production`, mounted read-only at `/mosquitto/auth/passwd`.

The file is a standard `mosquitto_passwd` file (`username:<bcrypt-hash>` lines).
Generate it with the mosquitto CLI image so the hash format matches the broker:

```bash
# Pick credentials. Use one shared device user, or one per consumer.
HA_USER=homeassistant
HA_PW="$(openssl rand -base64 24 | tr -d '\n')"
ESP_USER=esp
ESP_PW="$(openssl rand -base64 24 | tr -d '\n')"
MQTTUI_USER=mqttui
MQTTUI_PW="$(openssl rand -base64 24 | tr -d '\n')"
# AIS-catcher (edge-sdr) publishes the AIS stream here. Keep it ALPHANUMERIC — it goes in the
# broker URL (mqtt://user:pass@host) in AIS-catcher's -Q flag, which can't take @ : / in userinfo.
AIS_USER=ais-catcher
AIS_PW="$(openssl rand -hex 18)"

# Build the passwd file with the same image the broker uses.
docker run --rm --entrypoint sh eclipse-mosquitto:2.0.20 -c '
  touch /tmp/passwd
  mosquitto_passwd -b /tmp/passwd '"$HA_USER"' '"$HA_PW"'
  mosquitto_passwd -b /tmp/passwd '"$ESP_USER"' '"$ESP_PW"'
  mosquitto_passwd -b /tmp/passwd '"$MQTTUI_USER"' '"$MQTTUI_PW"'
  mosquitto_passwd -b /tmp/passwd '"$AIS_USER"' '"$AIS_PW"'
  cat /tmp/passwd' > passwd

kubectl create secret generic mosquitto-auth \
  --namespace mosquitto-production \
  --from-file=passwd=./passwd

rm -f passwd
```

Record `HA_USER`/`HA_PW` — they go into Home Assistant's MQTT config entry
(broker `mosquitto.mosquitto-production.svc.cluster.local`, port `1883`).
`ESP_USER`/`ESP_PW` go into ESP/Tasmota/ESPHome firmware (broker
`10.20.13.100`, port `1883`). `AIS_USER`/`AIS_PW` go into the `ais-catcher-secret`
(`MQTT_PASSWORD`) in `ais-catcher-edge-sdr` — see
[ais-catcher README](../../../edge-sdr/apps/ais-catcher-edge-sdr/README.md#mqtt-publishing).

To add/rotate a user later: regenerate the file the same way and
`kubectl create secret ... --dry-run=client -o yaml | kubectl apply -f -`, then
restart the pod (`kubectl -n mosquitto-production rollout restart statefulset/mosquitto`)
so it re-reads the file.

## Connectivity recap

- **In-cluster (HA):** `mosquitto.mosquitto-production.svc.cluster.local:1883`
  (CiliumNetworkPolicy allows the `home-assistant` pod).
- **External (ESP/IoT):** `10.20.13.100:1883` — Cilium LB-IPAM VIP, L2-announced
  on `10.20.13.0/24`. Devices on other VLANs need a router/firewall rule
  permitting `<iot-subnet> -> 10.20.13.100:1883`.
- **Prerequisite:** L2 announcements enabled in the k0s Cilium stanza (see
  `clusters/production/apps/cilium-lb/namespace-note.md`).
- **TLS (8883):** not configured yet. Plain 1883 only. Adding a TLS listener
  needs a cert decision (ESP firmware won't trust the internal cert-manager CA
  without baking it in) — tracked as a follow-up.
