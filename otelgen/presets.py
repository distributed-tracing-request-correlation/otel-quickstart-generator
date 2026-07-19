"""Static tables describing the supported matrix.

Everything that is "just data" lives here: the languages, the frameworks each
language supports, the backends, the article each generated file links to, and
the file plan (which template renders to which output path) for a target.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .spec import Spec

SITE = "https://www.distributed-tracing.com"

#: Named article paths on the site. Only these are ever linked from generated
#: files; see ``tests/test_links.py``, which pins the set.
ARTICLES: dict[str, str] = {
    "tracecontext": (
        "distributed-tracing-fundamentals-architecture/"
        "understanding-w3c-tracecontext-propagation/"
    ),
    "span_lifecycle": (
        "distributed-tracing-fundamentals-architecture/"
        "span-lifecycle-and-parent-child-relationships/"
    ),
    "orphaned_spans": (
        "distributed-tracing-fundamentals-architecture/"
        "span-lifecycle-and-parent-child-relationships/"
        "debugging-orphaned-spans-in-async-workflows/"
    ),
    "sampling": (
        "distributed-tracing-fundamentals-architecture/"
        "choosing-between-head-based-and-tail-based-sampling/"
    ),
    "sampling_cheatsheet": (
        "distributed-tracing-fundamentals-architecture/"
        "choosing-between-head-based-and-tail-based-sampling/"
        "head-based-vs-tail-based-sampling-cheatsheet/"
    ),
    "storage_backends": (
        "distributed-tracing-fundamentals-architecture/"
        "trace-storage-backend-comparison-jaeger-vs-tempo/"
    ),
    "backend_decision_guide": (
        "distributed-tracing-fundamentals-architecture/"
        "trace-storage-backend-comparison-jaeger-vs-tempo/"
        "jaeger-vs-tempo-vs-zipkin-decision-guide/"
    ),
    "security_boundaries": (
        "distributed-tracing-fundamentals-architecture/"
        "security-boundaries-in-distributed-tracing/"
    ),
    "sdk_setup": (
        "sdk-implementation-context-propagation/"
        "opentelemetry-sdk-setup-for-backend-services/"
    ),
    "python_sdk": (
        "sdk-implementation-context-propagation/"
        "opentelemetry-sdk-setup-for-backend-services/"
        "step-by-step-opentelemetry-python-sdk-integration/"
    ),
    "auto_vs_manual": (
        "sdk-implementation-context-propagation/"
        "auto-instrumentation-vs-manual-span-creation/"
    ),
    "manual_spans": (
        "sdk-implementation-context-propagation/"
        "auto-instrumentation-vs-manual-span-creation/"
        "manual-span-creation-for-custom-business-logic/"
    ),
    "web_frameworks": (
        "sdk-implementation-context-propagation/"
        "instrumenting-web-frameworks-with-opentelemetry/"
    ),
    "fastapi": (
        "sdk-implementation-context-propagation/"
        "instrumenting-web-frameworks-with-opentelemetry/"
        "instrumenting-fastapi-with-opentelemetry/"
    ),
    "express": (
        "sdk-implementation-context-propagation/"
        "instrumenting-web-frameworks-with-opentelemetry/"
        "instrumenting-express-with-opentelemetry/"
    ),
    "spring_boot": (
        "sdk-implementation-context-propagation/"
        "instrumenting-web-frameworks-with-opentelemetry/"
        "instrumenting-spring-boot-with-opentelemetry/"
    ),
    "grpc": (
        "sdk-implementation-context-propagation/"
        "instrumenting-web-frameworks-with-opentelemetry/"
        "instrumenting-grpc-services-with-opentelemetry/"
    ),
    "async_boundaries": (
        "sdk-implementation-context-propagation/"
        "handling-async-boundaries-in-nodejs-and-python/"
    ),
    "async_fastapi": (
        "sdk-implementation-context-propagation/"
        "handling-async-boundaries-in-nodejs-and-python/"
        "fixing-dropped-spans-in-async-python-fastapi-routes/"
    ),
    "threads": (
        "sdk-implementation-context-propagation/"
        "trace-context-in-multi-threaded-environments/"
    ),
    "java_thread_pools": (
        "sdk-implementation-context-propagation/"
        "trace-context-in-multi-threaded-environments/"
        "propagating-context-across-thread-pools-in-java/"
    ),
    "collector_pipeline": (
        "sdk-implementation-context-propagation/"
        "opentelemetry-collector-pipeline-configuration/"
    ),
    "collector_processors": (
        "sdk-implementation-context-propagation/"
        "opentelemetry-collector-pipeline-configuration/"
        "configuring-the-batch-and-memory-limiter-processors/"
    ),
    "collector_filtering": (
        "sdk-implementation-context-propagation/"
        "opentelemetry-collector-pipeline-configuration/"
        "filtering-and-transforming-spans-in-the-collector/"
    ),
    "baggage_vs_attributes": (
        "baggage-metadata-routing-workflows/"
        "baggage-vs-span-attributes-when-to-use-what/"
    ),
    "baggage_limits": (
        "baggage-metadata-routing-workflows/"
        "baggage-size-limits-and-header-constraints/"
    ),
    "baggage_grpc": (
        "baggage-metadata-routing-workflows/"
        "propagating-baggage-across-kafka-and-grpc/"
        "propagating-baggage-through-grpc-metadata/"
    ),
    "log_correlation": (
        "trace-debugging-and-signal-correlation/"
        "correlating-logs-metrics-and-traces/"
    ),
    "trace_ids_in_logs": (
        "trace-debugging-and-signal-correlation/"
        "correlating-logs-metrics-and-traces/"
        "adding-trace-ids-to-application-logs/"
    ),
    "critical_path": (
        "trace-debugging-and-signal-correlation/"
        "finding-latency-bottlenecks-with-critical-path-analysis/"
    ),
    "red_metrics": (
        "trace-debugging-and-signal-correlation/"
        "trace-based-alerting-and-slo-monitoring/"
        "generating-red-metrics-from-spans/"
    ),
}


def article(key: str) -> str:
    """Absolute URL of a named article."""
    try:
        return f"{SITE}/{ARTICLES[key]}"
    except KeyError as exc:  # pragma: no cover - guarded by tests
        raise KeyError(f"unknown article key {key!r}") from exc


# ----------------------------------------------------------------------
# Languages and frameworks
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Framework:
    key: str
    label: str
    #: Article key the framework wiring file points at.
    article: str
    #: Basename of the wiring template inside ``templates/<language>/``.
    wiring_template: str
    #: One-line summary shown by ``--list-targets``.
    summary: str
    #: Extra files rendered only for this framework: (template, output, article)
    extra: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True)
class Language:
    key: str
    label: str
    #: Ordered framework keys.
    frameworks: tuple[str, ...]
    #: Runtime prerequisite, shown in the generated setup guide.
    runtime: str


_PYTHON_FRAMEWORKS = (
    Framework(
        key="fastapi",
        label="FastAPI",
        article="fastapi",
        wiring_template="wiring_fastapi.py.j2",
        summary="ASGI app instrumented with FastAPIInstrumentor",
    ),
    Framework(
        key="django",
        label="Django",
        article="web_frameworks",
        wiring_template="wiring_django.py.j2",
        summary="WSGI/ASGI app instrumented with DjangoInstrumentor",
    ),
    Framework(
        key="flask",
        label="Flask",
        article="web_frameworks",
        wiring_template="wiring_flask.py.j2",
        summary="WSGI app instrumented with FlaskInstrumentor",
    ),
    Framework(
        key="celery",
        label="Celery worker",
        article="orphaned_spans",
        wiring_template="wiring_celery.py.j2",
        summary="worker processes instrumented per fork, context carried on the task",
    ),
    Framework(
        key="script",
        label="Plain script",
        article="manual_spans",
        wiring_template="wiring_script.py.j2",
        summary="no framework, manual spans only",
    ),
)

_NODE_FRAMEWORKS = (
    Framework(
        key="express",
        label="Express",
        article="express",
        wiring_template="wiring_express.js.j2",
        summary="HTTP + Express auto-instrumentation",
    ),
    Framework(
        key="fastify",
        label="Fastify",
        article="web_frameworks",
        wiring_template="wiring_fastify.js.j2",
        summary="HTTP + Fastify auto-instrumentation",
    ),
    Framework(
        key="nestjs",
        label="NestJS",
        article="web_frameworks",
        wiring_template="wiring_nestjs.js.j2",
        summary="HTTP + Express + NestJS core auto-instrumentation",
    ),
    Framework(
        key="plain",
        label="Plain Node.js",
        article="async_boundaries",
        wiring_template="wiring_plain.js.j2",
        summary="HTTP client/server instrumentation and manual spans",
    ),
)

_JAVA_FRAMEWORKS = (
    Framework(
        key="spring-boot-agent",
        label="Spring Boot (Java agent)",
        article="spring_boot",
        wiring_template="wiring_spring_agent.sh.j2",
        summary="zero-code instrumentation via the OpenTelemetry Java agent",
        extra=(
            (
                "manual_spans.java.j2",
                "src/main/java/com/example/otel/BusinessSpans.java",
                "manual_spans",
            ),
        ),
    ),
    Framework(
        key="spring-boot-manual",
        label="Spring Boot (manual SDK)",
        article="spring_boot",
        wiring_template="wiring_spring_manual.java.j2",
        summary="hand-built SdkTracerProvider plus a server-span servlet filter",
        extra=(
            (
                "tracing_filter.java.j2",
                "src/main/java/com/example/otel/TracingFilter.java",
                "tracecontext",
            ),
            (
                "context_executor.java.j2",
                "src/main/java/com/example/otel/TracedExecutors.java",
                "java_thread_pools",
            ),
        ),
    ),
)

_GO_FRAMEWORKS = (
    Framework(
        key="net-http",
        label="net/http service",
        article="web_frameworks",
        wiring_template="wiring_nethttp.go.j2",
        summary="otelhttp handler and transport",
    ),
    Framework(
        key="grpc",
        label="gRPC service",
        article="grpc",
        wiring_template="wiring_grpc.go.j2",
        summary="otelgrpc stats handlers for server and client",
    ),
)

LANGUAGES: dict[str, Language] = {
    "python": Language(
        key="python",
        label="Python",
        frameworks=tuple(f.key for f in _PYTHON_FRAMEWORKS),
        runtime="Python 3.9+",
    ),
    "node": Language(
        key="node",
        label="Node.js",
        frameworks=tuple(f.key for f in _NODE_FRAMEWORKS),
        runtime="Node.js 18+",
    ),
    "java": Language(
        key="java",
        label="Java",
        frameworks=tuple(f.key for f in _JAVA_FRAMEWORKS),
        runtime="Java 17+ and Maven",
    ),
    "go": Language(
        key="go",
        label="Go",
        frameworks=tuple(f.key for f in _GO_FRAMEWORKS),
        runtime="Go 1.22+",
    ),
}

FRAMEWORKS: dict[tuple[str, str], Framework] = {}
for _lang_key, _fws in (
    ("python", _PYTHON_FRAMEWORKS),
    ("node", _NODE_FRAMEWORKS),
    ("java", _JAVA_FRAMEWORKS),
    ("go", _GO_FRAMEWORKS),
):
    for _fw in _fws:
        FRAMEWORKS[(_lang_key, _fw.key)] = _fw


# ----------------------------------------------------------------------
# Backends
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Backend:
    key: str
    label: str
    #: Transport used when the application talks to the backend directly.
    protocol: str
    #: Endpoint used when the application talks to the backend directly.
    direct_endpoint: str = ""
    #: Transport used between the application and a local collector.
    collector_ingest_protocol: str = "grpc"
    #: Credentials as ``(header name, environment variable)`` pairs.
    header_env: tuple[tuple[str, str], ...] = ()
    #: Compose services (besides the collector) this backend brings up.
    compose_services: tuple[str, ...] = ()
    #: Where to look at the traces once they arrive.
    ui: str = ""
    #: One-line note surfaced in --list-targets and OTEL_SETUP.md.
    note: str = ""
    #: Extra environment variables for .env.example: (name, value, comment)
    extra_env: tuple[tuple[str, str, str], ...] = ()

    @property
    def is_console(self) -> bool:
        return self.key == "console"


BACKENDS: dict[str, Backend] = {
    "otlp-grpc": Backend(
        key="otlp-grpc",
        label="OTLP/gRPC",
        protocol="grpc",
        direct_endpoint="http://localhost:4317",
        ui="",
        note="Generic OTLP over gRPC on port 4317. Point it at any compliant backend.",
    ),
    "otlp-http": Backend(
        key="otlp-http",
        label="OTLP/HTTP",
        protocol="http",
        direct_endpoint="http://localhost:4318",
        collector_ingest_protocol="http",
        ui="",
        note="Generic OTLP over HTTP/protobuf on port 4318, for networks that dislike gRPC.",
    ),
    "jaeger": Backend(
        key="jaeger",
        label="Jaeger",
        protocol="grpc",
        direct_endpoint="http://localhost:4317",
        compose_services=("jaeger",),
        ui="http://localhost:16686",
        note="Jaeger all-in-one with native OTLP ingest. The legacy Jaeger exporters are removed; OTLP is the only supported path.",
    ),
    "tempo": Backend(
        key="tempo",
        label="Grafana Tempo",
        protocol="grpc",
        direct_endpoint="http://localhost:4317",
        compose_services=("tempo", "grafana"),
        ui="http://localhost:3000",
        note="Tempo with object-storage-shaped local blocks, explored through Grafana.",
    ),
    "honeycomb": Backend(
        key="honeycomb",
        label="Honeycomb",
        protocol="grpc",
        direct_endpoint="https://api.honeycomb.io:443",
        header_env=(("x-honeycomb-team", "HONEYCOMB_API_KEY"),),
        ui="https://ui.honeycomb.io",
        note="Managed backend; the ingest key is sent as an OTLP header.",
        extra_env=(
            (
                "HONEYCOMB_API_KEY",
                "",
                "Ingest key from https://ui.honeycomb.io/account",
            ),
            (
                "HONEYCOMB_DATASET",
                "",
                "Only needed for Classic accounts; modern ones use service.name",
            ),
        ),
    ),
    "datadog": Backend(
        key="datadog",
        label="Datadog (OTLP ingest)",
        protocol="grpc",
        direct_endpoint="http://localhost:4317",
        compose_services=("datadog-agent",),
        ui="https://app.datadoghq.com/apm/traces",
        note="Spans go to the Datadog Agent's OTLP receiver, which forwards them to the platform.",
        extra_env=(
            ("DD_API_KEY", "", "Datadog API key used by the local agent"),
            ("DD_SITE", "datadoghq.com", "datadoghq.eu, us5.datadoghq.com, ..."),
        ),
    ),
    "console": Backend(
        key="console",
        label="Console / stdout",
        protocol="console",
        ui="your terminal",
        note="No network, no backend. Spans are printed as JSON; ideal for a first run.",
    ),
}


# ----------------------------------------------------------------------
# File plan
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class FileSpec:
    """One template rendered to one output path."""

    template: str
    output: str
    #: Article key linked from this file's header comment.
    article: str
    #: Rendering is skipped when False.
    enabled: bool = True
    extra_context: dict[str, object] = field(default_factory=dict)


_LANGUAGE_CORE: dict[str, tuple[tuple[str, str, str], ...]] = {
    "python": (
        ("package_init.py.j2", "otel/__init__.py", "sdk_setup"),
        ("tracing.py.j2", "otel/tracing.py", "python_sdk"),
        ("logging_setup.py.j2", "otel/logging_setup.py", "trace_ids_in_logs"),
        ("requirements-otel.txt.j2", "requirements-otel.txt", "sdk_setup"),
    ),
    "node": (
        ("tracing.js.j2", "otel/tracing.js", "sdk_setup"),
        ("logging.js.j2", "otel/logging.js", "trace_ids_in_logs"),
        ("package.otel.json.j2", "package.otel.json", "sdk_setup"),
    ),
    "java": (
        ("logback-spring.xml.j2", "src/main/resources/logback-spring.xml", "trace_ids_in_logs"),
        ("pom-otel.xml.j2", "pom-otel.xml", "sdk_setup"),
    ),
    "go": (
        ("tracing.go.j2", "tracing/tracing.go", "sdk_setup"),
        ("logging.go.j2", "tracing/logging.go", "trace_ids_in_logs"),
        ("go.mod.snippet.j2", "go.mod.snippet", "sdk_setup"),
    ),
}

_WIRING_OUTPUT: dict[str, str] = {
    "python": "otel/instrumentation.py",
    "node": "otel/instrumentation.js",
    "go": "tracing/instrumentation.go",
}

_JAVA_WIRING_OUTPUT: dict[str, str] = {
    "spring-boot-agent": "run-with-agent.sh",
    "spring-boot-manual": "src/main/java/com/example/otel/OpenTelemetryConfig.java",
}


def plan_files(spec: "Spec") -> list[FileSpec]:
    """Return the ordered list of files a spec generates."""
    lang = spec.language.key
    fw = spec.framework
    files: list[FileSpec] = []

    for template, output, art in _LANGUAGE_CORE[lang]:
        files.append(FileSpec(f"{lang}/{template}", output, art))

    if lang == "java":
        wiring_output = _JAVA_WIRING_OUTPUT[fw.key]
    else:
        wiring_output = _WIRING_OUTPUT[lang]
    files.append(FileSpec(f"{lang}/{fw.wiring_template}", wiring_output, fw.article))

    for template, output, art in fw.extra:
        files.append(FileSpec(f"{lang}/{template}", output, art))

    files.append(FileSpec("common/env.example.j2", ".env.example", "sdk_setup"))
    files.append(
        FileSpec(
            "common/otel-collector-config.yaml.j2",
            "otel-collector-config.yaml",
            "collector_processors",
            enabled=spec.renders_collector,
        )
    )
    files.append(
        FileSpec(
            "common/docker-compose.yml.j2",
            "docker-compose.yml",
            "storage_backends" if spec.backend.compose_services else "collector_pipeline",
            enabled=spec.renders_compose,
        )
    )
    files.append(
        FileSpec(
            "common/tempo.yaml.j2",
            "tempo.yaml",
            "storage_backends",
            enabled=spec.renders_compose and spec.backend.key == "tempo",
        )
    )
    files.append(
        FileSpec(
            "common/grafana-datasources.yaml.j2",
            "grafana/provisioning/datasources/tempo.yaml",
            "log_correlation",
            enabled=spec.renders_compose and spec.backend.key == "tempo",
        )
    )
    files.append(FileSpec("common/OTEL_SETUP.md.j2", "OTEL_SETUP.md", "sdk_setup"))

    return [f for f in files if f.enabled]


#: Files that should be written with the executable bit set.
EXECUTABLE_OUTPUTS = frozenset({"run-with-agent.sh"})
