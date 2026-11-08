import json

from prometheus_client import CollectorRegistry, generate_latest

from app.exporter import WindowsCollector, build_script, parse_output, parse_targets

SAMPLE = {
    "computername": "WIN11-LAB",
    "cpu": 42.0,
    "mem_total": 8 * 1024**3,
    "mem_free": 2 * 1024**3,
    "uptime": 3600,
    "disks": [{"volume": "C:", "size": 100.0, "free": 25.0}],
    "services": [
        {"name": "Spooler", "exists": True, "running": True},
        {"name": "W32Time", "exists": True, "running": False},
    ],
}


def scrape(collector):
    registry = CollectorRegistry()
    registry.register(collector)
    return generate_latest(registry).decode()


def test_parse_targets():
    assert parse_targets("100.64.3.7=WIN11, 10.0.0.5") == [("100.64.3.7", "WIN11"), ("10.0.0.5", "10.0.0.5")]


def test_build_script_inserts_services():
    script = build_script(["Spooler", "W32Time"])
    assert "'Spooler,W32Time'" in script
    assert "__SERVICES__" not in script


def test_parse_output_handles_powershell_51_array_format():
    raw = json.dumps({**SAMPLE, "disks": {"value": SAMPLE["disks"], "Count": 1}, "services": SAMPLE["services"][0]})
    data = parse_output("﻿" + raw)
    assert data["disks"] == SAMPLE["disks"]
    assert data["services"] == [SAMPLE["services"][0]]


def test_metrics_when_host_responds():
    collector = WindowsCollector([("100.64.3.7", "WIN11-LAB")], "u", "p", ["Spooler"], query_fn=lambda host: SAMPLE)
    out = scrape(collector)
    assert 'windows_up{host="100.64.3.7",hostname="WIN11-LAB"} 1.0' in out
    assert 'windows_cpu_usage_percent{host="100.64.3.7",hostname="WIN11-LAB"} 42.0' in out
    assert 'windows_disk_free_bytes{host="100.64.3.7",hostname="WIN11-LAB",volume="C:"} 25.0' in out
    assert 'windows_service_running{host="100.64.3.7",hostname="WIN11-LAB",service="W32Time"} 0.0' in out


def test_metrics_when_host_is_down():
    def fail(host):
        raise ConnectionError("timeout")

    out = scrape(WindowsCollector([("100.64.3.7", "WIN11-LAB")], "u", "p", ["Spooler"], query_fn=fail))
    assert 'windows_up{host="100.64.3.7",hostname="WIN11-LAB"} 0.0' in out
    assert "windows_cpu_usage_percent{" not in out