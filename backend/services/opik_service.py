from __future__ import annotations

import logging
from typing import Callable, TypeVar

from config import settings

try:
    import opik  # type: ignore
    from opik import opik_context  # type: ignore
except Exception:  # pragma: no cover
    opik = None
    opik_context = None

T = TypeVar("T", bound=Callable)


def configure_opik() -> None:
    if not opik:
        return
    if not settings.OPIK_API_KEY:
        return
    try:
        # Opik reads project/workspace from env or ~/.opik.config
        opik.configure(use_local=False)
    except Exception as exc:
        logging.getLogger(__name__).warning("Failed to configure Opik: %s", exc)


def track(name: str) -> Callable[[T], T]:
    if opik:
        return opik.track(name=name)

    def decorator(func: T) -> T:
        return func

    return decorator


def set_trace_context(thread_id: str | None = None, metadata: dict | None = None, tags: list[str] | None = None) -> None:
    if not opik_context:
        return
    try:
        opik_context.update_current_trace(
            thread_id=thread_id,
            metadata=metadata,
            tags=tags,
        )
    except Exception:
        # Avoid breaking the app on tracing issues
        return
