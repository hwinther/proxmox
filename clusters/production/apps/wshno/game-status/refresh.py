# Snapshot writer for the public wsh.no game-server widgets. Every INTERVAL seconds it queries the
# in-cluster Prometheus (read-only) for a small, fixed set of A2S series and writes /data/status.json,
# which the nginx sidecar serves. This is the ONLY thing that ever touches Prometheus — the browser
# only sees the curated JSON, so neither Prometheus nor Grafana is exposed.
#
# Game-agnostic: one copy of this script backs every <game>-status Deployment. The game is selected
# by the GAME env (-> the `{app="<GAME>"}` series selector); SERVER_NAME sets the display name. So
# adding a game is just another Deployment with GAME/SERVER_NAME set — no code change here.
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
WINDOW = int(os.environ.get("WINDOW_SECONDS", str(24 * 3600)))
STEP = int(os.environ.get("STEP_SECONDS", "300"))
INTERVAL = int(os.environ.get("INTERVAL_SECONDS", "60"))
SEL = '{app="%s"}' % GAME


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


def build():
    now = int(time.time())
    return {
        "server": os.environ.get("SERVER_NAME", GAME.capitalize()),
        "updated": now,
        "up": instant(f"a2s_server_up{SEL}"),
        "players": instant(f"a2s_server_players{SEL}"),
        "maxPlayers": instant(f"a2s_server_max_players{SEL}"),
        "history": {
            "players": series(f"a2s_server_players{SEL}", now),
            "up": series(f"a2s_server_up{SEL}", now),
        },
    }


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
