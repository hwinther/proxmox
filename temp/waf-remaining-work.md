# WAF / edge — open items (trimmed 2026-07-16; history in git)

NAXSI enforcing on `*.wsh.no` via OPNsense nginx; abyss VPS (80.240.128.197) fronts everything.
Whitelist queue COMPLETE (8 rules: cookie header, HA client_id, OTLP /v1/traces, content-type 11,
`error_description`, `error_hint`, `/api/client-log` BODY, and Node-RED `/flows` BODY|NAME — all in
the OBVIOUS RFI policy).
GeoIP map, fail2ban (abyss + dns-master), CrowdSec geo enrichment, and the CrowdsecBanSpike
150/h threshold are all deployed and verified flowing in Loki. GUI gotchas (tokenfield commas,
policy membership mandatory, no "OIDC" in descriptions, never regex, **Clone an existing rule to
keep its ID chips**) live in private-apps `infra/crowdsec-vps/README.md`.

## Open

- [x] ~~Turn OFF Extensive NAXSI Log~~ — verified OFF on ALL 9 HTTP servers 2026-07-16
      (`naxsi_extensive_log: "0"` via `/api/nginx/settings/get`). Old June EXLOG lines with
      cookie values live in the opnsense 90d stream until ~Sept, but those sessions are expired
      (12h session / 1-month remember-me) — letting them age out; Loki delete-API purge optional.
- [x] ~~edge-sdr server_name~~ — config now shows wildcard `*.edge-sdr.wsh.no` (2026-07-16).
      End-to-end test with a real edge-sdr app hostname still worthwhile at next opportunity.
- [ ] abyss cleanup (private-apps `infra/abyss-nginx/README.md` step 5): remove old site files,
      `certbot delete --cert-name c.wsh.no` once nothing references it.
- [ ] Delete the dead GitHub webhook → `coolify.wsh.no/webhooks/source/github/events`
      (GitHub repo/org Settings → Webhooks). Related: dead Coolify-era vhosts
      (`*.ct1/*.r1/*.r2.wsh.no`, e.g. `g48oocgskcs8owscg8800w08.ct1`) still catch scanner
      sweeps (NAXSI ids 2/14) — remove stale server_names/DNS when convenient.
- [ ] Whitelist home: everything sits in OBVIOUS RFI (works, junk-drawer) vs. a dedicated
      "WAF whitelists" policy (tidier). Cosmetic; decide whenever.

## Watch

- **abyss static-403 layer**: a hostile-looking POST body (SQL comment `--` etc.) gets a static
  "Request Blocked" 403 page from abyss BEFORE reaching OPNsense (nginx/1.18.0, ETag = static
  file; page/rule NOT in the private-apps mirror — identify where it's configured if a legit
  payload ever hits it). Realistic app payloads pass — verified 2026-07-16 with
  `/api/client-log` end-to-end (204 + X-Skylens-Api).
- ~~Node-RED flow deploy (big JSON body) was never explicitly WAF-tested~~ — it failed 2026-08-10
  and is now fixed. `POST /flows` tripped **id 1000** ("sql keywords") twice in `BODY|NAME`:
  node property names `areaSelector` and `deviceSelector` both contain the substring **"select"**,
  4+4 = score 8 = block. Whitelisted with `BasicRule wl:1000 "mz:$URL:/flows|BODY|NAME";`
  (rule "node red flow deploy key names", in OBVIOUS RFI). Scoped to the NAME zone rather than to
  those two variable names on purpose — Node-RED node property names are arbitrary, so
  `updateRate`/`fromDate`/`tableView` etc. would each re-trip it. Values on `/flows` are still
  inspected; only JSON keys are exempt. First whitelist here that is `BODY|NAME`-shaped rather
  than `$ARGS_VAR`.

## Quick reference

- NAXSI stream: `{service_name="opnsense"} |= "NAXSI_FMT"` (Loki NodePort :30080,
  `X-Scope-OrgID: foo`); access logs same stream tag `nginx:`; geo via structured metadata
  (`geo_country_iso_code`).
- Dashboard: Grafana **Edge Security** (`edge-security`); rule-ID table = whitelist shopping list.
- Render check on OPNsense: `nginx -T | grep 'wl:'`; deny page is **HTTP 200** — test by body
  (`Request Denied For Security`), not status. SQLi canary:
  `curl "https://www.wsh.no/?q=1'%20union%20select"`.
