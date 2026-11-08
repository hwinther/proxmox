# sdr-debug-edge-sdr

On-demand **sdr-toolbox** pods for testing and debugging the edge RTL-SDR dongles, and for trying
other SDR work (433/868 MHz ISM with `rtl_433`, pagers with `multimon-ng`, `rtl_power` scans). The
image (`ghcr.io/hwinther/wsh-rtl-sdr/sdr-toolbox`, Debian, uid 65532) has rtl-sdr, rtl_433,
multimon-ng, hackrf/airspy/SoapySDR, readsb, AIS-catcher, sox, socat, curl, jq and python3 + numpy.

The two CronJobs, `sdr-toolbox-ais` and `sdr-toolbox-adsb`, are **suspended** and never run on a
schedule. They are templates. A Job made from one requests that dongle from the device plugin
(`sdr.wsh.no/rtlsdr-ais` / `sdr.wsh.no/rtlsdr-adsb`), so the pod is unprivileged with no hostPath.
It stays Pending until the decoder releases the dongle.

## Use

```bash
# 1. Free the dongle. Flux scales the decoder back to 1 within ~10 min; the new pod then waits
#    (Pending) until the toolbox Job is gone, and starts by itself afterwards.
kubectl -n ais-catcher-edge-sdr scale deploy/ais-catcher --replicas=0     # AIS dongle
kubectl -n adsb-edge-sdr scale deploy/readsb --replicas=0                 # ADS-B dongle

# 2. Start a toolbox Job on that dongle and open a shell.
kubectl -n sdr-debug-edge-sdr create job --from=cronjob/sdr-toolbox-ais ism-test
kubectl -n sdr-debug-edge-sdr wait --for=condition=Ready pod -l job-name=ism-test --timeout=5m
kubectl -n sdr-debug-edge-sdr exec -it job/ism-test -- bash

#    e.g.  rtl_test -t
#          rtl_433 -f 868.3M -s 1024k -F json
#          rtl_433 -f 433.92M -M level
#          rtl_power -f 400M:450M:25k -i 10 -1 /home/sdr/scan.csv

# 3. Done: delete the Job. The decoder takes the dongle back.
kubectl -n sdr-debug-edge-sdr delete job ism-test
```

If the Job is forgotten, the pod exits on its own after 8 hours (exit 0, so no KubeJobFailed), and
the Job is removed 10 minutes later. `/home/sdr` is a 2 GiB emptyDir for recordings. Copy files out
with `kubectl cp` before deleting the Job.

The AIS and ADS-B antennas are tuned for 162 MHz and 1090 MHz, so reception elsewhere is weaker;
nearby 433/868 MHz sensors still decode.

A third dongle: add its serial as a new group in `sdr-device-plugin-edge-sdr` (e.g.
`sdr.wsh.no/rtlsdr-ism`) and a third CronJob here, so testing no longer stops a decoder.
