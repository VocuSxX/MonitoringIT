import json
import logging
import os
import time
from pathlib import Path

import winrm
from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY, GaugeMetricFamily

log = logging.getLogger("windows-exporter")

PS_TEMPLATE = (Path(__file__).parent / "collect.ps1").read_text(encoding="utf-8")


def parse_targets(spec):
    """'100.64.3.7=WIN11,10.0.0.5=SRV2' -> [('100.64.3.7', 'WIN11'), ('10.0.0.5', 'SRV2')]"""
    targets = []
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        host, _, name = item.partition("=")
        targets.append((host.strip(), name.strip() or host.strip()))
    if not targets:
        raise ValueError("WIN_TARGETS jest puste")
    return targets


def build_script(services):
    return PS_TEMPLATE.replace("__SERVICES__", ",".join(services))


def as_list(value):
    """PowerShell 5.1 czasem zapisuje tablicę jako {"value": [...], "Count": n} albo pojedynczy obiekt."""
    if value is None:
        return []
    if isinstance(value, dict):
        return value.get("value", [value]) if "value" in value else [value]
    return list(value)


def parse_output(raw):
    data = json.loads(raw.strip().lstrip("﻿"))
    data["disks"] = as_list(data.get("disks"))
    data["services"] = as_list(data.get("services"))
    return data


class WindowsCollector:
    def __init__(self, targets, user, password, services, query_fn=None):
        self.targets = targets
        self.user = user
        self.password = password
        self.script = build_script(services)
        self.query_fn = query_fn or self.query_winrm

    def query_winrm(self, host):
        session = winrm.Session(
            f"http://{host}:5985/wsman",
            auth=(self.user, self.password),
            transport="ntlm",
            operation_timeout_sec=10,
            read_timeout_sec=15,
        )
        result = session.run_ps(self.script)
        if result.status_code != 0:
            raise RuntimeError(result.std_err.decode("utf-8", errors="replace")[:500])
        return parse_output(result.std_out.decode("utf-8", errors="replace"))

    def collect(self):
        labels = ["host", "hostname"]
        up = GaugeMetricFamily("windows_up", "1 = dane pobrane przez WinRM, 0 = błąd połączenia", labels=labels)
        duration = GaugeMetricFamily("windows_scrape_duration_seconds", "Czas pobierania danych przez WinRM", labels=labels)
        cpu = GaugeMetricFamily("windows_cpu_usage_percent", "Użycie CPU w procentach (wszystkie rdzenie)", labels=labels)
        mem_total = GaugeMetricFamily("windows_memory_total_bytes", "Całkowita pamięć RAM", labels=labels)
        mem_free = GaugeMetricFamily("windows_memory_free_bytes", "Wolna pamięć RAM", labels=labels)
        uptime = GaugeMetricFamily("windows_uptime_seconds", "Czas od ostatniego uruchomienia systemu", labels=labels)
        disk_size = GaugeMetricFamily("windows_disk_size_bytes", "Rozmiar dysku logicznego", labels=labels + ["volume"])
        disk_free = GaugeMetricFamily("windows_disk_free_bytes", "Wolne miejsce na dysku logicznym", labels=labels + ["volume"])
        svc_running = GaugeMetricFamily("windows_service_running", "1 = usługa działa, 0 = zatrzymana lub nie istnieje", labels=labels + ["service"])

        for host, name in self.targets:
            start = time.monotonic()
            try:
                data = self.query_fn(host)
            except Exception as exc:  # brak połączenia, złe hasło, timeout...
                log.warning("Nie udało się pobrać danych z %s (%s): %s", name, host, exc)
                up.add_metric([host, name], 0)
                duration.add_metric([host, name], time.monotonic() - start)
                continue

            up.add_metric([host, name], 1)
            duration.add_metric([host, name], time.monotonic() - start)
            cpu.add_metric([host, name], float(data["cpu"]))
            mem_total.add_metric([host, name], float(data["mem_total"]))
            mem_free.add_metric([host, name], float(data["mem_free"]))
            uptime.add_metric([host, name], float(data["uptime"]))
            for d in data["disks"]:
                disk_size.add_metric([host, name, d["volume"]], float(d["size"]))
                disk_free.add_metric([host, name, d["volume"]], float(d["free"]))
            for s in data["services"]:
                svc_running.add_metric([host, name, s["name"]], 1 if s["running"] else 0)

        yield from (up, duration, cpu, mem_total, mem_free, uptime, disk_size, disk_free, svc_running)


def read_password():
    path = os.environ.get("WIN_PASSWORD_FILE", "/run/secrets/windows_password")
    return Path(path).read_text(encoding="utf-8").strip()


def main():
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
    targets = parse_targets(os.environ["WIN_TARGETS"])
    services = [s.strip() for s in os.environ.get("WIN_SERVICES", "Spooler,W32Time").split(",") if s.strip()]
    port = int(os.environ.get("LISTEN_PORT", "9182"))

    REGISTRY.register(WindowsCollector(targets, os.environ["WIN_USER"], read_password(), services))
    start_http_server(port)
    log.info("Exporter działa na porcie %s, cele: %s, usługi: %s", port, targets, services)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()