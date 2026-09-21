# LogicMonitor collector path for NOVALI rc88

NOVALI stays collector-first in rc85.

Rules:

- telemetry is evidence only
- LogicMonitor does not control NOVALI
- controller authority and review gates remain unchanged
- no portal credentials, access IDs, access keys, bearer tokens, cookies, or OTLP header values belong in this repo

Recorded proof chain:

- rc83 established live collector proof
- rc83.1 aligned service name, mapping, and protocol diagnostics
- rc83.2 proved Dockerized NOVALI runtime export to the collector
- rc83.2 portal trace visibility remains operator-confirmed after collector config correction
- rc85 carries a sanitized packaged confirmation snapshot so clean handoffs can preserve that proof without secrets or API access
- rc88 adds local operator-alert readiness mapping docs without adding LogicMonitor API integration

LogicMonitor-safe proof identity:

- preferred proof service name: `novalioperatorshell`
- runtime default remains `novali-operator-shell`
- shell status warns when the runtime service name may be unsafe for LogicMonitor search/display

Mapping attributes:

- `NOVALI_LM_HOST_NAME`
- `NOVALI_LM_IP`
- `NOVALI_LM_RESOURCE_TYPE`
- `NOVALI_LM_RESOURCE_GROUP`

Merged resource attributes:

- `host.name=<value>`
- `ip=<value>`
- `resource.type=<value>`
- `resource.group=<optional>`
- `service.namespace=novali`
- `service.name=<selected service name>`

Protocol guidance:

- host proof
  - HTTP: `http://localhost:4318`
  - gRPC: `http://localhost:4317`
- Dockerized proof
  - `same_network`
    - gRPC: `http://<collector-container-name>:4317`
    - HTTP: `http://<collector-container-name>:4318`
  - `host_gateway` or `host_published`
    - gRPC: `http://host.docker.internal:4317`
    - HTTP: `http://host.docker.internal:4318`
  - `custom`
    - exact `RC83_2_LMOTEL_ENDPOINT` value, shown in status as a hint only

Key docs:

- `observability/logicmonitor/dockerized_agent_probe.md`
- `observability/logicmonitor/portal_verification_checklist.md`
- `observability/logicmonitor/alerts/`

Important limits:

- LogicMonitor does not become a governance authority in rc88
- rc88 does not call LogicMonitor APIs
- rc88 does not create LogicMonitor alerts by API
- rc88 acceptance does not depend on live LogicMonitor reachability
- the packaged confirmation snapshot is historical proof evidence, not a live runtime health signal
