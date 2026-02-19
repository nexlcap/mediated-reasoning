"""Optional Langfuse observability integration (SDK v3 / OTEL-based).

Enabled only when LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY are set.
Missing keys or missing packages → all functions are silent no-ops.
"""
import os
from contextlib import contextmanager
from typing import Optional

_enabled = False
_langfuse = None


def setup() -> None:
    global _enabled, _langfuse
    pk = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    sk = os.getenv("LANGFUSE_SECRET_KEY", "")
    if not (pk and sk):
        return
    try:
        from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
        AnthropicInstrumentor().instrument()
        from langfuse import get_client
        _langfuse = get_client()
        _enabled = True
    except ImportError:
        pass  # optional deps not installed — silent no-op


def is_enabled() -> bool:
    return _enabled


def get_otel_context():
    """Return the current OpenTelemetry context (for thread propagation)."""
    if not _enabled:
        return None
    from opentelemetry import context as otel_context
    return otel_context.get_current()


@contextmanager
def trace(name: str, input: Optional[str] = None, metadata: Optional[dict] = None):
    """Top-level Langfuse trace. Flushes on exit."""
    if not _enabled or _langfuse is None:
        yield
        return
    with _langfuse.start_as_current_observation(
        as_type="span", name=name, input=input, metadata=metadata or {}
    ):
        yield
    _langfuse.flush()


@contextmanager
def span(name: str, metadata: Optional[dict] = None):
    """Child span within an active trace."""
    if not _enabled or _langfuse is None:
        yield
        return
    with _langfuse.start_as_current_observation(
        as_type="span", name=name, metadata=metadata or {}
    ):
        yield
