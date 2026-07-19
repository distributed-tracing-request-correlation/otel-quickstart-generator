# otel-quickstart-generator

A CLI scaffolder that generates a complete, working OpenTelemetry tracing setup
for a given language, framework and backend. It writes real files — an SDK
bootstrap, framework instrumentation wiring, a dependency manifest, a
`.env.example`, a Docker Compose stack with an OpenTelemetry Collector, a
collector pipeline configuration, a log-correlation snippet and a short setup
guide — that you drop into your project and run.

It exists because the first hour with OpenTelemetry is nearly always spent on
the same handful of decisions: which exporter package, which propagator, where
the tracer provider is built, why the worker exports nothing after a fork, and
what a collector pipeline should actually contain. Those answers are the same
every time. This tool writes them down for your particular combination, with
the reasoning left in the comments rather than stripped out.

The generated code targets current OpenTelemetry APIs. There are no
Jaeger-native exporters anywhere in it: those were removed from the SDKs, and
Jaeger ingests OTLP directly now.

## Contents

- [What it generates](#what-it-generates)
- [Supported matrix](#supported-matrix)
- [Installation](#installation)
- [Usage](#usage)
- [Every option](#every-option)
- [Worked example: FastAPI + Grafana Tempo](#worked-example-fastapi--grafana-tempo)
- [Other examples](#other-examples)
- [How it works internally](#how-it-works-internally)
- [Design decisions in the generated code](#design-decisions-in-the-generated-code)
- [Limitations](#limitations)
- [Development](#development)
- [Further reading](#further-reading)
- [License](#license)

## What it generates

Per target, in the output directory:

| File | What it is |
|---|---|
| SDK bootstrap | Tracer provider, resource attributes, sampler, batch span processor, exporter, W3C TraceContext + Baggage composite propagator, graceful shutdown |
| Instrumentation wiring | Framework-specific: `FastAPIInstrumentor`, `DjangoInstrumentor`, the Node `instrumentations` array, a Spring servlet filter, `otelhttp`/`otelgrpc` helpers |
| Log correlation | A logging setup that stamps `trace_id`/`span_id` onto every record, in the hex form backends index on |
| Dependency manifest | `requirements-otel.txt`, `package.otel.json`, `pom-otel.xml` or `go.mod.snippet` |
| `.env.example` | Every `OTEL_*` variable that matters, annotated |
| `docker-compose.yml` | Collector plus the chosen backend, where one can run locally |
| `otel-collector-config.yaml` | Receivers, `memory_limiter` → `resource` → `batch`, exporters |
| `OTEL_SETUP.md` | A short guide for whoever picks the directory up next |

Each generated file carries a header comment linking to the one article that
explains the concept it implements — the FastAPI wiring points at the FastAPI
instrumentation article, the collector config at the processor-configuration
article, and so on.

## Supported matrix

| Language | Frameworks |
|---|---|
| Python 3.9+ | `fastapi`, `django`, `flask`, `celery`, `script` |
| Node.js 18+ | `express`, `fastify`, `nestjs`, `plain` |
| Java 17+ | `spring-boot-agent`, `spring-boot-manual` |
| Go 1.22+ | `net-http`, `grpc` |

| Backend | Notes |
|---|---|
| `otlp-grpc` | Generic OTLP over gRPC, port 4317 |
| `otlp-http` | Generic OTLP over HTTP/protobuf, port 4318 |
| `jaeger` | Jaeger all-in-one with native OTLP ingest, UI on 16686 |
| `tempo` | Grafana Tempo plus Grafana with the data source pre-provisioned |
| `honeycomb` | OTLP with the ingest key as a header |
| `datadog` | OTLP into the Datadog Agent's receiver |
| `console` | stdout only; no network, no credentials |

13 targets × 7 backends = 91 combinations, all of them tested.

`python -m otelgen --list-targets` prints the same table with descriptions.

## Installation

This tool is not published to PyPI. Clone it and run it from source.

```bash
git clone https://github.com/distributed-tracing-request-correlation/otel-quickstart-generator.git
cd otel-quickstart-generator
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Requires Python 3.10 or newer. The only runtime dependency is Jinja2; PyYAML
and pytest are used by the test suite.

Run it from the clone, pointing `--out` at wherever you want the files:

```bash
python -m otelgen --out ~/projects/checkout-api/otel-quickstart ...
```

## Usage

### Interactive

Run it with no arguments and it asks five questions:

```
$ python -m otelgen

otel-quickstart-generator
Answer five questions and get a working tracing setup. Enter accepts the default.

Language
 * 1) python               Python
   2) node                 Node.js
   3) java                 Java
   4) go                   Go
choice [1]:
```

It then prompts for framework, backend, service name and sampling, asks whether
you want a collector and a Compose file, and writes the result.

### Non-interactive

```bash
python -m otelgen \
  --language python \
  --framework fastapi \
  --backend tempo \
  --service-name checkout-api \
  --sampling head:0.1 \
  --out ./otel-quickstart
```

### Preview without writing

```bash
python -m otelgen -l go -f grpc -b jaeger -s ledger-svc --dry-run
```

`--dry-run` prints the file tree it would write, and a unified diff for every
file that already exists with different content.

## Every option

| Flag | Default | Meaning |
|---|---|---|
| `--list-targets` | | Print the supported matrix and exit |
| `--language`, `-l` | *required* | `python`, `node`, `java`, `go` |
| `--framework`, `-f` | *required* | See the matrix above |
| `--backend`, `-b` | *required* | Where spans are sent |
| `--service-name`, `-s` | *required* | The `service.name` resource attribute |
| `--service-version` | `0.1.0` | The `service.version` resource attribute |
| `--environment` | `development` | The `deployment.environment.name` attribute |
| `--sampling` | `parentbased` | `always_on`, `always_off`, `parentbased` or `head:<ratio>` |
| `--out`, `-o` | `otel-quickstart` | Output directory |
| `--with-collector` / `--no-collector` | with | Export through a local collector, or straight to the backend |
| `--with-compose` / `--no-compose` | with | Generate `docker-compose.yml` |
| `--dry-run` | off | Print the tree and diffs, write nothing |
| `--force` | off | Overwrite existing files |

Notes:

- **Service names** are validated: letters, digits, dot, dash and underscore,
  1–63 characters. Everything downstream keys on this attribute, so a typo is
  worth catching at generation time.
- **`--sampling head:0.1`** generates a `ParentBased(TraceIdRatioBased(0.1))`
  sampler, not a bare ratio sampler. The parent-based wrapper is what stops a
  trace from being recorded in one service and dropped in the next.
- **`--no-collector`** points the application straight at the backend and, for
  managed backends, moves the credential from the collector config into the
  application's environment.
- **`--backend console`** implies no collector and no Compose file: there is
  nothing to run.
- Without `--force`, an existing file is never touched; the run fails and lists
  what is in the way.

## Worked example: FastAPI + Grafana Tempo

Verbatim, from a clean directory:

```console
$ python -m otelgen --language python --framework fastapi --backend tempo \
    --service-name checkout-api --sampling head:0.1 --out ./otel-quickstart

otel-quickstart/
|-- .env.example  (2,298 bytes)
|-- OTEL_SETUP.md  (4,496 bytes)
|-- docker-compose.yml  (1,955 bytes)
|-- grafana/provisioning/datasources/tempo.yaml  (1,251 bytes)
|-- otel-collector-config.yaml  (2,334 bytes)
|-- otel/__init__.py  (677 bytes)
|-- otel/instrumentation.py  (2,422 bytes)
|-- otel/logging_setup.py  (3,308 bytes)
|-- otel/tracing.py  (4,972 bytes)
|-- requirements-otel.txt  (1,212 bytes)
`-- tempo.yaml  (1,283 bytes)

Python / FastAPI -> Grafana Tempo
  service     checkout-api v0.1.0 (development)
  export      OTLP/grpc via the local collector -> http://localhost:4317
  sampling    head-based, 0.1 of root traces sampled
  files       11

Next: read otel-quickstart/OTEL_SETUP.md
```

### `otel/tracing.py` (head of the generated file)

```python
"""OpenTelemetry tracing bootstrap for checkout-api.

Call :func:`configure_tracing` exactly once, as early in process startup as
possible and before any instrumented library is imported and used.

Exporter: Grafana Tempo via the local OpenTelemetry Collector.
Sampling: head-based, 0.1 of root traces sampled.

Generated by otel-quickstart-generator.
Background reading: https://www.distributed-tracing.com/sdk-implementation-context-propagation/opentelemetry-sdk-setup-for-backend-services/step-by-step-opentelemetry-python-sdk-integration/
"""

from __future__ import annotations

import atexit
import os
from typing import Any

from opentelemetry import trace
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
)
from opentelemetry.sdk.trace.sampling import (
    ParentBased,
    Sampler,
    TraceIdRatioBased,
)
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "checkout-api")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.1.0")
DEPLOYMENT_ENVIRONMENT = os.getenv("DEPLOYMENT_ENVIRONMENT", "development")
OTLP_ENDPOINT = os.getenv(
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://localhost:4317"
)
```

and the sampler it generated for `head:0.1`:

```python
def _build_sampler() -> Sampler:
    """Head-based sampling: keep 0.1 of root traces.

    ``ParentBased`` guarantees the decision made by the caller is honoured, so a
    trace is never half-recorded across services. Only root spans consult the
    ratio.
    """
    ratio = float(os.getenv("OTEL_TRACES_SAMPLER_ARG", "0.1"))
    return ParentBased(root=TraceIdRatioBased(ratio))
```

### `otel/instrumentation.py`

```python
def instrument(app: Any) -> Any:
    """Instrument a FastAPI application and the outbound HTTP client.

    Returns the app so it can be used inline.
    """
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls=EXCLUDED_URLS,
        # Record the matched route template ("/orders/{order_id}") rather than
        # the raw path, keeping span names low-cardinality.
        server_request_hook=_server_request_hook,
    )
    RequestsInstrumentor().instrument()
    logger.info("opentelemetry instrumentation installed for FastAPI")
    return app
```

### `docker-compose.yml`

```yaml
# Local tracing stack for checkout-api: an OpenTelemetry Collector plus Grafana Tempo.
#
#   docker compose up -d
#
# checkout-api itself stays outside the stack and sends spans to
# http://localhost:4317 on the host.
# Traces land in Grafana Tempo: http://localhost:3000

name: checkout-api-tracing

services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.117.0
    container_name: checkout-api-collector
    command: ["--config=/etc/otelcol/config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otelcol/config.yaml:ro
    ports:
      - "4317:4317"   # OTLP/gRPC
      - "4318:4318"   # OTLP/HTTP
      - "13133:13133" # health check
    depends_on:
      - tempo
    healthcheck:
      test: ["CMD", "/otelcol-contrib", "--help"]
      interval: 10s
      timeout: 5s
      retries: 3
    restart: unless-stopped

  tempo:
    image: grafana/tempo:2.7.0
    container_name: checkout-api-tempo
    command: ["-config.file=/etc/tempo/tempo.yaml"]
    user: "0:0"
    volumes:
      - ./tempo.yaml:/etc/tempo/tempo.yaml:ro
      - tempo-data:/var/tempo
    ports:
      - "3200:3200"   # Tempo HTTP API, queried by Grafana
    restart: unless-stopped

  grafana:
    image: grafana/grafana:11.5.1
    container_name: checkout-api-grafana
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Admin
      - GF_AUTH_DISABLE_LOGIN_FORM=true
      - GF_FEATURE_TOGGLES_ENABLE=traceqlEditor
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - grafana-data:/var/lib/grafana
    ports:
      - "3000:3000"   # Grafana, with Tempo pre-provisioned as a data source
    depends_on:
      - tempo
    restart: unless-stopped

volumes:
  tempo-data:
  grafana-data:
```

### `otel-collector-config.yaml` (pipeline section)

```yaml
processors:
  # Refuses new data before the process runs out of memory. Without it, a
  # backend outage turns into a collector OOM kill and you lose everything.
  memory_limiter:
    check_interval: 1s
    limit_percentage: 80
    spike_limit_percentage: 20

  # Adds identity for spans that arrive without it.
  resource:
    attributes:
      - key: collector.name
        value: checkout-api-collector
        action: insert
      - key: deployment.environment.name
        value: development
        action: insert

  # Always last. Batching is what makes export efficient; a collector without
  # it does one network round trip per span.
  batch:
    send_batch_size: 8192
    send_batch_max_size: 10000
    timeout: 5s
```

### Running it

```bash
cd otel-quickstart
pip install -r requirements-otel.txt
cp .env.example .env
docker compose up -d
```

Then, in the application:

```python
from fastapi import FastAPI

from otel import configure_logging, configure_tracing
from otel.instrumentation import instrument

configure_tracing()
configure_logging()

app = FastAPI()
instrument(app)
```

One request later, Grafana on `http://localhost:3000` has the trace, and the
application's own log lines carry the matching ID:

```json
{"timestamp": "2026-01-09T10:12:44+0000", "level": "INFO", "logger": "app",
 "message": "fetching order", "service.name": "checkout-api",
 "trace_id": "5596c3921034c3891bfa8b424ea8f527",
 "span_id": "2cd2b748743ff00a", "order.id": "42"}
```

## Other examples

Go gRPC service against Jaeger, no collector in between:

```bash
python -m otelgen -l go -f grpc -b jaeger -s ledger-svc --no-collector
```

Spring Boot with the Java agent, exporting to Honeycomb:

```bash
python -m otelgen -l java -f spring-boot-agent -b honeycomb -s billing \
  --environment production --sampling head:0.05
```

Node.js Express, printing spans to the terminal — the fastest way to see
whether instrumentation is working at all:

```bash
python -m otelgen -l node -f express -b console -s edge-api
node --require ./otel-quickstart/otel/tracing.js ./src/server.js
```

A Celery worker, where the tracer provider has to be built after the fork:

```bash
python -m otelgen -l python -f celery -b tempo -s order-worker
```

## How it works internally

```
otelgen/
├── cli.py          argument parsing, interactive prompts, output formatting
├── spec.py         the validated Spec: target, backend, sampling, endpoints
├── presets.py      static tables: languages, frameworks, backends, articles,
│                   and the file plan for each target
├── renderer.py     Jinja2 environment, rendering, writing, dry-run diffs
└── templates/
    ├── common/     .env.example, collector config, compose, tempo, setup guide
    ├── python/     bootstrap, logging, requirements, one wiring file per framework
    ├── node/       bootstrap, logging, package snippet, one wiring file per framework
    ├── java/       pom snippet, logback config, agent script, SDK config, filter
    └── go/         bootstrap, logging, go.mod snippet, net/http and gRPC wiring
```

The flow is deliberately linear:

1. `cli.py` collects raw strings, from flags or from prompts.
2. `spec.build_spec` validates them and returns a frozen `Spec`. Everything
   derived — the endpoint, whether TLS is off, which protocol the application
   speaks, whether a credential belongs in the application or in the collector —
   is a property on that object, computed once.
3. `presets.plan_files(spec)` returns the list of `(template, output path,
   article)` triples for the target, skipping files that make no sense for it
   (no collector config for the console exporter, no `tempo.yaml` unless the
   backend is Tempo).
4. `renderer.render(spec)` renders every template into an in-memory
   `{path: content}` mapping. Nothing touches the disk during rendering, which
   is what makes `--dry-run` and the test suite straightforward.
5. `renderer.write_files` writes the mapping, refusing to clobber anything
   unless `--force` was passed.

Jinja2 runs with `StrictUndefined`, so a typo in a template variable is a hard
error at generation time rather than a blank in the output.

The library is usable directly:

```python
from otelgen import build_spec, render

spec = build_spec(
    language="python",
    framework="fastapi",
    backend="tempo",
    service_name="checkout-api",
    sampling="head:0.1",
)
files = render(spec)          # {"otel/tracing.py": "...", ...}
print(spec.traces_endpoint)   # http://localhost:4317
```

## Design decisions in the generated code

A few choices are made consistently across every target, because they are the
ones that most often go wrong:

- **Composite propagator, always.** `traceparent` plus `baggage`. Registering
  only trace context is a common omission, and the symptom — baggage that
  silently never arrives — looks nothing like the cause. See
  [W3C TraceContext propagation](https://www.distributed-tracing.com/distributed-tracing-fundamentals-architecture/understanding-w3c-tracecontext-propagation/).
- **Batch span processor with an explicit shutdown path.** Whatever is in the
  queue when the process exits is lost unless something flushes it, so every
  target wires up an exit hook: `atexit` in Python, signal handlers in Node,
  `destroyMethod = "close"` in Spring, a returned `shutdown` function in Go.
- **Parent-based sampling.** Ratio sampling without the parent-based wrapper
  produces traces that are recorded by one service and dropped by the next.
- **Both `deployment.environment.name` and `deployment.environment`.** The
  attribute was renamed; backends are at different points in adopting it.
- **Health endpoints excluded.** They are polled every few seconds and their
  spans carry no information, but they do carry cost.
- **Low-cardinality span names.** Route templates, not concrete paths — the
  Spring filter renames its span after Spring has matched a handler, and the Go
  handler uses the `ServeMux` pattern.
- **Credentials follow the topology.** With a collector, the backend key lives
  in the collector config; without one, it moves into the application's
  environment. It is never written into a generated source file.

## Limitations

- **Traces only.** No metrics or logs pipelines. The `.env.example` sets
  `OTEL_METRICS_EXPORTER=none` and `OTEL_LOGS_EXPORTER=none` deliberately;
  switching them on is a one-line change but the wiring is not generated.
- **Head-based sampling only.** Tail-based sampling belongs in the collector and
  needs a topology decision (a single collector instance, or a load-balancing
  exporter in front of several) that a scaffolder should not make for you. See
  [head-based vs tail-based sampling](https://www.distributed-tracing.com/distributed-tracing-fundamentals-architecture/choosing-between-head-based-and-tail-based-sampling/).
- **The Compose stacks are development stacks.** In-memory Jaeger storage,
  local-disk Tempo blocks, anonymous Grafana. None of it is a production
  deployment.
- **Java assumes Maven and Spring Boot 3** (`jakarta.*`, not `javax.*`). Gradle
  users can transcribe `pom-otel.xml`; the code itself is framework-independent
  apart from the servlet filter.
- **Dependency versions are floors, not pins.** The generated manifests use
  ranges. The instrumentation packages in every ecosystem move faster than the
  stable API, so pin them yourself once you have a working combination.
- **Generated code is a starting point.** Datastore, message-queue and cache
  instrumentation is listed in the manifests but commented out; add what you
  actually use.
- **No `git init`, no package registry.** The tool is run from a clone.

## Development

```bash
pip install -r requirements.txt
python -m pytest -q
```

The suite renders all 91 combinations and checks that:

- every planned file is written and non-empty;
- generated Python parses with `ast.parse`;
- generated YAML and JSON parse with `yaml.safe_load` and `json.loads`;
- generated JavaScript passes `node --check` when node is available, and a
  string-aware bracket balance check when it is not;
- generated Java and Go have balanced brackets;
- no unrendered Jinja syntax and no `TODO` markers survive into the output;
- the collector pipeline puts `memory_limiter` first and `batch` last, and
  every exporter referenced by a pipeline is actually configured;
- no deprecated Jaeger-native exporter is referenced anywhere;
- every link points at a real article path, and each generated file carries
  exactly one.

`node`, `go` and `javac` are not required; the checks that need them skip
cleanly.

CI runs the same suite on Python 3.10 through 3.13 — see
`.github/workflows/ci.yml`.

## Further reading

The generated files link to the article that explains what they do. The
starting points:

- [OpenTelemetry SDK setup for backend services](https://www.distributed-tracing.com/sdk-implementation-context-propagation/opentelemetry-sdk-setup-for-backend-services/)
- [Instrumenting web frameworks with OpenTelemetry](https://www.distributed-tracing.com/sdk-implementation-context-propagation/instrumenting-web-frameworks-with-opentelemetry/)
- [OpenTelemetry Collector pipeline configuration](https://www.distributed-tracing.com/sdk-implementation-context-propagation/opentelemetry-collector-pipeline-configuration/)
- [Correlating logs, metrics and traces](https://www.distributed-tracing.com/trace-debugging-and-signal-correlation/correlating-logs-metrics-and-traces/)
- [Jaeger vs Tempo vs Zipkin: a decision guide](https://www.distributed-tracing.com/distributed-tracing-fundamentals-architecture/trace-storage-backend-comparison-jaeger-vs-tempo/jaeger-vs-tempo-vs-zipkin-decision-guide/)

## License

MIT — see [LICENSE](LICENSE).
