# MonitoringIT

Platforma służąca do monitorowania Windows Serwera z Ubuntu.

- windows-exporter -> aplikacja w pythonie, która co 30s łączy się z WS poprzez WINRM i odczytuje CPU, RAM, Dyski oraz stan usług

- Prometheus zapisuje metryki i sprawdza reguły alertów

- Alertmanager wysyła alerty na Discorda

- Grafana pokazuje dashboard "Monitoring serwera Windows"

# Adresy

Grafana - http://100.64.3.8:3000
Prometheus - http://100.64.3.8:9090
Alertmanager - http://100.64.3.8:9093
Exporter - http://100.64.3.8:9182/metrics