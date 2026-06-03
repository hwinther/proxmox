# SDR base debug (edge-sdr)

Disposable **debug / development** pod on **radio-pi02** running the **trixie** SDR base image
(`ghcr.io/hwinther/wsh-rtl-sdr/sdr-base:0.4.0-trixie`). Unlike the feeders this is the *base*
image with no service — it just `sleep infinity` so you can `kubectl exec` in and run the SDR
tooling by hand against the USB radio.

## Scheduling (hardware)

Pinned to **radio-pi02** by `nodeSelector kubernetes.io/hostname=radio-pi02` plus a toleration for
the edge taint `node-type=edge-sdr:NoSchedule`. This deliberately bypasses the
`role=sdr-edge` + antenna-label scheme the feeders use, so production feeders on radio-pi01 are
never disturbed. radio-pi02 must be a joined worker with the edge taint — see
[raspberry-pi-worker.md](../../../../infra/k0s/raspberry-pi-worker.md).

## USB / privileged access

`privileged: true` + `hostPath /dev/bus/usb` give the pod raw access to the USB SDR. The
[PolicyException](kyverno-policyexception-hostpath.yaml) exempts it from `wsh-disallow-host-path`,
matching the [ais-catcher](../ais-catcher-edge-sdr/) pattern.

## Use it

```bash
kubectl -n sdr-base-debug-edge-sdr exec -it deploy/sdr-base-debug -- bash

# inside the pod — confirm the radio is visible, then smoke-test:
lsusb
rtl_test -t
```

## Bumping the image

Edit the tag + digest in [deployment.yaml](deployment.yaml). Base images are published from the
`hwinther/wsh-rtl-sdr` repo as `0.4.0-<debian-release>` (trixie / bookworm / bullseye / buster).

## Teardown

Remove the `- sdr-base-debug-edge-sdr` line from [../kustomization.yaml](../kustomization.yaml)
(Flux prunes the namespace and pod), or scale to 0 for a quick pause.
