"""Command-line interface for otel-quickstart-generator.

Run ``python -m otelgen`` with no arguments for the interactive prompt, or pass
flags for a scripted run. ``python -m otelgen --list-targets`` prints the
supported matrix.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence, TextIO

from . import presets, renderer
from .presets import BACKENDS, FRAMEWORKS, LANGUAGES
from .spec import Spec, SpecError, build_spec, parse_sampling, validate_service_name

PROG = "python -m otelgen"

EPILOG = """\
examples:
  python -m otelgen
      interactive: prompts for language, framework, backend, service and sampling

  python -m otelgen --language python --framework fastapi --backend tempo \\
      --service-name checkout-api --sampling head:0.1 --out ./otel-quickstart
      generate a FastAPI + Grafana Tempo setup keeping 10% of root traces

  python -m otelgen --language go --framework grpc --backend console --dry-run
      show what would be written, without writing anything

Further reading: https://www.distributed-tracing.com/
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "Generate a complete OpenTelemetry tracing setup for a given "
            "language, framework and backend."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--list-targets",
        action="store_true",
        help="print the supported language/framework/backend matrix and exit",
    )
    parser.add_argument(
        "--language",
        "-l",
        choices=sorted(LANGUAGES),
        help="target language",
    )
    parser.add_argument(
        "--framework",
        "-f",
        help="target framework (see --list-targets)",
    )
    parser.add_argument(
        "--backend",
        "-b",
        choices=sorted(BACKENDS),
        help="where spans are sent",
    )
    parser.add_argument(
        "--service-name",
        "-s",
        help="value of the service.name resource attribute",
    )
    parser.add_argument(
        "--service-version",
        default="0.1.0",
        help="value of service.version (default: %(default)s)",
    )
    parser.add_argument(
        "--environment",
        default="development",
        help="value of deployment.environment.name (default: %(default)s)",
    )
    parser.add_argument(
        "--sampling",
        default="parentbased",
        metavar="STRATEGY",
        help=(
            "always_on, always_off, parentbased or head:<ratio> "
            "(default: %(default)s)"
        ),
    )
    parser.add_argument(
        "--out",
        "-o",
        default="otel-quickstart",
        metavar="DIR",
        help="output directory (default: %(default)s)",
    )
    collector = parser.add_mutually_exclusive_group()
    collector.add_argument(
        "--with-collector",
        dest="with_collector",
        action="store_true",
        default=True,
        help="generate an OpenTelemetry Collector config and export via it "
        "(default)",
    )
    collector.add_argument(
        "--no-collector",
        dest="with_collector",
        action="store_false",
        help="export straight from the application to the backend",
    )
    compose = parser.add_mutually_exclusive_group()
    compose.add_argument(
        "--with-compose",
        dest="with_compose",
        action="store_true",
        default=True,
        help="generate a docker-compose.yml for the local stack (default)",
    )
    compose.add_argument(
        "--no-compose",
        dest="with_compose",
        action="store_false",
        help="skip docker-compose.yml",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the file tree and diffs, write nothing",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing files",
    )
    return parser


# ----------------------------------------------------------------------
# --list-targets
# ----------------------------------------------------------------------
def format_targets() -> str:
    lines: list[str] = ["Languages and frameworks", ""]
    for lang in LANGUAGES.values():
        lines.append(f"  {lang.key}  ({lang.label}, {lang.runtime})")
        for fw_key in lang.frameworks:
            fw = FRAMEWORKS[(lang.key, fw_key)]
            lines.append(f"    {fw_key:<20} {fw.summary}")
        lines.append("")
    lines.append("Backends")
    lines.append("")
    for backend in BACKENDS.values():
        lines.append(f"  {backend.key:<12} {backend.label}")
        lines.append(f"  {'':<12} {backend.note}")
    lines.append("")
    lines.append("Sampling")
    lines.append("")
    lines.append("  always_on      record every trace")
    lines.append("  always_off     record nothing")
    lines.append("  parentbased    honour the caller, sample new traces")
    lines.append("  head:<ratio>   parent-based ratio, e.g. head:0.1")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# Interactive mode
# ----------------------------------------------------------------------
def _choose(
    prompt: str,
    options: Sequence[tuple[str, str]],
    *,
    default: int = 0,
    stream: TextIO,
) -> str:
    """Ask the user to pick one of ``options`` (``(key, description)``)."""
    print(f"\n{prompt}", file=stream)
    for index, (key, description) in enumerate(options, start=1):
        marker = "*" if index - 1 == default else " "
        print(f" {marker} {index}) {key:<20} {description}", file=stream)
    while True:
        raw = input(f"choice [{default + 1}]: ").strip()
        if not raw:
            return options[default][0]
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][0]
        for key, _ in options:
            if raw == key:
                return key
        print("  not one of the options", file=stream)


def _ask(prompt: str, default: str, stream: TextIO) -> str:
    raw = input(f"{prompt} [{default}]: ").strip()
    return raw or default


def _ask_bool(prompt: str, default: bool, stream: TextIO) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{prompt} [{suffix}]: ").strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  answer y or n", file=stream)


def interactive(stream: TextIO = sys.stdout) -> Spec:
    """Prompt through language, framework, backend, service name and sampling."""
    print("otel-quickstart-generator", file=stream)
    print(
        "Answer five questions and get a working tracing setup. "
        "Enter accepts the default.",
        file=stream,
    )

    language = _choose(
        "Language",
        [(lang.key, lang.label) for lang in LANGUAGES.values()],
        stream=stream,
    )
    lang = LANGUAGES[language]
    framework = _choose(
        "Framework",
        [
            (fw_key, FRAMEWORKS[(language, fw_key)].summary)
            for fw_key in lang.frameworks
        ],
        stream=stream,
    )
    backend = _choose(
        "Backend",
        [(be.key, be.label) for be in BACKENDS.values()],
        default=list(BACKENDS).index("console"),
        stream=stream,
    )

    while True:
        service_name = _ask("\nService name", "my-service", stream)
        try:
            validate_service_name(service_name)
            break
        except SpecError as exc:
            print(f"  {exc}", file=stream)

    sampling_choice = _choose(
        "Sampling",
        [
            ("parentbased", "honour the caller, sample every new trace"),
            ("always_on", "record everything (development)"),
            ("head:0.1", "keep 10% of root traces"),
            ("head:0.01", "keep 1% of root traces"),
            ("always_off", "record nothing locally"),
        ],
        stream=stream,
    )

    backend_obj = BACKENDS[backend]
    if backend_obj.is_console:
        with_collector = False
        with_compose = False
    else:
        with_collector = _ask_bool(
            "\nExport via a local OpenTelemetry Collector?", True, stream
        )
        with_compose = _ask_bool("Generate docker-compose.yml?", True, stream)

    out_dir = _ask("Output directory", "otel-quickstart", stream)

    return build_spec(
        language=language,
        framework=framework,
        backend=backend,
        service_name=service_name,
        sampling=sampling_choice,
        out_dir=out_dir,
        with_collector=with_collector,
        with_compose=with_compose,
    )


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------
def _summarise(spec: Spec, rendered: dict[str, str], stream: TextIO) -> None:
    print(f"\n{spec.language.label} / {spec.framework.label} -> {spec.backend.label}", file=stream)
    print(f"  service     {spec.service_name} v{spec.service_version} ({spec.environment})", file=stream)
    if spec.protocol == "console":
        print("  export      console (stdout)", file=stream)
    else:
        via = " via the local collector" if spec.exports_to_collector else ""
        print(f"  export      OTLP/{spec.protocol}{via} -> {spec.traces_endpoint}", file=stream)
    print(f"  sampling    {spec.sampling.description}", file=stream)
    print(f"  files       {len(rendered)}", file=stream)


def main(argv: Sequence[str] | None = None, stream: TextIO | None = None) -> int:
    stream = stream or sys.stdout
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_targets:
        print(format_targets(), file=stream)
        return 0

    try:
        if not argv:
            spec = interactive(stream)
        else:
            missing = [
                flag
                for flag, value in (
                    ("--language", args.language),
                    ("--framework", args.framework),
                    ("--backend", args.backend),
                    ("--service-name", args.service_name),
                )
                if not value
            ]
            if missing:
                parser.error(
                    "missing required option(s): "
                    + ", ".join(missing)
                    + "  (run without arguments for interactive mode)"
                )
            # Validate the sampling string before anything else touches disk.
            parse_sampling(args.sampling)
            spec = build_spec(
                language=args.language,
                framework=args.framework,
                backend=args.backend,
                service_name=args.service_name,
                service_version=args.service_version,
                environment=args.environment,
                sampling=args.sampling,
                out_dir=args.out,
                with_collector=args.with_collector,
                with_compose=args.with_compose,
            )
    except SpecError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (KeyboardInterrupt, EOFError):
        print("\naborted", file=sys.stderr)
        return 130

    rendered = renderer.render(spec)

    if args.dry_run:
        print(renderer.dry_run_report(spec, rendered), end="", file=stream)
        _summarise(spec, rendered, stream)
        print("\ndry run: nothing was written", file=stream)
        return 0

    try:
        result = renderer.write_files(spec, rendered, force=args.force)
    except renderer.OverwriteError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(renderer.file_tree(rendered, str(spec.out_dir)), file=stream)
    _summarise(spec, rendered, stream)
    if result.overwritten:
        print(f"  overwrote   {len(result.overwritten)}", file=stream)
    print(
        f"\nNext: read {Path(spec.out_dir) / 'OTEL_SETUP.md'}",
        file=stream,
    )
    return 0


__all__ = ["build_parser", "format_targets", "interactive", "main", "presets"]
