# mosquitto-exporter

Prometheus exporter for the [Mosquitto](https://mosquitto.org/) broker. It subscribes to `$SYS/#`
and exposes every numeric `$SYS` topic as a metric on `:9234/metrics`
(`$SYS/broker/clients/connected` becomes `broker_clients_connected`). It runs as the `exporter`
sidecar in `clusters/production/apps/mosquitto-production/mosquitto-statefulset.yaml`.

## Origin

Vendored from [sapcc/mosquitto-exporter](https://github.com/sapcc/mosquitto-exporter) at commit
[`e097dec`](https://github.com/sapcc/mosquitto-exporter/commit/e097dec2cf003f606caf92fafab1167a7da98375)
(2022-05-09, the last commit; the last image is `sapcc/mosquitto-exporter:0.8.0`). Licensed under
Apache-2.0, see [LICENSE](LICENSE). The upstream image was built with Go 1.17 and old dependencies,
and its findings were all in the Go standard library, `golang.org/x/net` and
`prometheus/client_golang`, so the fix is a rebuild with current versions.

## Changes from upstream

- `go.mod`: module path `github.com/hwinther/proxmox/images/mosquitto-exporter`, Go 1.26 language
  version, built with the Go toolchain of the `golang` image in the Dockerfile.
- Dependencies: `github.com/codegangsta/cli` replaced by `github.com/urfave/cli/v3` (the same
  project, renamed); `eclipse/paho.mqtt.golang` and `prometheus/client_golang` on current
  releases.
- `main.go`: ported to the urfave/cli v3 API. Flag names, short aliases, defaults and environment
  variables are unchanged (`--endpoint/-e`, `--bind-address/-b`, `--user/-u`, `--pass/-p`,
  `--cert/-c`, `--key/-k`, `--client-id/-i`; `BROKER_ENDPOINT`, `BIND_ADDRESS`, `MQTT_USER`,
  `MQTT_PASS`, `MQTT_CERT`, `MQTT_KEY`, `MQTT_CLIENT_ID`). The bind-failure log message now
  includes the error.
- TLS: upstream disabled certificate checks (`InsecureSkipVerify: true`). The broker certificate is
  now verified against the system roots, or against a private CA given with the new `--ca-cert`
  flag (`MQTT_CA_CERT`). Minimum TLS 1.2. The production sidecar uses plain MQTT on 1883, so this
  only matters if TLS is turned on later.
- `main_test.go` (new): pins the metric names and types that dashboards and alerts use.
- `Dockerfile`: static build (`CGO_ENABLED=0`) on a digest-pinned `golang` image, distroless
  `static-debian13:nonroot` runtime. The version comes from the `mosquitto-exporter-v*` release tag.
- Not taken: upstream's Makefile, Dockerfile and renovate.json.

Metric names, types and values are the same as upstream: topics in `counterKeyMetrics` are counters,
every other numeric topic is a gauge, and the static/deprecated topics in `ignoreKeyMetrics` are
skipped.

## Build and test

```sh
go vet ./... && go test ./...
docker build -t mosquitto-exporter:dev .
```

`.github/workflows/build-mosquitto-exporter.yml` builds and Grype-scans the image on pull requests
that touch this directory. A `mosquitto-exporter-v<version>` tag publishes and signs
`ghcr.io/hwinther/proxmox/mosquitto-exporter:<version>`.
