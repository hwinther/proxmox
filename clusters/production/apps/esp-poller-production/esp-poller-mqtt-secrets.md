# esp-poller MQTT credentials

The poller authenticates to Mosquitto with a dedicated user (separate from the
shared `esp` device user) so it can be rotated independently.

The Secret is **not** in this repo. Create it once on the cluster:

```bash
POLLER_USER=esp-poller
POLLER_PW="$(openssl rand -base64 24 | tr -d '\n')"

# 1) Append the user to mosquitto-auth (see ../mosquitto-production/mosquitto-secrets.md
#    for how to regenerate the passwd file with the existing users + this new one,
#    then re-apply mosquitto-auth and restart the broker pod).

# 2) Create the poller-side credential Secret.
kubectl create secret generic esp-poller-mqtt \
  --namespace esp-poller-production \
  --from-literal=username="$POLLER_USER" \
  --from-literal=password="$POLLER_PW"
```

The Deployment reads `MQTT_USER` and `MQTT_PASS` from this Secret. Rotate by
re-creating the Secret (`kubectl create ... --dry-run=client -o yaml | kubectl apply -f -`)
and `kubectl -n esp-poller-production rollout restart deployment/esp-poller`.
