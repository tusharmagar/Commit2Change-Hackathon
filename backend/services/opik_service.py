from __future__ import annotations

import logging
from typing import Callable, TypeVar

from config import settings

try:
    import opik  # type: ignore
except Exception:  # pragma: no cover
    opik = None

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
