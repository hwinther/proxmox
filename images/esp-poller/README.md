# esp-poller

Tiny Python poller for DIY ESP8266/ESP32 sensor devices. For each device, on
an interval it:

1. HTTP-GETs a JSON endpoint (`{"temperature": 21.3, "humidity": 45, ...}`).
2. Republishes the payload to MQTT as
   `homelab/esp/<device_id>/state`.
3. Publishes Home Assistant
   [MQTT Discovery](https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery)
   config (retained) on startup so HA auto-creates one entity per sensor.
4. Exports every numeric reading as a Prometheus gauge on `:9100/metrics`
   (label `device=<device_id>`, metric name `esp_<sensor_key>`).

MQTT is optional — unset `MQTT_HOST` to run as a metrics-only exporter.

## Environment

| Var                  | Default                          | Notes                                          |
|----------------------|----------------------------------|------------------------------------------------|
| `DEVICES_PATH`       | `/etc/esp-poller/devices.yaml`   | Device list (ConfigMap)                        |
| `POLL_INTERVAL_SEC`  | `30`                             | Poll cadence                                   |
| `HTTP_TIMEOUT_SEC`   | `5`                              | Per-device GET timeout                         |
| `METRICS_PORT`       | `9100`                           | Prometheus scrape port                         |
| `MQTT_HOST`          | (unset → MQTT disabled)          | e.g. `mosquitto.mosquitto-production.svc.cluster.local` |
| `MQTT_PORT`          | `1883`                           |                                                |
| `MQTT_USER`          | required if `MQTT_HOST` set      |                                                |
| `MQTT_PASS`          | required if `MQTT_HOST` set      |                                                |
| `MQTT_CLIENT_ID`     | `esp-poller`                     |                                                |
| `LOG_LEVEL`          | `INFO`                           |                                                |

## devices.yaml shape

A `device` is a physical thing (one HA device card). Each device has one or more
`endpoints` — HTTP URLs to poll. Default: the endpoint returns a flat JSON object
whose keys match the sensor keys.

```yaml
devices:
  - id: esp_living_room          # MQTT topic prefix + Prometheus `device` label
    name: ESP Living Room        # HA-visible name
    model: esp8266-dht22         # optional, exposed via HA Discovery
    endpoints:
      - id: dht                  # MQTT topic segment + log lines
        url: http://10.20.30.40/api  # returns {"temperature": 21.3, "humidity": 45}
        sensors:
          - {key: temperature, unit: "°C", device_class: temperature}
          - {key: humidity,    unit: "%",  device_class: humidity}
```

If an endpoint packs readings into a single string field, declare a `parser`.
`source` is the JSON key holding the string; `regex` is a Python regex whose
named groups become the sensor values.

```yaml
devices:
  - id: sensor01
    name: Sensor 01
    endpoints:
      - id: dht11
        url: http://10.20.1.142:8080/api/sensor01/dht11/value  # → {"value": "25c26"}
        parser:
          source: value
          regex: '^(?P<temperature>\d+)c(?P<humidity>\d+)$'
        sensors:
          - {key: temperature, unit: "°C", device_class: temperature}
          - {key: humidity,    unit: "%",  device_class: humidity}
      - id: lightsensor
        url: http://10.20.1.142:8080/api/sensor01/lightsensor/read  # → {"value": "900"}
        parser:
          source: value
          regex: '^(?P<light>\d+)$'
        sensors:
          - {key: light, unit: "raw"}   # device_class is optional — omit if uncalibrated
```

After parsing, the poller always republishes a flat numeric dict to MQTT
(`homelab/esp/<dev_id>/<endpoint_id>/state`), so HA Discovery's
`value_template: {{ value_json.<key> }}` works the same way for both shapes.
All sensors from all endpoints on a device share `device.identifiers`, so HA
groups them under one device card.

`device_class` values come from
[HA's sensor device classes](https://www.home-assistant.io/integrations/sensor/#device-class).

Sensor `key` must be unique *across all endpoints of a device* — HA's
`unique_id` and the Prometheus metric name are derived from it. If a device
has two temperature probes, give them distinct keys
(e.g. `temperature` for the DHT11 and `dsb_temperature` for a DS18B20).

## Local run

```bash
pip install -r requirements.txt
DEVICES_PATH=./devices.yaml python poller.py
```
