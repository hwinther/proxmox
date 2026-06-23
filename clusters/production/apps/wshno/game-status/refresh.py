# Snapshot writer for the public wsh.no game-server widgets. Every INTERVAL seconds it queries the
# in-cluster Prometheus (read-only) for a small, fixed set of A2S series and writes /data/status.json,
# which the nginx sidecar serves. This is the ONLY thing that ever touches Prometheus — the browser
# only sees the curated JSON, so neither Prometheus nor Grafana is exposed.
#
# Game-agnostic: one copy of this script backs every <game>-status Deployment. GAME selects the
# series; SERVER_NAME sets the display name; METRICS_FLAVOR picks how up/players are sourced —
# "a2s" (default: Valheim/Enshrouded, Steam A2S series) or "satisfactory" (no A2S — a VPS blackbox
# probe for reachability plus the in-cluster satisfactory_* exporter for the rich stats). Adding an
# A2S game needs no code change here; a genuinely different metrics shape adds one builder below.
#
# Prometheus is reached via its in-cluster ClusterIP service (PROM_URL env). A matching ingress allow
# on the Prometheus pod (observability-production/networkpolicies.yaml) is required — its default
# ingress only permits host/remote-node/world, not in-cluster pods. Stdlib only — no pip install.
import json
import os
import time
import urllib.parse
import urllib.request

PROM = os.environ["PROM_URL"].rstrip("/")
OUT = "/data/status.json"
GAME = os.environ.get("GAME", "valheim")
FLAVOR = os.environ.get("METRICS_FLAVOR", "a2s")  # a2s | satisfactory
SERVER = os.environ.get("SERVER_NAME", GAME.capitalize())
WINDOW = int(os.environ.get("WINDOW_SECONDS", str(24 * 3600)))
STEP = int(os.environ.get("STEP_SECONDS", "300"))
INTERVAL = int(os.environ.get("INTERVAL_SECONDS", "60"))


def _get(path, params):
    url = f"{PROM}{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.load(r)


def instant(expr):
    res = _get("/api/v1/query", {"query": expr})["data"]["result"]
    return float(res[0]["value"][1]) if res else None


def series(expr, now):
    res = _get(
        "/api/v1/query_range",
        {"query": expr, "start": now - WINDOW, "end": now, "step": STEP},
    )["data"]["result"]
    return [[int(float(t)), round(float(v), 2)] for t, v in res[0]["values"]] if res else []


def build_a2s(now):
    # Valheim/Enshrouded: Steam A2S series from the VPS a2s-exporter, selected by {app="<GAME>"}.
    sel = '{app="%s"}' % GAME
    return {
        "server": SERVER,
        "updated": now,
        "up": instant(f"a2s_server_up{sel}"),
        "players": instant(f"a2s_server_players{sel}"),
        "maxPlayers": instant(f"a2s_server_max_players{sel}"),
        "history": {
            "players": series(f"a2s_server_players{sel}", now),
            "up": series(f"a2s_server_up{sel}", now),
        },
    }


def build_satisfactory(now):
    # Satisfactory has no Steam A2S. "up" = the VPS blackbox TCP probe of the public game port
    # (probe_success — same public-path meaning as the A2S games' a2s_server_up). Players/tech tier
    # come from the in-cluster exporter sidecar's token-gated satisfactory_* metrics (null until the
    # API-token Secret is set). max() collapses any transient duplicate series during a pod roll.
    up = 'max(probe_success{app="%s",probe_origin="vps-external"})' % GAME
    return {
        "server": SERVER,
        "updated": now,
        "up": instant(up),
        "players": instant("max(satisfactory_connected_players)"),
        "maxPlayers": instant("max(satisfactory_player_limit)"),
        "techTier": instant("max(satisfactory_tech_tier)"),
        "history": {
            "players": series("max(satisfactory_connected_players)", now),
            "up": series(up, now),
        },
    }


BUILDERS = {"a2s": build_a2s, "satisfactory": build_satisfactory}


def build():
    return BUILDERS[FLAVOR](int(time.time()))


def main():
    while True:
        try:
            snap = build()
            tmp = OUT + ".tmp"
            with open(tmp, "w") as f:
                json.dump(snap, f, separators=(",", ":"))
            os.replace(tmp, OUT)  # atomic — nginx never serves a half-written file
            print(f"snapshot ok: game={GAME} up={snap['up']} players={snap['players']}", flush=True)
        except Exception as e:  # keep the last good file; just log and retry
            print(f"snapshot error: {e}", flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
