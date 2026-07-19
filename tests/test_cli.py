"""CLI behaviour: validation, dry runs, overwrite protection, interactive mode."""

from __future__ import annotations

import io
import shutil
import subprocess
from pathlib import Path

import pytest

from otelgen import build_spec, render, write_files
from otelgen.cli import format_targets, main
from otelgen.renderer import OverwriteError
from otelgen.spec import SpecError, parse_sampling

BASH = shutil.which("bash")


def run(args: list[str]) -> tuple[int, str]:
    stream = io.StringIO()
    code = main(args, stream=stream)
    return code, stream.getvalue()


def test_list_targets_covers_the_matrix() -> None:
    code, output = run(["--list-targets"])
    assert code == 0
    for token in ("fastapi", "celery", "nestjs", "spring-boot-agent", "net-http",
                  "honeycomb", "tempo", "console", "head:<ratio>"):
        assert token in output


def test_generate_writes_files(tmp_path: Path) -> None:
    code, output = run(
        [
            "--language", "python",
            "--framework", "flask",
            "--backend", "jaeger",
            "--service-name", "checkout-api",
            "--out", str(tmp_path / "out"),
        ]
    )
    assert code == 0
    assert (tmp_path / "out" / "otel" / "tracing.py").exists()
    assert "OTEL_SETUP.md" in output


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    out = tmp_path / "out"
    code, output = run(
        [
            "--language", "node",
            "--framework", "express",
            "--backend", "tempo",
            "--service-name", "edge-api",
            "--out", str(out),
            "--dry-run",
        ]
    )
    assert code == 0
    assert not out.exists()
    assert "otel/tracing.js" in output
    assert "nothing was written" in output


def test_dry_run_shows_a_diff_for_changed_files(tmp_path: Path) -> None:
    out = tmp_path / "out"
    spec = build_spec(
        language="python",
        framework="script",
        backend="console",
        service_name="batch-job",
        out_dir=out,
    )
    write_files(spec, render(spec))
    (out / "otel" / "tracing.py").write_text("# emptied\n", encoding="utf-8")

    code, output = run(
        [
            "--language", "python",
            "--framework", "script",
            "--backend", "console",
            "--service-name", "batch-job",
            "--out", str(out),
            "--dry-run",
        ]
    )
    assert code == 0
    assert "--- otel/tracing.py (existing)" in output
    assert "-# emptied" in output
    assert "= OTEL_SETUP.md (unchanged)" in output


def test_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    args = [
        "--language", "go",
        "--framework", "grpc",
        "--backend", "console",
        "--service-name", "ledger",
        "--out", str(tmp_path / "out"),
    ]
    assert run(args)[0] == 0
    assert run(args)[0] == 1, "second run should refuse to overwrite"
    assert run(args + ["--force"])[0] == 0


def test_overwrite_error_lists_the_paths(tmp_path: Path) -> None:
    spec = build_spec(
        language="go",
        framework="net-http",
        backend="console",
        service_name="ledger",
        out_dir=tmp_path / "out",
    )
    rendered = render(spec)
    write_files(spec, rendered)
    with pytest.raises(OverwriteError) as excinfo:
        write_files(spec, rendered)
    assert len(excinfo.value.paths) == len(rendered)
    assert "--force" in str(excinfo.value)


@pytest.mark.parametrize(
    "args",
    [
        ["--language", "python", "--framework", "rails", "--backend", "console",
         "--service-name", "x"],
        ["--language", "python", "--framework", "fastapi", "--backend", "console",
         "--service-name", "not a valid name"],
        ["--language", "python", "--framework", "fastapi", "--backend", "console",
         "--service-name", "svc", "--sampling", "head:2.5"],
        ["--language", "python", "--framework", "fastapi", "--backend", "console",
         "--service-name", "svc", "--sampling", "tail"],
    ],
)
def test_bad_input_exits_with_2(args: list[str]) -> None:
    assert run(args)[0] == 2


def test_missing_required_flags_exits_with_2() -> None:
    with pytest.raises(SystemExit) as excinfo:
        run(["--language", "python"])
    assert excinfo.value.code == 2


@pytest.mark.parametrize(
    ("value", "kind", "ratio"),
    [
        ("always_on", "always_on", 1.0),
        ("ALWAYS_OFF", "always_off", 1.0),
        ("parentbased", "parentbased", 1.0),
        ("head:0.1", "head", 0.1),
        ("head:1", "head", 1.0),
    ],
)
def test_sampling_parsing(value: str, kind: str, ratio: float) -> None:
    sampling = parse_sampling(value)
    assert sampling.kind == kind
    assert sampling.ratio == pytest.approx(ratio)


@pytest.mark.parametrize("value", ["head", "head:abc", "head:-1", "", "tail:0.1"])
def test_bad_sampling_is_rejected(value: str) -> None:
    with pytest.raises(SpecError):
        parse_sampling(value)


def test_interactive_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    answers = iter(
        [
            "1",            # language: python
            "1",            # framework: fastapi
            "4",            # backend: tempo
            "checkout-api", # service name
            "3",            # sampling: head:0.1
            "y",            # collector
            "n",            # compose
            str(tmp_path / "out"),
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    from otelgen.cli import interactive

    spec = interactive(stream=io.StringIO())
    assert spec.language.key == "python"
    assert spec.framework.key == "fastapi"
    assert spec.backend.key == "tempo"
    assert spec.service_name == "checkout-api"
    assert spec.sampling.kind == "head"
    assert spec.sampling.ratio == pytest.approx(0.1)
    assert spec.with_collector is True
    assert spec.with_compose is False


def test_interactive_rejects_a_bad_service_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = iter(
        ["python", "script", "console", "not valid", "checkout-api", "1", "out"]
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    from otelgen.cli import interactive

    spec = interactive(stream=io.StringIO())
    assert spec.service_name == "checkout-api"
    # The console backend needs neither a collector nor compose.
    assert spec.with_collector is False
    assert spec.with_compose is False


def test_module_entry_point_runs() -> None:
    result = subprocess.run(
        ["python3", "-m", "otelgen", "--list-targets"],
        capture_output=True,
        text=True,
        check=False,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert result.returncode == 0
    assert "Backends" in result.stdout


@pytest.mark.skipif(BASH is None, reason="bash is not available")
def test_generated_agent_script_is_valid_shell(tmp_path: Path) -> None:
    spec = build_spec(
        language="java",
        framework="spring-boot-agent",
        backend="honeycomb",
        service_name="billing",
        out_dir=tmp_path / "out",
        with_collector=False,
    )
    write_files(spec, render(spec))
    script = spec.out_dir / "run-with-agent.sh"
    result = subprocess.run(
        [BASH, "-n", str(script)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert script.stat().st_mode & 0o111, "script should be executable"


def test_format_targets_lists_every_framework() -> None:
    from otelgen import FRAMEWORKS

    output = format_targets()
    for (_language, framework) in FRAMEWORKS:
        assert framework in output
