# Demo-runbook — live gjennomgang av hjemmelabben

Følgesvenn til `k8s-homelab.html`. Målet er en ~10–15 min live-demo som viser de
samme tingene som lysbildene, i en rekkefølge som forteller én historie:

> **«Jeg pusher en PR → en komplett, isolert kopi av appen ruller ut av seg selv
> → og jeg kan se alt som skjer.»**

Demoen knytter sammen: **PR-preview (Clutterstock) · Flux/Headlamp · Hubble ·
Grafana · Prometheus-varsler · Authelia SSO.**

---

## 0. Før publikum kommer (pre-flight)

- [ ] **Vær på LAN/VPN.** Alle `*.mgmt.wsh.no` peker på interne IP-er og er
      *ikke* tilgjengelige utenfra. Test at sidene lastet under på forhånd.
- [ ] **Logg HELT ut av Authelia** (`https://auth.wsh.no` → logout) — vi vil vise
      selve innloggingen som første steg. Ha brukernavn/passord (+ evt. 2FA) klart.
- [ ] **Ha PR-en klar, men ikke trigget.** Lag branchen og åpne PR-en på
      Clutterstock-repoet på forhånd, men **ikke** sett `deploy-feature`-labelen
      ennå — vi gjør det live. Velg en liten, synlig endring (f.eks. en tekst/farge
      på forsiden) så previewen tydelig skiller seg fra produksjon.
- [ ] **Forhåndsåpne faner** i denne rekkefølgen (alle vil kreve SSO første gang):
      `auth.wsh.no` · GitHub-PR-en · `headlamp.mgmt.wsh.no` ·
      `hubble.mgmt.wsh.no` · `grafana.mgmt.wsh.no` · `alertmanager.mgmt.wsh.no`.
- [ ] **Vit preview-URL-en på forhånd:** `https://clutterstock-pr-<N>.test.wsh.no`
      (sett inn PR-nummeret). Produksjon til sammenligning: `https://clutterstock.wsh.no`.
- [ ] **Timing-tips:** image-bygg + reconcile tar noen minutter. **Trigg previewen
      tidlig** (steg 2), og fyll ventetiden med Headlamp/Hubble/Grafana — avslør den
      ferdige previewen til slutt.

---

## 1. Authelia — «logg inn én gang» (≈1 min)

1. Gå til en beskyttet tjeneste, f.eks. `https://headlamp.mgmt.wsh.no`.
2. Du blir sendt til `auth.wsh.no` — logg inn.
3. Åpne deretter `hubble.mgmt.wsh.no` og `alertmanager.mgmt.wsh.no` → ingen ny
   innlogging.

**Snakkepunkt:** Single sign-on (OIDC + forward-auth) ligger *foran* tjenestene som
ikke har egen innlogging. For Windows-folk: tenk én sentral pålogging à la ADFS,
men håndhevet i ingress-laget (Traefik-middleware) for alt på `*.mgmt.wsh.no`.

---

## 2. Trigg preview-deployen (≈1 min å starte, så ruller den i bakgrunnen)

1. På GitHub-PR-en: legg på labelen **`deploy-feature`**.
2. Vis fanen **Actions** — bygget starter (API/frontend/migrator-images bygges og
   pushes til GHCR med tag `…-pr.<N>` + signeres).
3. Forklar hva som skjer videre *uten* å vente på det:
   - Den gjenbrukbare workflowen `gitops-preview-upsert.yml` fyller ut malene i
     `clusters/production/apps/previews/clutterstock/template/` og committer en
     per-PR-overlay + namespace + en **CNPG Database-CR** til infrastruktur-repoet.
   - **Flux** plukker opp committen og ruller ut previewen.

**Snakkepunkt:** Hele preview-miljøet er *deklarert*, ikke klikket sammen — én label
gir en isolert kopi: eget namespace, egen Postgres-database (`clutterstock_pr<N>`),
egen Valkey-cache, og images låst til digest av Kyverno. La denne bygge mens vi ser
på resten.

---

## 3. Headlamp + Flux — GitOps som skjer foran øynene (≈2–3 min)

1. `https://headlamp.mgmt.wsh.no`.
2. Vis **Flux/GitOps-pluginen**: Kustomizations som reconciler — pek på at klyngen
   trekker fra Git, ikke motsatt.
3. Bytt namespace til **`clutterstock-pr-<N>`** (dukker opp når Flux har reconcilet)
   og vis at podene starter: API, frontend, migrator-job, Valkey.

**Snakkepunkt:** Dette er «klyngen speiler Git» fra lysbildene, helt konkret. Ingen
`kubectl apply` for hånd — det eneste jeg gjorde var å sette en label.

> **Fallback hvis bygget henger:** vis et *eksisterende* namespace
> (`clutterstock-production`) og Flux-reconcile der i stedet — poenget er det samme.

---

## 4. Den levende previewen (≈1 min)

1. Åpne `https://clutterstock-pr-<N>.test.wsh.no`.
2. Vis den lille endringen fra PR-en, og sammenlign med `https://clutterstock.wsh.no`.

**Snakkepunkt:** En komplett, kjørende kopi av appen — egen database og alt — på en
egen URL, kun fordi PR-en finnes. Når PR-en lukkes, rydder Flux opp av seg selv.

---

## 5. Hubble — se trafikken (≈2 min)

1. `https://hubble.mgmt.wsh.no`.
2. Velg namespace **`clutterstock-pr-<N>`**.
3. Vis **service-kartet**: frontend → API → Postgres/Valkey, i sanntid. Klikk inn på
   flows for å vise kilde/mål/port/verdikt (`FORWARDED`).
4. Pek på at default-deny gjelder: bare tillatt trafikk vises som godkjent.

**Snakkepunkt:** eBPF gir denne innsikten gratis — som å ha Wireshark + et
nettverkskart innebygd, uten agenter i hver pod. Hver app har sin egen «brannmur»
(NetworkPolicy); ingenting snakker sammen uten at det er erklært.

---

## 6. Grafana — metrikker & dashboards (≈2 min)

1. `https://grafana.mgmt.wsh.no` (logget inn via Authelia-OIDC).
2. Vis 1–2 dashboards med tydelig verdi, f.eks.:
   - **ASP.NET / OTEL-traces** — requests fra Clutterstock (gjerne fra previewen).
   - **Ceph** eller **Proxmox** — «infrastruktur-helse på ett blikk».
3. Nevn at logger (Loki) og traces (Tempo) henger sammen herfra.

**Snakkepunkt:** PerfMon + Event Viewer + APM samlet, med historikk — på tvers av
hele klyngen, ikke én server om gangen.

---

## 7. Prometheus-varsler (≈2 min)

1. `https://alertmanager.mgmt.wsh.no` — vis hva som er aktivt nå.
   - `Watchdog`-varselet fyrer alltid (by design) → garantert noe å peke på som
     bevis for at varslingskjeden lever.
2. Nevn de egendefinerte reglene i repoet (kilde, ikke nødvendigvis vis YAML live):
   cert-manager-utløp, Ceph-helse, Flux-reconcile, og **netpol-regresjons­detektoren**
   (varsler på økende Hubble `POLICY_DENIED`-drops).
3. Lukk loopen: varsler går til **Telegram** → rett på mobilen.

**Snakkepunkt:** Varsling er også «som kode» — reglene ligger i Git og rulles ut av
Flux, akkurat som appene.

> **Valgfritt (kun hvis trygt og avtalt):** demonstrer et varsel som går fra grønt
> til rødt. Ikke improviser dette live på noe produksjonsnært — forhåndsavtal og
> test på forhånd, ellers hold deg til `Watchdog` + de eksisterende reglene.

---

## 8. Rydd opp / avslutt (≈30 sek)

1. På PR-en: fjern `deploy-feature`-labelen (eller lukk PR-en).
2. Forklar: Flux pruner previewen automatisk — namespace, database og alt forsvinner.
   Ingen etterlatt drift.

**Avslutning:** Knytt tilbake til lysbildene — én label ga oss et komplett miljø med
nettverk, database, observability og sikkerhet, og det ryddes opp av seg selv. Alt
deklarativt, alt i Git.

---

## Hurtigreferanse — URL-er

| Hva | URL | Auth |
|---|---|---|
| Authelia (SSO) | `https://auth.wsh.no` | — |
| Preview-app | `https://clutterstock-pr-<N>.test.wsh.no` | åpen (test-wildcard TLS) |
| Produksjons-app | `https://clutterstock.wsh.no` | per app |
| Headlamp | `https://headlamp.mgmt.wsh.no` | Authelia forward-auth |
| Hubble | `https://hubble.mgmt.wsh.no` | Authelia forward-auth |
| Grafana | `https://grafana.mgmt.wsh.no` | Authelia OIDC |
| Alertmanager | `https://alertmanager.mgmt.wsh.no` | Authelia forward-auth |

> Alt på `*.mgmt.wsh.no` er **LAN-only** — vær på riktig nett/VPN.

## Sjekkliste rett før start

- [ ] På LAN/VPN, alle URL-er lastet OK i forhåndstest
- [ ] Utlogget av Authelia (for å vise SSO-login)
- [ ] PR åpnet, liten synlig endring, men `deploy-feature` IKKE satt enda
- [ ] PR-nummer og preview-URL notert
- [ ] Faner forhåndsåpnet i rekkefølge
