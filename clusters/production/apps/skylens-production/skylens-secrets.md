# skylens secrets & prerequisites

`skylens-api` needs an MQTT login for the in-cluster broker, several third-party enrichment API
credentials (aircraft: OpenSky, ADSBExchange, AeroAPI; maritime: BarentsWatch AIS + the separate
FiskInfo "extended" client), and the home feed coordinates. None of these are committed to git — they
all live in the `skylens-secrets` Secret, consumed via `envFrom` in `deployment.yaml`.

## `skylens-secrets` Secret (create out-of-band)

```bash
kubectl -n skylens-production create secret generic skylens-secrets \
  --from-literal=MQTT__USERNAME='skylens' \
  --from-literal=MQTT__PASSWORD='<mosquitto skylens password>' \
  --from-literal=OPENSKY__CLIENTID='<opensky-oauth2-client-id>' \
  --from-literal=OPENSKY__CLIENTSECRET='<opensky-oauth2-client-secret>' \
  --from-literal=ADSBX__RAPIDAPIKEY='<rapidapi-key>' \
  --from-literal=AEROAPI__APIKEY='<flightaware-aeroapi-key>' \
  --from-literal=BarentsWatch__ClientId='<barentswatch-oauth2-client-id>' \
  --from-literal=BarentsWatch__ClientSecret='<barentswatch-oauth2-client-secret>' \
  --from-literal=FiskInfo__ClientId='<barentswatch-extended-oauth2-client-id>' \
  --from-literal=FiskInfo__ClientSecret='<barentswatch-extended-oauth2-client-secret>' \
  --from-literal=FEED__LAT='<home-latitude>' \
  --from-literal=FEED__LON='<home-longitude>' \
  --from-literal=FEED__RADIUSKM='300'
```

`MQTT__USERNAME` is fixed to `skylens` (matches the passwd-file user). The non-secret config
(`MQTT__HOST/PORT/TOPIC`, `Oidc__*`, `ADSBX__RAPIDAPIHOST`, budgets, `OTEL_*`) is set as plain env
in `deployment.yaml`, not here.

| Key | Required | Where it comes from |
| --- | -------- | ------------------- |
| `MQTT__USERNAME` | yes | Fixed value `skylens` (the mosquitto passwd-file user). |
| `MQTT__PASSWORD` | yes | The `skylens` password generated in the mosquitto passwd file — see [mosquitto-secrets.md](../mosquitto-production/mosquitto-secrets.md). Same value on both sides. |
| `OPENSKY__CLIENTID` | yes | OpenSky Network account → API portal → **OAuth2 API client** (client-credentials). OpenSky moved off HTTP Basic to OAuth2; this is the client id. |
| `OPENSKY__CLIENTSECRET` | yes | The matching OAuth2 client secret from the OpenSky API portal. |
| `ADSBX__RAPIDAPIKEY` | yes | RapidAPI account subscribed to the **ADSBExchange** API (host `adsbexchange-com1.p.rapidapi.com`); the `X-RapidAPI-Key`. |
| `AEROAPI__APIKEY` | yes | FlightAware **AeroAPI** portal → API key (used for on-tap route lookups only). |
| `BarentsWatch__ClientId` | no | BarentsWatch developer portal → OAuth2 client-credentials client (scope `ais`). Powers vessel away-mode + `/api/vessels/{mmsi}` enrichment (NLOD-licensed official Norwegian AIS). Unset = away-mode returns empty and detail falls back to the local feed — safe to deploy without. |
| `BarentsWatch__ClientSecret` | no | The matching BarentsWatch client secret. |
| `FiskInfo__ClientId` | no | A **second, separate** BarentsWatch OAuth2 client-credentials client — the "extended" API (scope `api`, not `ais`). Powers the fishing layers: `/api/fishing/zones` (cod boundaries / forbidden / zero areas), `/api/fishing/lost-gear`, and NOR/NIS ship-register enrichment folded into `/api/vessels/{mmsi}`. Unset = those endpoints return `200` with an empty list + a `fiskinfo-unconfigured` note (the map layers degrade to "nothing to show") — safe to deploy without. |
| `FiskInfo__ClientSecret` | no | The matching client secret for the extended (FiskInfo) client. |
| `FEED__LAT` | yes | Home feed latitude. **Intentionally secret** (repo convention: precise home coordinates never go in git). |
| `FEED__LON` | yes | Home feed longitude. **Intentionally secret** — same reason. |
| `FEED__RADIUSKM` | yes | Home coverage radius in km (default `300`); beyond this the gateway falls back to ADSBx away-mode. |

The non-secret FiskInfo config (`Scope: api`, `BaseUrl: https://www.barentswatch.no/bwapi`,
`DailyBudget: 500`) ships as defaults in `appsettings.json` — only the two credential keys go in the
Secret. The client fails **closed**: over budget / token failure / upstream error yields an empty
result with a reason, never a throw.

### Activating FiskInfo on an already-running deployment

The Secret already exists, so add just the two keys without disturbing the rest (a strategic-merge
patch on `stringData` is base64-encoded and merged server-side, leaving every other key intact):

```bash
kubectl -n skylens-production patch secret skylens-secrets --type merge -p '{"stringData":{
  "FiskInfo__ClientId":"<extended-client-id>",
  "FiskInfo__ClientSecret":"<extended-client-secret>"}}'
```

`envFrom` only reads the Secret at pod start, so roll the deployment to pick the new keys up:

```bash
kubectl -n skylens-production rollout restart deployment/skylens-api
```

Then confirm from the app (the `/api/fishing/*` endpoints are JWT-gated, so verify signed-in): the
fishing-zone / lost-gear layers populate and the `fiskinfo-unconfigured` note disappears.

## Satellites domain (no secrets)

The satellite overlay's data sources are **keyless** — there is nothing to add to `skylens-secrets`.
The backend fetches TLE/GP orbital data from **CelesTrak** and radio-transmitter metadata from
**SatNOGS** over anonymous HTTPS; neither has or needs an API key. In Development/previews these are
replaced by baked fixtures (`Satellites__TleFile` / `Satellites__TransmittersFile`, see the preview
`base/deployment.yaml`); Production fetches live with the `appsettings.json` defaults. SatNOGS data
is licensed **CC BY-SA**, and the required attribution is shown in the app UI / README.

## mosquitto `skylens` user

The broker runs `allow_anonymous false` + `password_file`. Add a `skylens` user to that passwd file
(the `MQTT__PASSWORD` above must equal the password you set there) — see
[mosquitto-secrets.md](../mosquitto-production/mosquitto-secrets.md). The matching broker-side
network allow is in `../mosquitto-production/cilium-mqtt-ingress.yaml`.

## Container image visibility

`deployment.yaml` references `ghcr.io/hwinther/skylens/api` with **no `imagePullSecrets`**, matching
clutterstock's public-package convention. Make that GHCR package **public**, or — if you keep it
private — add a `ghcr-pull` clone policy + `imagePullSecrets` (copy the pattern in
`../ddnsadmin/kyverno-clusterpolicies.yaml` and add a `…/ghcr-pull: "true"` namespace label).

## Access

The app is public on `https://skylens.wsh.no` with **no Authelia forward-auth** on the ingress: the
API validates the Authelia OIDC JWT (`aud=skylens-api`) in-app via JwtBearer (the clutterstock /
test-api pattern), and the SignalR hub authenticates via the `?access_token=` query param. Requiring
a valid token is what protects the third-party API quotas from anonymous scraping.
