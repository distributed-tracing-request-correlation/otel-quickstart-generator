"""Target/backend model and validation for otelgen.

A :class:`Spec` is the fully validated description of one generation run:
which language and framework to wire up, which backend to export to, how to
sample, and where to write the result. Everything else in the package treats
the ``Spec`` as read-only input.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from .presets import BACKENDS, FRAMEWORKS, LANGUAGES, Backend, Framework, Language

SAMPLING_ALWAYS_ON = "always_on"
SAMPLING_ALWAYS_OFF = "always_off"
SAMPLING_PARENTBASED = "parentbased"
SAMPLING_HEAD = "head"

_SERVICE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,62}$")


class SpecError(ValueError):
    """Raised when a requested combination is not supported or is malformed."""


@dataclass(frozen=True)
class Sampling:
    """Resolved sampling configuration.

    ``kind`` is one of ``always_on``, ``always_off``, ``parentbased`` or
    ``head``. ``ratio`` is only meaningful for ``head``.
    """

    kind: str
    ratio: float = 1.0

    @property
    def is_ratio(self) -> bool:
        return self.kind == SAMPLING_HEAD

    @property
    def description(self) -> str:
        if self.kind == SAMPLING_HEAD:
            return f"head-based, {self.ratio:.4g} of root traces sampled"
        if self.kind == SAMPLING_ALWAYS_ON:
            return "every trace sampled (development default)"
        if self.kind == SAMPLING_ALWAYS_OFF:
            return "no traces sampled"
        return "parent decision honoured, root traces always sampled"

    @property
    def otel_traces_sampler(self) -> str:
        """The value for the ``OTEL_TRACES_SAMPLER`` environment variable."""
        if self.kind == SAMPLING_HEAD:
            return "parentbased_traceidratio"
        if self.kind == SAMPLING_ALWAYS_ON:
            return "always_on"
        if self.kind == SAMPLING_ALWAYS_OFF:
            return "always_off"
        return "parentbased_always_on"

    @property
    def otel_traces_sampler_arg(self) -> str:
        return f"{self.ratio:.4g}" if self.kind == SAMPLING_HEAD else ""


def parse_sampling(value: str) -> Sampling:
    """Parse a ``--sampling`` value such as ``always_on`` or ``head:0.1``."""
    raw = (value or "").strip().lower()
    if not raw:
        raise SpecError("sampling value is empty")
    if raw in (SAMPLING_ALWAYS_ON, "alwayson", "always-on"):
        return Sampling(SAMPLING_ALWAYS_ON)
    if raw in (SAMPLING_ALWAYS_OFF, "alwaysoff", "always-off"):
        return Sampling(SAMPLING_ALWAYS_OFF)
    if raw in (SAMPLING_PARENTBASED, "parent-based", "parent"):
        return Sampling(SAMPLING_PARENTBASED)
    if raw.startswith("head"):
        _, _, arg = raw.partition(":")
        if not arg:
            raise SpecError(
                "head sampling needs a ratio, for example 'head:0.1'"
            )
        try:
            ratio = float(arg)
        except ValueError as exc:  # pragma: no cover - message tested instead
            raise SpecError(f"'{arg}' is not a valid sampling ratio") from exc
        if not 0.0 <= ratio <= 1.0:
            raise SpecError(
                f"sampling ratio must be between 0 and 1, got {ratio}"
            )
        return Sampling(SAMPLING_HEAD, ratio)
    raise SpecError(
        f"unknown sampling strategy '{value}'. "
        "Use always_on, always_off, parentbased or head:<ratio>."
    )


def validate_service_name(name: str) -> str:
    name = (name or "").strip()
    if not _SERVICE_NAME_RE.match(name):
        raise SpecError(
            "service name must be 1-63 characters of letters, digits, dot, "
            f"dash or underscore, starting with a letter or digit (got {name!r})"
        )
    return name


@dataclass(frozen=True)
class Spec:
    """A validated, fully resolved generation request."""

    language: Language
    framework: Framework
    backend: Backend
    service_name: str
    service_version: str = "0.1.0"
    environment: str = "development"
    sampling: Sampling = field(default_factory=lambda: Sampling(SAMPLING_PARENTBASED))
    out_dir: Path = field(default_factory=lambda: Path("otel-quickstart"))
    with_collector: bool = True
    with_compose: bool = True

    # ------------------------------------------------------------------
    # Derived values used by the templates
    # ------------------------------------------------------------------
    @property
    def target(self) -> str:
        return f"{self.language.key}/{self.framework.key}"

    @property
    def exports_to_collector(self) -> bool:
        """True when the application sends spans to the local collector."""
        return self.with_collector and not self.backend.is_console

    @property
    def protocol(self) -> str:
        """``grpc``, ``http`` or ``console`` as seen by the application."""
        if self.backend.is_console:
            return "console"
        if self.exports_to_collector:
            return self.backend.collector_ingest_protocol
        return self.backend.protocol

    @property
    def protocol_label(self) -> str:
        """Human-readable transport name."""
        return {"grpc": "gRPC", "http": "HTTP", "console": "console"}[self.protocol]

    @property
    def endpoint(self) -> str:
        """The OTLP endpoint the *application* should use."""
        if self.backend.is_console:
            return ""
        if self.exports_to_collector:
            return (
                "http://localhost:4317"
                if self.protocol == "grpc"
                else "http://localhost:4318"
            )
        return self.backend.direct_endpoint

    @property
    def traces_endpoint(self) -> str:
        """Signal-specific endpoint (OTLP/HTTP needs the ``/v1/traces`` path)."""
        if self.protocol == "http" and self.endpoint:
            return self.endpoint.rstrip("/") + "/v1/traces"
        return self.endpoint

    @property
    def headers(self) -> tuple[tuple[str, str], ...]:
        """Exporter headers the application needs, as ``(name, env var)``.

        Empty when spans go through the collector: the credential then lives in
        the collector configuration instead of the application.
        """
        if self.exports_to_collector or self.backend.is_console:
            return ()
        return self.backend.header_env

    @property
    def insecure(self) -> bool:
        """True when the gRPC exporter should skip TLS (localhost collector)."""
        if self.protocol != "grpc":
            return False
        return self.endpoint.startswith("http://")

    @property
    def renders_collector(self) -> bool:
        """A collector is only useful when spans leave the process."""
        return self.with_collector and not self.backend.is_console

    @property
    def renders_compose(self) -> bool:
        """Compose is only useful when there is something to run locally."""
        if self.backend.is_console:
            return False
        return self.with_compose and (
            self.with_collector or bool(self.backend.compose_services)
        )

    @property
    def slug(self) -> str:
        return f"{self.language.key}-{self.framework.key}-{self.backend.key}"


def build_spec(
    *,
    language: str,
    framework: str,
    backend: str,
    service_name: str,
    service_version: str = "0.1.0",
    environment: str = "development",
    sampling: str = "parentbased",
    out_dir: str | Path = "otel-quickstart",
    with_collector: bool = True,
    with_compose: bool = True,
) -> Spec:
    """Validate raw CLI input and return a :class:`Spec`.

    Raises :class:`SpecError` with an actionable message for every bad input.
    """
    lang_key = (language or "").strip().lower()
    if lang_key not in LANGUAGES:
        raise SpecError(
            f"unknown language '{language}'. Supported: "
            + ", ".join(sorted(LANGUAGES))
        )
    lang = LANGUAGES[lang_key]

    fw_key = (framework or "").strip().lower()
    if fw_key not in lang.frameworks:
        raise SpecError(
            f"unknown framework '{framework}' for language '{lang_key}'. "
            "Supported: " + ", ".join(lang.frameworks)
        )
    fw = FRAMEWORKS[(lang_key, fw_key)]

    be_key = (backend or "").strip().lower()
    if be_key not in BACKENDS:
        raise SpecError(
            f"unknown backend '{backend}'. Supported: "
            + ", ".join(sorted(BACKENDS))
        )
    be = BACKENDS[be_key]

    return Spec(
        language=lang,
        framework=fw,
        backend=be,
        service_name=validate_service_name(service_name),
        service_version=(service_version or "0.1.0").strip(),
        environment=(environment or "development").strip(),
        sampling=parse_sampling(sampling),
        out_dir=Path(out_dir),
        with_collector=bool(with_collector),
        with_compose=bool(with_compose),
    )


def all_combinations() -> list[tuple[str, str, str]]:
    """Every supported ``(language, framework, backend)`` triple."""
    combos: list[tuple[str, str, str]] = []
    for lang_key, lang in LANGUAGES.items():
        for fw_key in lang.frameworks:
            for be_key in BACKENDS:
                combos.append((lang_key, fw_key, be_key))
    return combos
