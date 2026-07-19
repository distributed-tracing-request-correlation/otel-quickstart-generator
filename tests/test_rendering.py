"""Render every supported combination and validate the output.

The point of these tests is not that the generator produces *something*, but
that what it produces parses: Python through :mod:`ast`, YAML and JSON through
their parsers, JavaScript through ``node --check`` when node is available and a
brace/paren balance check when it is not.
"""

from __future__ import annotations

import ast
import json
import subprocess
import shutil
from pathlib import Path

import pytest
import yaml

from otelgen import presets, render
from otelgen.spec import all_combinations, build_spec

NODE = shutil.which("node")

COMBINATIONS = all_combinations()
COMBINATION_IDS = [f"{lang}-{fw}-{be}" for lang, fw, be in COMBINATIONS]


@pytest.fixture(scope="module")
def all_rendered() -> dict[tuple[str, str, str], dict[str, str]]:
    """Render every combination once and share it across tests."""
    out: dict[tuple[str, str, str], dict[str, str]] = {}
    for language, framework, backend in COMBINATIONS:
        spec = build_spec(
            language=language,
            framework=framework,
            backend=backend,
            service_name="checkout-api",
            sampling="head:0.1",
        )
        out[(language, framework, backend)] = render(spec)
    return out


def _balanced(text: str) -> bool:
    """Cheap structural check: brackets balance outside strings and comments."""
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    quote: str | None = None
    in_line_comment = False
    in_block_comment = False
    index = 0
    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""
        if in_line_comment:
            if char == "\n":
                in_line_comment = False
        elif in_block_comment:
            if char == "*" and nxt == "/":
                in_block_comment = False
                index += 1
        elif quote:
            if char == "\\":
                index += 1
            elif char == quote:
                quote = None
        elif char == "/" and nxt == "/":
            in_line_comment = True
            index += 1
        elif char == "/" and nxt == "*":
            in_block_comment = True
            index += 1
        elif char in "\"'`":
            quote = char
        elif char in "([{":
            stack.append(char)
        elif char in ")]}":
            if not stack or stack.pop() != pairs[char]:
                return False
        index += 1
    return not stack


def test_every_combination_is_supported() -> None:
    # 13 language/framework targets across 7 backends.
    assert len(COMBINATIONS) == 13 * 7, "matrix size changed unexpectedly"


@pytest.mark.parametrize(
    ("language", "framework", "backend"), COMBINATIONS, ids=COMBINATION_IDS
)
def test_files_exist_and_are_non_empty(
    language: str, framework: str, backend: str, tmp_path: Path
) -> None:
    spec = build_spec(
        language=language,
        framework=framework,
        backend=backend,
        service_name="checkout-api",
        out_dir=tmp_path / "out",
    )
    rendered = render(spec)
    assert rendered, "no files rendered"

    from otelgen import write_files

    write_files(spec, rendered)
    for relative in rendered:
        path = spec.out_dir / relative
        assert path.exists(), f"{relative} was not written"
        assert path.stat().st_size > 0, f"{relative} is empty"
        assert path.read_text(encoding="utf-8").strip(), f"{relative} is blank"

    # Every target ships a bootstrap, a wiring file and a setup guide.
    assert "OTEL_SETUP.md" in rendered
    assert any("instrumentation" in name or "run-with-agent" in name or
               "OpenTelemetryConfig" in name for name in rendered)


@pytest.mark.parametrize(
    ("language", "framework", "backend"), COMBINATIONS, ids=COMBINATION_IDS
)
def test_generated_python_parses(
    all_rendered, language: str, framework: str, backend: str
) -> None:
    rendered = all_rendered[(language, framework, backend)]
    python_files = {n: c for n, c in rendered.items() if n.endswith(".py")}
    if language == "python":
        assert python_files, "python target produced no .py files"
    for name, content in python_files.items():
        try:
            ast.parse(content, filename=name)
        except SyntaxError as exc:  # pragma: no cover - failure path
            pytest.fail(f"{language}/{framework}/{backend} {name}: {exc}")


@pytest.mark.parametrize(
    ("language", "framework", "backend"), COMBINATIONS, ids=COMBINATION_IDS
)
def test_generated_yaml_parses(
    all_rendered, language: str, framework: str, backend: str
) -> None:
    rendered = all_rendered[(language, framework, backend)]
    for name, content in rendered.items():
        if not name.endswith((".yaml", ".yml")):
            continue
        try:
            parsed = yaml.safe_load(content)
        except yaml.YAMLError as exc:  # pragma: no cover - failure path
            pytest.fail(f"{name}: {exc}")
        assert isinstance(parsed, dict) and parsed, f"{name} parsed to nothing"


@pytest.mark.parametrize(
    ("language", "framework", "backend"), COMBINATIONS, ids=COMBINATION_IDS
)
def test_generated_json_parses(
    all_rendered, language: str, framework: str, backend: str
) -> None:
    rendered = all_rendered[(language, framework, backend)]
    for name, content in rendered.items():
        if not name.endswith(".json"):
            continue
        parsed = json.loads(content)
        assert parsed["dependencies"], f"{name} has no dependencies"


@pytest.mark.parametrize(
    ("language", "framework", "backend"), COMBINATIONS, ids=COMBINATION_IDS
)
def test_generated_javascript_is_valid(
    all_rendered, language: str, framework: str, backend: str, tmp_path: Path
) -> None:
    rendered = all_rendered[(language, framework, backend)]
    js_files = {n: c for n, c in rendered.items() if n.endswith(".js")}
    if language == "node":
        assert js_files, "node target produced no .js files"
    for name, content in js_files.items():
        assert _balanced(content), f"{name}: unbalanced brackets"
        if NODE:
            path = tmp_path / Path(name).name
            path.write_text(content, encoding="utf-8")
            result = subprocess.run(
                [NODE, "--check", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 0, f"{name}: {result.stderr}"


@pytest.mark.parametrize(
    ("language", "framework", "backend"), COMBINATIONS, ids=COMBINATION_IDS
)
def test_braces_balance_in_java_and_go(
    all_rendered, language: str, framework: str, backend: str
) -> None:
    rendered = all_rendered[(language, framework, backend)]
    for name, content in rendered.items():
        if name.endswith((".java", ".go")):
            assert _balanced(content), f"{name}: unbalanced brackets"


@pytest.mark.parametrize(
    ("language", "framework", "backend"), COMBINATIONS, ids=COMBINATION_IDS
)
def test_no_unrendered_template_syntax(
    all_rendered, language: str, framework: str, backend: str
) -> None:
    rendered = all_rendered[(language, framework, backend)]
    for name, content in rendered.items():
        assert "{%" not in content, f"{name} contains an unrendered Jinja tag"
        assert "{{" not in content, f"{name} contains an unrendered Jinja variable"
        assert "TODO" not in content, f"{name} contains a TODO"


@pytest.mark.parametrize(
    ("language", "framework", "backend"), COMBINATIONS, ids=COMBINATION_IDS
)
def test_service_name_reaches_the_output(
    all_rendered, language: str, framework: str, backend: str
) -> None:
    rendered = all_rendered[(language, framework, backend)]
    assert any("checkout-api" in content for content in rendered.values())


@pytest.mark.parametrize(
    ("language", "framework", "backend"), COMBINATIONS, ids=COMBINATION_IDS
)
def test_no_deprecated_jaeger_exporter(
    all_rendered, language: str, framework: str, backend: str
) -> None:
    """The Jaeger-native exporters are removed from the SDKs; OTLP replaced them."""
    forbidden = (
        "jaeger_thrift",
        "JaegerExporter",
        "exporter-jaeger",
        "opentelemetry-exporter-jaeger",
        "jaegerpropagator",
        "otlptracejaeger",
    )
    for name, content in all_rendered[(language, framework, backend)].items():
        lowered = content.lower()
        for token in forbidden:
            assert token.lower() not in lowered, f"{name} references {token}"


@pytest.mark.parametrize(
    ("language", "framework", "backend"), COMBINATIONS, ids=COMBINATION_IDS
)
def test_collector_pipeline_shape(
    all_rendered, language: str, framework: str, backend: str
) -> None:
    rendered = all_rendered[(language, framework, backend)]
    config = rendered.get("otel-collector-config.yaml")
    if backend == "console":
        assert config is None, "a collector makes no sense for the console exporter"
        return
    assert config is not None
    parsed = yaml.safe_load(config)
    traces = parsed["service"]["pipelines"]["traces"]
    assert traces["receivers"] == ["otlp"]
    # memory_limiter must come first and batch last.
    assert traces["processors"][0] == "memory_limiter"
    assert traces["processors"][-1] == "batch"
    for exporter in traces["exporters"]:
        assert exporter in parsed["exporters"], f"{exporter} is not configured"


def test_console_backend_has_no_compose_or_collector() -> None:
    spec = build_spec(
        language="python",
        framework="fastapi",
        backend="console",
        service_name="checkout-api",
    )
    rendered = render(spec)
    assert "docker-compose.yml" not in rendered
    assert "otel-collector-config.yaml" not in rendered


def test_tempo_stack_is_complete() -> None:
    spec = build_spec(
        language="python",
        framework="fastapi",
        backend="tempo",
        service_name="checkout-api",
    )
    rendered = render(spec)
    assert "tempo.yaml" in rendered
    assert "grafana/provisioning/datasources/tempo.yaml" in rendered
    compose = yaml.safe_load(rendered["docker-compose.yml"])
    assert set(compose["services"]) == {"otel-collector", "tempo", "grafana"}
    tempo = yaml.safe_load(rendered["tempo.yaml"])
    assert tempo["distributor"]["receivers"]["otlp"]["protocols"]["grpc"]


def test_no_collector_points_the_app_at_the_backend() -> None:
    spec = build_spec(
        language="go",
        framework="net-http",
        backend="jaeger",
        service_name="checkout-api",
        with_collector=False,
    )
    rendered = render(spec)
    assert "otel-collector-config.yaml" not in rendered
    compose = yaml.safe_load(rendered["docker-compose.yml"])
    assert set(compose["services"]) == {"jaeger"}
    # Jaeger has to expose the OTLP ports itself now.
    assert "4317:4317" in compose["services"]["jaeger"]["ports"]


def test_honeycomb_credentials_move_to_the_collector() -> None:
    via_collector = build_spec(
        language="node",
        framework="express",
        backend="honeycomb",
        service_name="checkout-api",
    )
    assert via_collector.headers == ()
    assert "HONEYCOMB_API_KEY" in render(via_collector)["otel-collector-config.yaml"]

    direct = build_spec(
        language="node",
        framework="express",
        backend="honeycomb",
        service_name="checkout-api",
        with_collector=False,
    )
    assert direct.headers == (("x-honeycomb-team", "HONEYCOMB_API_KEY"),)
    assert "HONEYCOMB_API_KEY" in render(direct)["otel/tracing.js"]


def test_every_file_links_to_exactly_one_article() -> None:
    """Discreet promotion: one contextual link per generated file, no more."""
    spec = build_spec(
        language="python",
        framework="fastapi",
        backend="tempo",
        service_name="checkout-api",
    )
    for name, content in render(spec).items():
        occurrences = content.count(presets.SITE)
        if name == "OTEL_SETUP.md":
            # The generated guide has a short "further reading" list.
            assert 3 <= occurrences <= 6, name
        else:
            assert occurrences == 1, f"{name} has {occurrences} site links"
