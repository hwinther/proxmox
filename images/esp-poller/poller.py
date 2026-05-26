"""Poll DIY ESP devices over HTTP and republish their readings.

Two sinks, both optional:
  - MQTT with Home Assistant Discovery (auto-creates entities in HA).
  - Prometheus /metrics endpoint (scraped by kube-prometheus-stack).

Each physical device exposes one or more HTTP endpoints. By default an endpoint
must return a JSON object whose keys match the sensor `key`s declared in
devices.yaml (e.g. {"temperature": 21.3, ...}).

For endpoints that pack multiple readings into one string field, set a `parser`
block with `source` (the JSON key holding the string) and `regex` (a Python
regex whose named groups become sensor values). Example:

  parser:
    source: value
    regex: '^(?P<temperature>\\d+)c(?P<humidity>\\d+)$'
"""

from __future__ import annotations

import json
import logging
import os
import re
import signal
import sys
import time
from dataclasses import dataclass
from typing import Any

import paho.mqtt.client as mqtt
import requests
import yaml
from prometheus_client import Gauge, start_http_server

LOG = logging.getLogger("esp-poller")


@dataclass(frozen=True)
class Sensor:
    key: str
    unit: str
    device_class: str | None = None  # omit from HA Discovery when None


@dataclass(frozen=True)
class Parser:
    source: str  # JSON key whose string value the regex is applied to
    regex: re.Pattern[str]  # named groups → sensor values


@dataclass(frozen=True)
class Endpoint:
    id: str  # used in MQTT state topic + log lines
    url: str
    sensors: tuple[Sensor, ...]
    parser: Parser | None = None


@dataclass(frozen=True)
class Device:
    id: str
    name: str
    endpoints: tuple[Endpoint, ...]
    model: str = "esp"


def load_devices(path: str) -> list[Device]:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    out: list[Device] = []
    for d in raw["devices"]:
        endpoints: list[Endpoint] = []
        for ep in d["endpoints"]:
            parser: Parser | None = None
            if "parser" in ep:
                parser = Parser(source=ep["parser"]["source"], regex=re.compile(ep["parser"]["regex"]))
            endpoints.append(
                Endpoint(
                    id=ep["id"],
                    url=ep["url"],
                    sensors=tuple(Sensor(**s) for s in ep["sensors"]),
                    parser=parser,
                )
            )
        out.append(
            Device(
                id=d["id"],
                name=d["name"],
                model=d.get("model", "esp"),
                endpoints=tuple(endpoints),
            )
        )
    return out


def extract(ep: Endpoint, payload: Any) -> dict[str, float]:
    """Turn the raw HTTP response into {sensor_key: numeric_value}."""
    if ep.parser is None:
        if not isinstance(payload, dict):
            raise ValueError(f"endpoint {ep.id}: response is not a JSON object")
        return {s.key: float(payload[s.key]) for s in ep.sensors if s.key in payload}
    if not isinstance(payload, dict):
        raise ValueError(f"endpoint {ep.id}: parser set but response is not a JSON object")
    raw = payload.get(ep.parser.source)
    if not isinstance(raw, str):
        raise ValueError(f"endpoint {ep.id}: parser source '{ep.parser.source}' is not a string")
    m = ep.parser.regex.match(raw)
    if m is None:
        raise ValueError(f"endpoint {ep.id}: regex did not match {raw!r}")
    return {k: float(v) for k, v in m.groupdict().items() if v is not None}


# ---- MQTT --------------------------------------------------------------------


def mqtt_connect() -> mqtt.Client | None:
    host = os.getenv("MQTT_HOST")
    if not host:
        LOG.info("MQTT_HOST not set, skipping MQTT sink")
        return None
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=os.getenv("MQTT_CLIENT_ID", "esp-poller"),
    )
    user = os.environ["MQTT_USER"]
    password = os.environ["MQTT_PASS"]
    client.username_pw_set(user, password)
    client.connect(host, int(os.getenv("MQTT_PORT", "1883")), keepalive=60)
    client.loop_start()
    return client


def state_topic(dev: Device, ep: Endpoint) -> str:
    return f"homelab/esp/{dev.id}/{ep.id}/state"


def publish_discovery(client: mqtt.Client, dev: Device) -> None:
    """Send retained HA Discovery configs — one per sensor — so HA auto-creates entities.

    All sensors share the same `device.identifiers` so HA groups them under one device card,
    even though their state topics differ per endpoint.
    """
    device_block = {
        "identifiers": [dev.id],
        "name": dev.name,
        "manufacturer": "DIY",
        "model": dev.model,
    }
    for ep in dev.endpoints:
        for s in ep.sensors:
            cfg: dict[str, Any] = {
                "name": f"{dev.name} {s.key.replace('_', ' ').title()}",
                "unique_id": f"{dev.id}_{s.key}",
                "state_topic": state_topic(dev, ep),
                "value_template": f"{{{{ value_json.{s.key} }}}}",
                "unit_of_measurement": s.unit,
                "state_class": "measurement",
                "device": device_block,
            }
            if s.device_class is not None:
                cfg["device_class"] = s.device_class
            topic = f"homeassistant/sensor/{dev.id}/{s.key}/config"
            client.publish(topic, json.dumps(cfg), retain=True, qos=1)


# ---- Prometheus --------------------------------------------------------------

_GAUGES: dict[str, Gauge] = {}


def _gauge(key: str, unit: str) -> Gauge:
    g = _GAUGES.get(key)
    if g is None:
        g = Gauge(f"esp_{key}", f"{key} reported by ESP devices (unit: {unit})", ["device"])
        _GAUGES[key] = g
    return g


def export_metrics(dev: Device, ep: Endpoint, values: dict[str, float]) -> None:
    for s in ep.sensors:
        v = values.get(s.key)
        if v is not None:
            _gauge(s.key, s.unit).labels(device=dev.id).set(v)


# ---- Main loop ---------------------------------------------------------------


def poll_once(dev: Device, ep: Endpoint, mqtt_client: mqtt.Client | None, timeout: float) -> None:
    r = requests.get(ep.url, timeout=timeout)
    r.raise_for_status()
    values = extract(ep, r.json())
    # Always republish a flat numeric dict so HA Discovery's
    # `value_template: {{ value_json.<key> }}` works whatever the upstream shape was.
    if mqtt_client is not None:
        mqtt_client.publish(state_topic(dev, ep), json.dumps(values), qos=0)
    export_metrics(dev, ep, values)


def main() -> int:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    devices_path = os.getenv("DEVICES_PATH", "/etc/esp-poller/devices.yaml")
    interval = float(os.getenv("POLL_INTERVAL_SEC", "30"))
    http_timeout = float(os.getenv("HTTP_TIMEOUT_SEC", "5"))
    metrics_port = int(os.getenv("METRICS_PORT", "9100"))

    devices = load_devices(devices_path)
    endpoint_count = sum(len(d.endpoints) for d in devices)
    LOG.info("loaded %d device(s), %d endpoint(s) from %s", len(devices), endpoint_count, devices_path)

    start_http_server(metrics_port)
    LOG.info("metrics on :%d/metrics", metrics_port)

    client = mqtt_connect()
    if client is not None:
        for dev in devices:
            publish_discovery(client, dev)
        LOG.info("published HA Discovery for %d device(s)", len(devices))

    stop = False

    def _sigterm(*_: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _sigterm)
    signal.signal(signal.SIGINT, _sigterm)

    while not stop:
        for dev in devices:
            for ep in dev.endpoints:
                try:
                    poll_once(dev, ep, client, http_timeout)
                except Exception as e:
                    LOG.warning("poll %s/%s failed: %s", dev.id, ep.id, e)
        # Sleep in small slices so SIGTERM stops within ~1s instead of waiting a full interval.
        slept = 0.0
        while not stop and slept < interval:
            time.sleep(min(1.0, interval - slept))
            slept += 1.0

    if client is not None:
        client.loop_stop()
        client.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
