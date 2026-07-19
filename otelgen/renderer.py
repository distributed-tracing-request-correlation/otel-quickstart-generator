"""Template rendering and file writing.

``render(spec)`` turns a :class:`~otelgen.spec.Spec` into an ordered mapping of
relative output path to file content, entirely in memory. ``write_files`` then
puts that on disk, and ``dry_run_report`` describes what would change without
touching anything.
"""

from __future__ import annotations

import difflib
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from . import presets
from .presets import EXECUTABLE_OUTPUTS, FileSpec, plan_files
from .spec import Spec

TEMPLATE_DIR = Path(__file__).parent / "templates"


class RenderError(RuntimeError):
    """Raised when a target cannot be rendered."""


class OverwriteError(RuntimeError):
    """Raised when writing would clobber an existing file without --force."""

    def __init__(self, paths: list[Path]) -> None:
        self.paths = paths
        listed = "\n".join(f"  {p}" for p in paths)
        super().__init__(
            "refusing to overwrite existing files (pass --force to replace "
            f"them):\n{listed}"
        )


def build_environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
    )
    env.filters["indent_block"] = _indent_block
    env.filters["camel"] = _camel
    return env


def _camel(value: str) -> str:
    """``HONEYCOMB_API_KEY`` -> ``honeycombApiKey``."""
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", value.lower()) if p]
    if not parts:
        return ""
    return parts[0] + "".join(p.title() for p in parts[1:])


def _indent_block(text: str, width: int) -> str:
    pad = " " * width
    return "\n".join(pad + line if line else line for line in text.splitlines())


def _context(spec: Spec, file_spec: FileSpec) -> dict[str, object]:
    ctx: dict[str, object] = {
        "spec": spec,
        "lang": spec.language,
        "framework": spec.framework,
        "backend": spec.backend,
        "sampling": spec.sampling,
        "service_name": spec.service_name,
        "service_version": spec.service_version,
        "environment": spec.environment,
        "article": presets.article(file_spec.article),
        "article_url": presets.article,
        "site": presets.SITE,
        "output_path": file_spec.output,
        "generator": "otel-quickstart-generator",
    }
    ctx.update(file_spec.extra_context)
    return ctx


def render(spec: Spec) -> dict[str, str]:
    """Render every file for ``spec``. Returns ``{relative path: content}``."""
    env = build_environment()
    out: dict[str, str] = {}
    for file_spec in plan_files(spec):
        try:
            template = env.get_template(file_spec.template)
        except Exception as exc:  # pragma: no cover - configuration error
            raise RenderError(
                f"template {file_spec.template!r} is missing for target "
                f"{spec.target}"
            ) from exc
        content = template.render(**_context(spec, file_spec))
        if not content.endswith("\n"):
            content += "\n"
        out[file_spec.output] = content
    return out


@dataclass
class WriteResult:
    created: list[Path]
    overwritten: list[Path]

    @property
    def all_paths(self) -> list[Path]:
        return sorted(self.created + self.overwritten)


def write_files(
    spec: Spec, rendered: dict[str, str], *, force: bool = False
) -> WriteResult:
    """Write rendered content under ``spec.out_dir``.

    Existing files are left untouched and reported unless ``force`` is set.
    """
    out_dir = spec.out_dir
    existing = [out_dir / rel for rel in rendered if (out_dir / rel).exists()]
    if existing and not force:
        raise OverwriteError(sorted(existing))

    result = WriteResult(created=[], overwritten=[])
    for rel, content in rendered.items():
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        already = path.exists()
        path.write_text(content, encoding="utf-8")
        if rel in EXECUTABLE_OUTPUTS:
            mode = path.stat().st_mode
            path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        (result.overwritten if already else result.created).append(path)
    return result


def file_tree(rendered: dict[str, str], root: str) -> str:
    """Render an ASCII tree of the output paths."""
    lines = [f"{root}/"]
    paths = sorted(rendered)
    for index, rel in enumerate(paths):
        last = index == len(paths) - 1
        prefix = "`-- " if last else "|-- "
        size = len(rendered[rel].encode("utf-8"))
        lines.append(f"{prefix}{rel}  ({size:,} bytes)")
    return "\n".join(lines)


def dry_run_report(spec: Spec, rendered: dict[str, str]) -> str:
    """Describe the effect of a run without writing anything.

    Shows the file tree, and a unified diff for every file that already exists
    with different content.
    """
    parts = [file_tree(rendered, str(spec.out_dir))]
    diffs: list[str] = []
    for rel in sorted(rendered):
        path = spec.out_dir / rel
        if not path.exists():
            continue
        try:
            current = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            diffs.append(f"--- {path} (unreadable, would be overwritten)")
            continue
        if current == rendered[rel]:
            diffs.append(f"= {rel} (unchanged)")
            continue
        diff = difflib.unified_diff(
            current.splitlines(keepends=True),
            rendered[rel].splitlines(keepends=True),
            fromfile=f"{rel} (existing)",
            tofile=f"{rel} (generated)",
        )
        diffs.append("".join(diff).rstrip("\n"))
    if diffs:
        parts.append("")
        parts.append("Existing files:")
        parts.extend(diffs)
    return "\n".join(parts) + "\n"


def relative_to_cwd(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


__all__ = [
    "OverwriteError",
    "RenderError",
    "WriteResult",
    "build_environment",
    "dry_run_report",
    "file_tree",
    "relative_to_cwd",
    "render",
    "write_files",
]
