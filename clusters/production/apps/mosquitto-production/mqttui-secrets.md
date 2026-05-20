# mqttui MQTT credentials (`mosquitto-production`)

The broker runs `allow_anonymous false`, so the mqttui web inspector must log in
as a real MQTT user. Credentials come from the Secret **`mqttui-mqtt`** in
`mosquitto-production` (env `MQTT_USERNAME` / `MQTT_PASSWORD`). Not in git.

Use one of the users you put in the `mosquitto-auth` passwd file (see
[`mosquitto-secrets.md`](mosquitto-secrets.md)) — e.g. a dedicated `mqttui`
user, or the `homeassistant` user. The value must be the **plaintext**
password (mqttui sends it in the MQTT CONNECT packet; the broker hashes/compares
against `mosquitto-auth`).

```bash
kubectl -n mosquitto-production create secret generic mqttui-mqtt \
  --from-literal=MQTT_USERNAME='mqttui' \
  --from-literal=MQTT_PASSWORD='<that user'\''s plaintext password>' \
  --from-literal=MQTTUI_ADMIN_USER='admin' \
  --from-literal=MQTTUI_ADMIN_PASSWORD="$(openssl rand -base64 24)" \
  --from-literal=SECRET_KEY="$(openssl rand -hex 32)"
```

The last three keys are for **mqttui's own web UI login** (v2.0 adds a built-in
admin user, default `admin/changeme` — override it here). `SECRET_KEY` is Flask's
session signing key; without it, sessions reset on each pod restart. All three
are read via `secretKeyRef ... optional: true` in the Deployment, so they can be
patched in later without recreating the Secret:

```bash
kubectl -n mosquitto-production patch secret mqttui-mqtt --type merge -p \
  "{\"stringData\":{\"MQTTUI_ADMIN_USER\":\"admin\",\"MQTTUI_ADMIN_PASSWORD\":\"$(openssl rand -base64 24)\",\"SECRET_KEY\":\"$(openssl rand -hex 32)\"}}"
kubectl -n mosquitto-production rollout restart deploy/mqttui
```

If you add a new `mqttui` user, regenerate the `mosquitto-auth` passwd file
(`mosquitto_passwd`) to include it and roll the broker pod (see
mosquitto-secrets.md).

## Access

UI is mgmt-only at **`https://mqtt.mgmt.wsh.no/`**, behind Authelia 2FA via the
`authelia-forwardauth` middleware. With Authelia `default_policy: two_factor`
(Option A) no per-host rule is needed in the public proxmox repo.

## Image env caveat

`MQTT_BROKER` / `MQTT_PORT` match your prior podman run and are confirmed.
`MQTT_USERNAME` / `MQTT_PASSWORD` are the common var names but vary by image
build — if mqttui can't authenticate, check the container logs / image docs and
adjust the env names in `mqttui-deployment.yaml`. Likewise `runAsNonRoot:true`
with uid 1000 is assumed; if the image needs root it will CrashLoop — relax the
securityContext (and add a kyverno-policyexception, mirroring the lsio apps).
