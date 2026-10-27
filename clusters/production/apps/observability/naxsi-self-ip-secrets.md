# NAXSI self-IP secret (operator-created)

The OTel collector's `transform/naxsi-classify` processor labels NAXSI blocks with
`naxsi.client="self"` when the request came from our own public WAN address (LAN traffic
hairpins out and back via NAT reflection, so OPNsense logs the public IP). The address is kept
out of git and injected as the `NAXSI_SELF_IP` env var from this secret.

```bash
kubectl -n observability-production create secret generic naxsi-self-ip \
  --from-literal=ip="$(curl -s https://ifconfig.me)"
```

Run the `curl` from a host on the home LAN, so it returns the OPNsense WAN address and not an
away-mode or VPN egress.

Notes:

- When the ISP address changes, update the secret and restart the collector (env vars are read
  at pod start):

  ```bash
  kubectl -n observability-production create secret generic naxsi-self-ip \
    --from-literal=ip='<new-ip>' --dry-run=client -o yaml | kubectl apply -f -
  kubectl -n observability-production rollout restart deploy/obs-otel-collector
  ```

- The secret ref is `optional`: if it is missing, nothing is classified as `self` and the
  "self" alert stays silent, but the pipeline keeps running. The second NAXSI alert (blocks
  against our own services) still fires either way.
