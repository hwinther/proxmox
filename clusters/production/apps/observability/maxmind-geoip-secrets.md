# MaxMind GeoLite2 license secret (operator-created)

The OTel collector's `geoip` processor enriches edge syslog (NAXSI events + nginx access
lines) with country/coordinates for the edge-security dashboard's attack map. An init
container downloads the free **GeoLite2-City** database at pod start, which requires a
MaxMind license key.

1. Create a free account at <https://www.maxmind.com/en/geolite2/signup>.
2. Generate a license key (Account → Manage License Keys).
3. Create the secret:

```bash
kubectl -n observability-production create secret generic maxmind-license \
  --from-literal=license-key='<your-license-key>'
```

Notes:

- The DB (~60 MB) lives in an emptyDir and is re-downloaded on every pod restart — that is
  also the only update mechanism (GeoLite2 publishes twice weekly; staleness between
  restarts is harmless for this use).
- If the secret is missing or MaxMind is unreachable through all retries, the collector pod
  stays in `Init:0/1` and the logs pipeline is down — check
  `kubectl -n observability-production logs deploy/obs-otel-collector -c geoip-db`.
- GeoLite2 EULA requires attribution for public redistribution; internal dashboard use is
  fine.
