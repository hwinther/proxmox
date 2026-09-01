# Away mode — keep the SDR feed up with everything else powered off

Procedure for extended absences (~3 weeks): power down all Proxmox hosts, OPNsense and the
edge control plane, while **radio-pi01 keeps feeding ADS-B/AIS to the internet**.

Verified 2026-08-29 against the live clusters. Re-check the facts below before relying on it.

## What the feed actually depends on

| Dependency                 | Status                                                                                                       |
| -------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Ceph / Proxmox storage     | **None.** The whole edge cluster has exactly one PVC (`kubescape-storage`, on edge01). No feeder touches it. |
| Feeder placement           | **All on `radio-pi01`.** `radio-pi02` runs only fluent-bit + node-exporter — power it off.                   |
| Default gateway            | `10.20.13.1` (OPNsense) normally; **VLAN 2015 → USG `10.20.15.1`** in away mode. No longer a constraint.     |
| DNS                        | CoreDNS forwards to the _node's_ `/etc/resolv.conf`. Away mode repoints it at the USG `10.20.15.1`.          |
| k0s control plane (edge01) | Not needed in steady state. **Needed to recover from a reboot** — see the risk below.                        |

### Accepted risk

With edge01 down, a reboot of radio-pi01 means kubelet has **no cached pod specs**: the node comes
back with zero containers and stays empty until edge01 returns. Accepted deliberately (power
outages historically unlikely). Feeder-outage email alerts from FlightAware / FR24 are the
detection mechanism — confirm they are enabled before leaving.

The _likelier_ failure is not a power cut but the Pi filling up. As of 2026-08-29 radio-pi01 was at
**81% of its 29G SD card (5.4G free)** and **~297MB RAM available with 175MB of swap already in
use**. kubelet evicts pods below 10% free (~2.9G); with edge01 off, **evicted pods never come
back**. Hence the shutdown list below — it is not optional tidiness.

## Before leaving

1. **Flip the default gateway to the USG**: run `/root/away-mode-gw.sh on` on radio-pi01.
   Verify: `ip -4 route show default` shows `default via 10.20.15.1 dev eth0.2015`.
2. **Stop everything on the Pi whose backend will be dead.** Do this _while edge01 is still up_, so
   kubelet actually terminates the pods.

   ```bash
   K="kubectl --context EdgeSDR"
   # Deployments: park with nodeSelector, NOT `scale --replicas=0` - see the warning below
   for d in adsb-mqtt tar1090; do
     $K -n adsb-edge-sdr patch deploy $d        -p '{"spec":{"template":{"spec":{"nodeSelector":{"away":"true"}}}}}'
   done
   $K -n adsb-edge-sdr delete pod -l app=adsb-mqtt
   $K -n adsb-edge-sdr delete pod -l app=tar1090
   for p in fluent-bit-edge-sdr/fluent-bit \
            node-exporter-edge-sdr/node-exporter-prometheus-node-exporter \
            ceph-csi-edge-sdr/ceph-csi-rbd-nodeplugin; do
     $K -n ${p%%/*} patch ds ${p##*/} \
       -p '{"spec":{"template":{"spec":{"nodeSelector":{"away":"true"}}}}}'
   done
   ```

   | Stopped                   | Why                                                           |
   | ------------------------- | ------------------------------------------------------------- |
   | `fluent-bit`              | ships to Loki (off) — buffers and retries, eats disk + memory |
   | `adsb-mqtt`               | publishes to `10.20.13.100:1883` (off) — retries every 1s     |
   | `node-exporter`           | scraped by prometheus-agent → Prometheus (both off)           |
   | `ceph-csi-rbd-nodeplugin` | Ceph is off                                                   |
   | `tar1090`                 | local web UI, unreachable while away                          |

   > **Do not park Deployments with `scale --replicas=0` — Flux undoes it.** Verified 2026-08-31:
   > both `adsb-mqtt` and `tar1090` were back to `replicas=1` and Running within minutes. `replicas`
   > is declared in git, so Flux owns that field and resets it; `nodeSelector` is not, so an added
   > key survives reconciliation. That is why the DaemonSet patches stick and the scale did not.
   >
   > Deployments also need their pods deleted after patching: with one replica and the default
   > rolling-update strategy the old pod keeps running while the unschedulable replacement sits
   > Pending, so the workload is not actually parked until you evict it.
   >
   > Nothing here is in git, so Flux restores it all on return.

Leaves exactly: `dump1090-fa`, `piaware`, `fr24`, `opensky`, `adsbexchange`, `ais-catcher`.

3. **Move CoreDNS onto radio-pi01 — MANDATORY before powering off edge01.** Both CoreDNS replicas
   live on edge01 (one Running, one permanently Pending because the Pi nodes carry
   `node-type=edge-sdr:NoSchedule` and CoreDNS has no matching toleration). Shut edge01 down as-is
   and every feeder loses its resolver. They coast on already-resolved IPs, then fail silently at
   the first reconnect — and fr24/piaware also need the _cluster_ name `dump1090-fa`.

   Leaving two endpoints is equally bad: with no API server, kube-proxy cannot drop the dead one,
   so roughly half of all DNS queries blackhole with 5s timeouts for the whole absence.

   ```bash
   K="kubectl --context EdgeSDR"
   $K cordon radio-pi02 && $K cordon k0s-prod-edge01.k0s.wsh.no
   $K -n kube-system patch deploy coredns -p '{"spec":{"template":{"spec":{"tolerations":[
     {"key":"node-type","value":"edge-sdr","effect":"NoSchedule","operator":"Equal"},
     {"key":"node-role.kubernetes.io/master","effect":"NoSchedule","operator":"Exists"},
     {"key":"node-role.kubernetes.io/control-plane","effect":"NoSchedule","operator":"Exists"}]}}}}'
   # wait for a replica Running on radio-pi01, then drop the edge01 one
   $K -n kube-system get pods -l k8s-app=kube-dns -o wide -w
   $K -n kube-system delete pod -l k8s-app=kube-dns       --field-selector spec.nodeName=k0s-prod-edge01.k0s.wsh.no
   $K -n kube-system get endpoints kube-dns     # MUST show only a 10.200.2.x address
   ```

   Verify before shutting anything down — query the CoreDNS pod IP directly for one external name
   and one cluster name (`dump1090-fa.adsb-edge-sdr.svc.cluster.local`). Both must answer.

   CoreDNS is a k0s-managed component, so k0s may revert the toleration while edge01 is still up.
   Re-check the pod is Running on radio-pi01 immediately before shutdown; once edge01 is off,
   nothing can revert it.

4. **Free disk headroom on radio-pi01.** There is no `crictl` on the Pi — k0s bundles containerd,
   so use `k0s ctr`. It has no `--prune`, so compute the unused set explicitly (images backing any
   existing container are excluded, so running feeders are never touched):

   ```bash
   k0s ctr -n k8s.io containers ls | awk 'NR>1{print $2}' | sort -u > /tmp/inuse.txt
   k0s ctr -n k8s.io images ls     | awk 'NR>1{print $1}' | sort -u > /tmp/all.txt
   grep -vxF -f /tmp/inuse.txt /tmp/all.txt > /tmp/prune.txt
   wc -l /tmp/prune.txt                      # review before deleting
   xargs -a /tmp/prune.txt -n 15 k0s ctr -n k8s.io images rm --sync
   ```

   Run 2026-08-31: 159 image refs down to 15, **12.54 GiB freed, 80% -> 33% used**. Do this
   _after_ parking the workloads, so their images count as unused and get collected too.

5. **Power off radio-pi02.**
6. **Dress rehearsal — do not skip.** Shut down OPNsense + all Proxmox for ~30 min and confirm the
   feeders still report on the FlightAware / FR24 / OpenSky / ADSBExchange stats pages. This is the
   only real proof the cutover works.

## The UniFi cutover

Superseded 2026-08-31. The Pi no longer depends on OPNsense for internet, so there is **no
takeover of `10.20.13.1` and no IP-conflict dance**.

`eth0` is a trunk: untagged VLAN 1 (no IP, carrier only), tagged **2013** (`10.20.13.21`, k0s
control plane, gw `10.20.13.1`), tagged **2015** (`10.20.15.5`, gw+DNS `10.20.15.1` via the USG).
VLAN 2015 is always up but passive — route metric 500 loses to 2013's 100.

> **Why VLAN 1 and not just "native 2013 + tagged 2015"?** The small UniFi switch the Pi is on
> can only do _either_ a single untagged VLAN _or_ tagged VLANs with native/default tag **1**.
> Native-2013-plus-tagged-2015 is not expressible on that hardware. VLAN 1 therefore exists
> purely as the required native carrier and is deliberately left unaddressed. It does not need
> to be up or routed. Do not "simplify" this away.

**Cut over `radio-pi02` first.** It runs only fluent-bit + node-exporter — both parked for away
mode anyway — and is powered off while away, so a failed cutover there costs nothing. Prove the
switch-port profile and the reboot behaviour on it, then repeat on `radio-pi01`, which carries
every feeder. Both nodes are staged identically, so one port profile applies to both.

Away mode is one command on radio-pi01:

```bash
/root/away-mode-gw.sh on     # USG becomes default gw + primary DNS (metric 50)
/root/away-mode-gw.sh off    # restore OPNsense as default
```

### Proving the USG path works (without flipping anything)

VLAN 2015 stays up permanently, so the away-mode path can be exercised in place — no shutdown,
no route change. Run on radio-pi01 **after** the trunk cutover:

```bash
ip -4 -br addr show eth0.2015          # expect 10.20.15.5/24 (pi01) / .4 (pi02)
ping -c3 -I eth0.2015 10.20.15.1       # USG reachable
curl -sS --interface eth0.2015 -o /dev/null -w '%{http_code}
' https://1.1.1.1   # NAT to WAN
dig +short @10.20.15.1 -b 10.20.15.5 cloudflare.com                               # USG resolves
```

Note the USG **blocks outbound DNS to external resolvers** on this VLAN — `dig @1.1.1.1` times
out. `10.20.15.1` is the only resolver that works here, so do not "improve" `vlan2015-usg` by
pointing it at a public resolver.

Then the feeder endpoints themselves. Verified working over the USG path 2026-08-31:

| Feeder       | Endpoint               |
| ------------ | ---------------------- |
| piaware      | `206.253.80.207:1200`  |
| adsbexchange | `34.215.191.184:30004` |
| opensky      | `194.209.200.41:10004` |
| fr24         | `13.61.217.232:8099`   |
| ais-catcher  | `185.77.96.227:4242`   |

```bash
t() { timeout 8 bash -c "cat < /dev/null > /dev/tcp/$1/$2" 2>/dev/null       && echo "  $3 OPEN" || echo "  $3 BLOCKED"; }
t 206.253.80.207 1200 piaware;      t 34.215.191.184 30004 adsbexchange
t 194.209.200.41 10004 opensky;     t 13.61.217.232  8099  fr24
t 185.77.96.227  4242  ais-catcher
```

> **UDP over the USG path is VERIFIED WORKING (2026-08-31).** An earlier note here claimed it was
> blocked — that was a testing error, corrected below. Confirmed good: NTP/123 3/3 and STUN/3478
> both succeed out `eth0.2015`, returning public IP `88.88.157.110` (vs `83.108.60.20` via
> OPNsense), so the two paths use genuinely different WAN addresses and both NAT correctly.
>
> **Testing gotcha that caused the false alarm — read before re-testing.** Binding a source
> address (`socket.bind(("10.20.15.5", 0))`, `curl --interface <ip>`) does **not** control which
> interface a packet leaves by; the route table still decides. With the default route on
> `eth0.2013`, such probes egress via OPNsense carrying a `10.20.15.5` source and get dropped as
> spoofed — looking exactly like "the USG blocks UDP". Always force the path with
> `SO_BINDTODEVICE` (or `curl --interface eth0.2015`, the device name, not the address):
>
> ```python
> s.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, b"eth0.2015")
> ```
>
> Second trap: a short tcpdump on `eth0.2015` showing outbound UDP with **zero inbound** is not
> evidence of a block. fr24's feed is fire-and-forget UDP, so a 15-second window is legitimately
> one-way. Judge UDP health with a protocol that round-trips (NTP or STUN), never with packet
> counts on the feed itself.

These endpoints are **UDP** and must be verified separately from the TCP list above. Verified
carrying traffic over the USG path 2026-08-31:

| Feeder            | UDP endpoint                   | Identifies station by |
| ----------------- | ------------------------------ | --------------------- |
| fr24 feed         | `13.61.217.232:8099` (blender) | feeder key            |
| piaware / FA MLAT | `206.253.84.200:8182`          | feeder key            |
| MarineTraffic AIS | `5.9.207.224:11661`            | **source IP**         |
| VesselFinder AIS  | `ais.vesselfinder.com:6860`    | **source IP**         |
| ShipXplorer AIS   | `hub.shipxplorer.com:37615`    | **source IP**         |
| AisHub AIS        | `data.aishub.net:2864`         | **source IP**         |
| Community hub AIS | `185.77.96.227:4242` (TCP)     | uuid                  |

> **AIS and the public IP — behaviour differs per aggregator.** The four AIS UDP feeds send plain
> NMEA with no credential in the stream, so an aggregator can only attribute data by source
> address, and away mode changes it (USG `88.88.157.110` vs OPNsense `83.108.60.20`). Observed
> 2026-08-31, ~12 minutes after flipping:
>
> | Service       | Behaviour after the flip                                                                           |
> | ------------- | -------------------------------------------------------------------------------------------------- |
> | MarineTraffic | "last signal" counted back **down** (5 min → 3 min) — re-associated, feed accepted                 |
> | ShipXplorer   | went **offline and stayed offline** (12 min and climbing) — appears to hard-lock the registered IP |
> | VesselFinder  | not observed                                                                                       |
> | AisHub        | not observed                                                                                       |
>
> **The reliable test is direction, not value:** counting _down_ means data is being accepted and
> the station is simply between vessel messages; counting _up_ past ~15 minutes while vessels are
> visible in the local AIS-catcher UI means the feed is being rejected.
>
> Packets are sent either way — a capture on `eth0.2015` shows all four AIS destinations receiving
> traffic regardless, so tcpdump cannot tell you whether a feed is accepted. Inbound UDP is
> likewise near-zero by design: AIS NMEA is one-way, and only fr24 (`13.61.217.232:8099`) and NTP
> reply at all.
>
> **Before a long absence:** register `88.88.157.110` with ShipXplorer (and check whether the USG
> WAN address is static — if the ISP reassigns it mid-absence there is no way to fix it remotely),
> or accept losing that one feed. ADS-B is immune throughout — piaware, fr24 and adsbexchange all
> authenticate with a feeder key.
>
> The transient at the moment of the flip is normal and self-healing: ais-catcher's TCP feeds
> (community hub `185.77.96.227:4242`, MQTT) log `send error 110/104` as connections break on the
> source-address change, then reconnect unaided.

Quick UDP egress check. **Must** use `SO_BINDTODEVICE` — binding only the source address
lets the route table pick the interface, which silently tests the wrong path:

```bash
python3 - <<'PY'
import socket, struct, os
for dev, src, label in (("eth0.2015", "10.20.15.5", "USG"),
                        ("eth0.2013", "10.20.13.21", "OPNsense")):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, dev.encode())
    s.bind((src, 0)); s.settimeout(4)
    try:
        s.sendto(struct.pack("!HHI12s", 1, 0, 0x2112A442, os.urandom(12)),
                 ("18.156.18.133", 3478))
        s.recvfrom(1024); print("  %-9s UDP OK" % label)
    except Exception as e:
        print("  %-9s UDP FAIL (%s)" % (label, type(e).__name__))
    finally:
        s.close()
PY
```

Those IPs drift (DNS round-robin, provider changes). The feeder hostnames and ports are baked
into the images, **not** in the deployment env, so re-derive them from live traffic on
radio-pi01 rather than guessing — guessing produced three false "blocked" results:

```bash
for pid in $(pgrep -f "piaware|fr24|opensky|adsbexchange|AIS-catcher"); do
  nsenter -t $pid -n ss -tn state established 2>/dev/null | awk 'NR>1{print $4}'
done | grep -vE '^(10\.|127\.|192\.168\.)' | sort -u
```

All five passing means away mode will work. This replaces most of the value of the 30-minute
dress rehearsal below — that rehearsal now only proves the _feeders_ tolerate OPNsense being
gone, not the network path.

**The flip is mandatory.** With OPNsense powered off, the metric-100 default via `10.20.13.1`
does not disappear — eth0 is still up, so the route stays installed and blackholes. Nothing
fails over on its own; `away-mode-gw.sh on` is what actually moves traffic.

kubelet's node IP is pinned to `10.20.13.21` via
`/etc/systemd/system/k0sworker.service.d/node-ip.conf`. **Do not remove it** — without it kubelet
re-derives InternalIP from the default-route interface and would register the node as
`10.20.15.5` once the USG takes over, breaking kube-router peering.

## On return

1. **Restore the default gateway**: `/root/away-mode-gw.sh off` on radio-pi01. No ordering
   constraint against OPNsense any more — the VLANs are separate.
2. Power on Proxmox hosts, wait for Ceph to reach health, then OPNsense, then edge01.
3. Flux (on edge01) reconciles and **restores the scaled-down workloads by itself** — the
   `replicas: 0` and `nodeSelector` edits above are runtime-only and are not in git. Verify:

   ```bash
   kubectl --context EdgeSDR get pods -A -o wide | grep radio-pi01   # expect 14 pods
   ```

   If anything is still parked, Flux is suspended or failing to reconcile — check it rather than
   re-patching by hand.

4. **Uncordon both nodes** — they were cordoned to pin CoreDNS, and nothing reschedules until
   this is undone:

   ```bash
   kubectl --context EdgeSDR uncordon radio-pi02 k0s-prod-edge01.k0s.wsh.no
   ```

   k0s will restore the stock CoreDNS deployment on its own; confirm two replicas end up Running.

5. Power radio-pi02 back on.

## See also

- [raspberry-pi-worker.md](raspberry-pi-worker.md) — Pi worker join, log caps, tmpfs sizing
- [network-plan.md](network-plan.md) — VLAN / CIDR model
