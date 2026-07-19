"""otel-quickstart-generator: scaffold a working OpenTelemetry tracing setup.

Run it as a module::

    python -m otelgen --list-targets

Or use it as a library::

    from otelgen import build_spec, render

    spec = build_spec(
        language="python",
        framework="fastapi",
        backend="tempo",
        service_name="checkout-api",
        sampling="head:0.1",
    )
    files = render(spec)  # {relative path: content}
"""

from .presets import BACKENDS, FRAMEWORKS, LANGUAGES
from .renderer import dry_run_report, render, write_files
from .spec import Spec, SpecError, build_spec, parse_sampling

__version__ = "1.0.0"

__all__ = [
    "BACKENDS",
    "FRAMEWORKS",
    "LANGUAGES",
    "Spec",
    "SpecError",
    "__version__",
    "build_spec",
    "dry_run_report",
    "parse_sampling",
    "render",
    "write_files",
]
