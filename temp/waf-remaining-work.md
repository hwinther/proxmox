# WAF / edge tuning — remaining work (handoff 2026-06-11 ~01:30)

Status: NAXSI enforcing on the `*.wsh.no` location (public hosts). Whitelists for the OIDC
params (`redirect_uri`, `iss`, `rd`, `post_logout_redirect_uri`, BODY variant for the token
endpoint) and internal rule 11 are in and verified. Last observed blocks: cookie rules at
01:25 on auth.wsh.no.

## 1. Whitelist queue — verify each renders (`nginx -T | grep 'wl:'`)

| # | Issue | Fix (Naxsi WAF Rule, Basic Rule + Whitelist) | Status |
|---|---|---|---|
| 1 | Cookie header scores on random session tokens → **intermittent login failures** (ids 1002 `0x`, 1007 `--`, 1016 `#` seen 01:25 on auth.wsh.no) | IDs `1002,1003,1004,1005,1006,1007,1008,1009,1010,1011,1013,1015,1016,1017`, **Search in specific HTTP Header** = `cookie` | applied? — blocks still seen 01:25, may predate Apply. Re-test login, re-check stream |
| 2 | HA OAuth uses URL as client id → 1101 in ARGS+BODY (`/auth/authorize`, `/auth/token`) | IDs `1100,1101`, specific **GET** arg `client_id` AND specific **POST** arg `client_id` | applied? verify HA login clean |
| 3 | OTLP traces blocked, id 2 "big request" (`/v1/traces` on clutterstock/test/preview, last seen 01:14) | ID `2`, tick "Search in any POST Argument and in Body", **Restrict to URL** `/v1/traces` | NOT rendering as of 01:14 — check `nginx -T \| grep 'wl:2'` |
| 4 | id 11 "uncommon content-type" (HA `login_flow`, SignalR negotiate) | ID `11`, BODY zone, no URL restriction | ✅ silent since 01:18; if it recurs, also tick "Search in Raw Body" |

Watchlist (only act if they block *alone* after #1 lands): `code_challenge` (1007, `--` in
base64url) and `state` (1009, `=`) in ARGS — partial scores, under threshold once cookies
stop scoring.

GUI gotchas (full detail in private-apps `infra/crowdsec-vps/README.md`):
comma-separate IDs; never tick "Use Regular Expressions" on a whitelist (renders invalid
config, fails nginx -t); the word "OIDC" in Description silently prevents rendering;
whitelists are location-global — policy membership is just the rendering vehicle.

## 2. Verification pass (after queue is applied)

Full click-through, then check `{service_name="opnsense"} |= "NAXSI_FMT"` in Grafana Explore:

- Authelia: login (incl. password with `' ( ) ; , # =` — test account, see §3), full OIDC
  round-trip to clutterstock, logout
- Home Assistant: native login, forwardauth bounce
- Node-RED: forwardauth bounce + **deploy a flow** (big JSON body — untested!)
- test.test.wsh.no: chat hub (SignalR), traces flowing again
- SQLi canary still blocks: `curl "https://www.wsh.no/?q=1'%20union%20select"`

## 3. Housekeeping

- [ ] **Turn OFF Extensive NAXSI Log on `*.wsh.no`** once tuning settles — EXLOG writes
      matched values; cookie-rule hits put **live session cookies into Loki (90d)**.
      Consider Loki delete-API cleanup of existing EXLOG lines containing cookie values.
- [ ] Decide whitelist home: keep all in OBVIOUS RFI (works, junk-drawer) vs. dedicated
      "WAF whitelists" policy (tidier, one inert CheckRule). Then record in runbook.
- [ ] Delete the dead GitHub webhook → `coolify.wsh.no/webhooks/source/github/events`
      (GitHub repo/org Settings → Webhooks; source was 140.82.115.161, blocked by WAF).
- [ ] `cscli decisions list` on OPNsense — confirm own IP (83.108.60.20) not banned after
      all the deliberate triggers.
- [ ] Verify edge-sdr routing post-consolidation: OPNsense server_name must be
      `*.edge-sdr.wsh.no` (was exact `edge-sdr.wsh.no` in the 2026-06-10 dump → app hosts
      fell through to production upstream). Test an edge-sdr hostname end-to-end.
- [ ] abyss cleanup (private-apps `infra/abyss-nginx/README.md` step 5): remove old site
      files if not done, `certbot delete --cert-name c.wsh.no` once nothing references it.

## 3b. GeoIP attack map (built 2026-06-11, needs secret before push)

Option A implemented in the public repo (uncommitted): OTel collector `transform/source-ip`
(extracts attacker IP from NAXSI + nginx access lines) → `geoip` processor (GeoLite2-City,
fetched by an init container) → `geo_*` structured metadata in Loki; dashboard gained a
Geomap panel + top-countries table (panels 14/15).

**Before pushing**: create the MaxMind secret, or the collector pod will hang in Init and
take the logs pipeline down — see `maxmind-geoip-secrets.md` (free account → license key →
`kubectl -n observability-production create secret generic maxmind-license
--from-literal=license-key='...'`).

After push: trigger a NAXSI event, check the line in Explore has `geo_country_iso_code`
structured metadata, map populates. Only events ingested after the change carry geo data.

## 3c. fail2ban collection (built 2026-06-11, needs host-side deploys)

- abyss: redeploy `private-apps/infra/crowdsec-vps/fluent-bit.conf` (adds /var/log/fail2ban.log
  input, job=fail2ban host=abyss — also fixes the remove_keys/logfile JSON-wrap issue) +
  `systemctl restart fluent-bit`.
- dns-master (10.31.0.3): fresh fluent-bit install per `private-apps/infra/dns-master-logs/README.md`
  (fail2ban + optional BIND logs; check where named actually logs first; allow outbound :30080).
- public repo: `{job="fail2ban"}` added to Loki 90d retention_stream; dashboard panels 16/17
  (bans by host/jail + event log).
- Optional later: fail2ban-prometheus-exporter on both hosts for live banned-per-jail gauges.

## 3d. CrowdSec detections on the map (built 2026-06-11, needs abyss redeploy)

The agent's "Ip X performed scenario" detection lines are already in Loki (job=crowdsec from
abyss) but lacked geo. Added a parser + geoip2 filter to abyss fluent-bit to enrich them;
dashboard panels 18/19 (CrowdSec detections map + top countries). Only origin=crowdsec local
detections map — the 28k CAPI community-blocklist bans are counts-only, not mapped (low value:
generic global list, same for everyone).

Host-side (abyss): copy `fluent-bit.conf` + `parsers-crowdsec.conf` to /etc/fluent-bit/,
download GeoLite2-City.mmdb to /var/lib/fluent-bit/ (same MaxMind key as the cluster geoip),
verify the geoip2 plugin exists (`fluent-bit --help | grep geoip`), restart. Detail in
`private-apps/infra/crowdsec-vps/README.md` §Fluent Bit. This redeploy ALSO picks up the
fail2ban input (3c) and the earlier remove_keys/logfile JSON-wrap fix.

## 4. Repo state (uncommitted / held)

- **proxmox (public)**: `prometheusrule-crowdsec.yaml` staged change — CrowdsecBanSpike
  threshold 50 → 150/h (calibrated against ~35/h background, ~105/h scanner gusts).
  **Deliberately held** — user wants to watch how NAXSI feeding CrowdSec changes trigger
  volume first. SMART rule restructure already committed.
- **private-apps**: uncommitted — `infra/crowdsec-vps/README.md` (NAXSI tuning + syslog
  paths + GUI pitfalls sections), `infra/abyss-nginx/` (consolidated site conf + runbook),
  OPNsense IP correction (10.20.13.1).
- Cosmetic, optional: abyss fluent-bit crowdsec stream wraps lines in JSON
  (`{"logfile":...,"log":...}`) — the deployed conf lacks the `remove_keys logfile` fix
  from `infra/crowdsec-vps/fluent-bit.conf`; redeploy that file to get raw lines.

## 5. Quick reference

- NAXSI stream: `{service_name="opnsense"} |= "NAXSI_FMT"` (label via OTel collector,
  NodePort 30514/udp); access logs same stream, tag `nginx:`; error logs tag `nginx-error`
  via syslog-ng drop-in `/usr/local/etc/syslog-ng.conf.d/nginx-error-otel.conf`
- Dashboard: Grafana **Edge Security** (`edge-security`); rule-ID table = whitelist
  shopping list
- Render check on OPNsense: `nginx -T | grep 'wl:'`
