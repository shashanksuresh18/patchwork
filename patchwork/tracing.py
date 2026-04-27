from __future__ import annotations

import os
from functools import wraps
from typing import Callable


def _noop_decorator(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


def _make_tracer() -> Callable:
    pub = os.getenv("LANGFUSE_PUBLIC_KEY")
    sec = os.getenv("LANGFUSE_SECRET_KEY")
    if pub and sec:
        try:
            from langfuse.decorators import observe
            return observe
        except ImportError:
            pass
    return _noop_decorator


traced = _make_tracer()
