# Podinfo edge (Pi scheduling demo)

| Item | Value |
|------|--------|
| Namespace | **`podinfo-test`** (app **podinfo** + env **test** — separate from **`test-test`**, the sample `ghcr.io/hwinther/test` stack) |
| URL | **https://podinfo-edge.test.wsh.no** |
| Scheduling | [podinfo-edge-deployment.yaml](podinfo-edge-deployment.yaml) — tolerates `node-type=edge-sdr:NoSchedule`, **nodeAffinity** `role In [sdr-edge]` |

See [infra/k0s/raspberry-pi-worker.md](../../../infra/k0s/raspberry-pi-worker.md) for joining Pis and labeling/tainting nodes.
