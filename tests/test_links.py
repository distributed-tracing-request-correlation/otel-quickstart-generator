"""Every link the generator emits must be a real article path.

The list below is transcribed from the site's published article index. A typo
in ``presets.ARTICLES`` would otherwise ship a dead link inside every generated
file, which is exactly the kind of thing nobody notices for months.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from otelgen import presets, render
from otelgen.spec import all_combinations, build_spec

KNOWN_PATHS = {
    "distributed-tracing-fundamentals-architecture/understanding-w3c-tracecontext-propagation/",
    "distributed-tracing-fundamentals-architecture/understanding-w3c-tracecontext-propagation/how-to-implement-w3c-tracecontext-in-legacy-systems/",
    "distributed-tracing-fundamentals-architecture/span-lifecycle-and-parent-child-relationships/",
    "distributed-tracing-fundamentals-architecture/span-lifecycle-and-parent-child-relationships/debugging-orphaned-spans-in-async-workflows/",
    "distributed-tracing-fundamentals-architecture/choosing-between-head-based-and-tail-based-sampling/",
    "distributed-tracing-fundamentals-architecture/choosing-between-head-based-and-tail-based-sampling/head-based-vs-tail-based-sampling-cheatsheet/",
    "distributed-tracing-fundamentals-architecture/choosing-between-head-based-and-tail-based-sampling/when-to-use-tail-based-sampling-for-microservices/",
    "distributed-tracing-fundamentals-architecture/trace-storage-backend-comparison-jaeger-vs-tempo/",
    "distributed-tracing-fundamentals-architecture/trace-storage-backend-comparison-jaeger-vs-tempo/jaeger-vs-tempo-vs-zipkin-decision-guide/",
    "distributed-tracing-fundamentals-architecture/trace-storage-backend-comparison-jaeger-vs-tempo/configuring-jaeger-retention-policies-for-compliance/",
    "distributed-tracing-fundamentals-architecture/security-boundaries-in-distributed-tracing/",
    "distributed-tracing-fundamentals-architecture/security-boundaries-in-distributed-tracing/encrypting-trace-payloads-at-rest-and-in-transit/",
    "sdk-implementation-context-propagation/opentelemetry-sdk-setup-for-backend-services/",
    "sdk-implementation-context-propagation/opentelemetry-sdk-setup-for-backend-services/step-by-step-opentelemetry-python-sdk-integration/",
    "sdk-implementation-context-propagation/auto-instrumentation-vs-manual-span-creation/",
    "sdk-implementation-context-propagation/auto-instrumentation-vs-manual-span-creation/manual-span-creation-for-custom-business-logic/",
    "sdk-implementation-context-propagation/instrumenting-web-frameworks-with-opentelemetry/",
    "sdk-implementation-context-propagation/instrumenting-web-frameworks-with-opentelemetry/instrumenting-fastapi-with-opentelemetry/",
    "sdk-implementation-context-propagation/instrumenting-web-frameworks-with-opentelemetry/instrumenting-express-with-opentelemetry/",
    "sdk-implementation-context-propagation/instrumenting-web-frameworks-with-opentelemetry/instrumenting-spring-boot-with-opentelemetry/",
    "sdk-implementation-context-propagation/instrumenting-web-frameworks-with-opentelemetry/instrumenting-grpc-services-with-opentelemetry/",
    "sdk-implementation-context-propagation/handling-async-boundaries-in-nodejs-and-python/",
    "sdk-implementation-context-propagation/handling-async-boundaries-in-nodejs-and-python/fixing-dropped-spans-in-async-python-fastapi-routes/",
    "sdk-implementation-context-propagation/trace-context-in-multi-threaded-environments/",
    "sdk-implementation-context-propagation/trace-context-in-multi-threaded-environments/propagating-context-across-thread-pools-in-java/",
    "sdk-implementation-context-propagation/context-propagation-across-service-meshes/",
    "sdk-implementation-context-propagation/context-propagation-across-service-meshes/propagating-trace-context-through-kafka-consumers/",
    "sdk-implementation-context-propagation/opentelemetry-collector-pipeline-configuration/",
    "sdk-implementation-context-propagation/opentelemetry-collector-pipeline-configuration/configuring-the-batch-and-memory-limiter-processors/",
    "sdk-implementation-context-propagation/opentelemetry-collector-pipeline-configuration/filtering-and-transforming-spans-in-the-collector/",
    "baggage-metadata-routing-workflows/baggage-vs-span-attributes-when-to-use-what/",
    "baggage-metadata-routing-workflows/baggage-vs-span-attributes-when-to-use-what/how-to-safely-propagate-user-ids-via-opentelemetry-baggage/",
    "baggage-metadata-routing-workflows/baggage-size-limits-and-header-constraints/",
    "baggage-metadata-routing-workflows/baggage-size-limits-and-header-constraints/avoiding-431-request-header-too-large-errors/",
    "baggage-metadata-routing-workflows/propagating-baggage-across-kafka-and-grpc/",
    "baggage-metadata-routing-workflows/propagating-baggage-across-kafka-and-grpc/injecting-baggage-into-kafka-message-headers/",
    "baggage-metadata-routing-workflows/propagating-baggage-across-kafka-and-grpc/propagating-baggage-through-grpc-metadata/",
    "baggage-metadata-routing-workflows/tenant-context-propagation-in-multi-tenant-saas/",
    "baggage-metadata-routing-workflows/tenant-context-propagation-in-multi-tenant-saas/enforcing-tenant-isolation-in-trace-data/",
    "baggage-metadata-routing-workflows/dynamic-request-routing-with-baggage/",
    "baggage-metadata-routing-workflows/dynamic-request-routing-with-baggage/canary-routing-with-opentelemetry-baggage/",
    "baggage-metadata-routing-workflows/dynamic-request-routing-with-baggage/routing-by-region-and-compliance-zone/",
    "trace-debugging-and-signal-correlation/correlating-logs-metrics-and-traces/",
    "trace-debugging-and-signal-correlation/correlating-logs-metrics-and-traces/adding-trace-ids-to-application-logs/",
    "trace-debugging-and-signal-correlation/finding-latency-bottlenecks-with-critical-path-analysis/",
    "trace-debugging-and-signal-correlation/finding-latency-bottlenecks-with-critical-path-analysis/identifying-slow-database-queries-in-traces/",
    "trace-debugging-and-signal-correlation/trace-based-alerting-and-slo-monitoring/",
    "trace-debugging-and-signal-correlation/trace-based-alerting-and-slo-monitoring/generating-red-metrics-from-spans/",
}

LINK_RE = re.compile(r"https://www\.distributed-tracing\.com/([^\s)\"'`>,]*)")

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_preset_articles_are_real_paths() -> None:
    for key, path in presets.ARTICLES.items():
        assert path in KNOWN_PATHS, f"{key} points at an unknown path: {path}"


def test_generated_links_are_real_paths() -> None:
    seen: set[str] = set()
    for language, framework, backend in all_combinations():
        spec = build_spec(
            language=language,
            framework=framework,
            backend=backend,
            service_name="checkout-api",
        )
        for name, content in render(spec).items():
            for path in LINK_RE.findall(content):
                assert path in KNOWN_PATHS, f"{name} links to {path!r}"
                seen.add(path)
    assert len(seen) >= 8, "expected links to spread across several articles"


def test_readme_uses_markdown_links_only() -> None:
    """No raw site URLs in the README; they must be markdown text links."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    outside_code: list[str] = []
    in_fence = False
    for line in readme.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            outside_code.append(line)
    text = "\n".join(outside_code)
    for match in LINK_RE.finditer(text):
        start = match.start()
        assert text[start - 2 : start] == "](", (
            "raw site URL outside a markdown link: " + match.group(0)
        )


def test_readme_links_are_real_paths() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for path in LINK_RE.findall(readme):
        assert path in KNOWN_PATHS or path == "", f"README links to {path!r}"


@pytest.mark.parametrize("key", sorted(presets.ARTICLES))
def test_article_helper_builds_absolute_urls(key: str) -> None:
    url = presets.article(key)
    assert url.startswith("https://www.distributed-tracing.com/")
    assert url.endswith("/")
