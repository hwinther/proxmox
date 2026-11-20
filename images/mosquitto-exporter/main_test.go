package main

import (
	"testing"

	"github.com/prometheus/client_golang/prometheus"
	dto "github.com/prometheus/client_model/go"
)

// The metric names are what dashboards and alerts query, so they must stay exactly as upstream
// produced them.
func TestProcessUpdateMetricNames(t *testing.T) {
	updates := map[string]string{
		"$SYS/broker/clients/connected":           "7",
		"$SYS/broker/uptime":                      "12345 seconds",
		"$SYS/broker/bytes/received":              "1024",
		"$SYS/broker/load/messages/received/1min": "2.50",
		"$SYS/broker/messages/stored":             "3",
		"$SYS/broker/version":                     "mosquitto version 2.0.20",
		"$SYS/broker/clients/active":              "1",
		"$SYS/broker/publish/messages/dropped":    "0",
		"$SYS/broker/heap/current size":           "1048576 bytes",
		"$SYS/broker/load/publish/sent/15min":     "0.00",
	}
	for topic, payload := range updates {
		processUpdate(topic, payload)
	}

	families, err := prometheus.DefaultGatherer.Gather()
	if err != nil {
		t.Fatalf("gather: %v", err)
	}
	got := map[string]*dto.MetricFamily{}
	for _, f := range families {
		got[f.GetName()] = f
	}

	want := map[string]struct {
		typ   dto.MetricType
		value float64
	}{
		"broker_clients_connected":           {dto.MetricType_GAUGE, 7},
		"broker_uptime":                      {dto.MetricType_COUNTER, 12345},
		"broker_bytes_received":              {dto.MetricType_COUNTER, 1024},
		"broker_load_messages_received_1min": {dto.MetricType_GAUGE, 2.5},
		"broker_messages_stored":             {dto.MetricType_GAUGE, 3},
		"broker_publish_messages_dropped":    {dto.MetricType_COUNTER, 0},
		"broker_heap_current_size":           {dto.MetricType_GAUGE, 1048576},
		"broker_load_publish_sent_15min":     {dto.MetricType_GAUGE, 0},
	}
	for name, w := range want {
		f, ok := got[name]
		if !ok {
			t.Errorf("metric %s missing", name)
			continue
		}
		if f.GetType() != w.typ {
			t.Errorf("metric %s: type %v, want %v", name, f.GetType(), w.typ)
		}
		m := f.GetMetric()[0]
		var v float64
		if w.typ == dto.MetricType_COUNTER {
			v = m.GetCounter().GetValue()
		} else {
			v = m.GetGauge().GetValue()
		}
		if v != w.value {
			t.Errorf("metric %s: value %v, want %v", name, v, w.value)
		}
	}
	for _, ignored := range []string{"broker_version", "broker_clients_active"} {
		if _, ok := got[ignored]; ok {
			t.Errorf("metric %s should be ignored", ignored)
		}
	}
}
