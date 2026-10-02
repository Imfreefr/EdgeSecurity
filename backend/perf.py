"""Opt-in request timing; never records SQL values, tokens or response bodies."""
from contextvars import ContextVar
from contextlib import contextmanager
from functools import wraps
from time import perf_counter

current = ContextVar("edge_perf", default=None)


@contextmanager
def measure(name):
    metrics = current.get()
    if metrics is None:
        yield
        return
    start = perf_counter()
    try:
        yield
    finally:
        metrics[name] = metrics.get(name, 0) + (perf_counter() - start) * 1000


def auth_timing(function):
    @wraps(function)
    def timed(*args, **kwargs):
        metrics = current.get()
        if metrics is None or metrics.get("auth_depth", 0):
            return function(*args, **kwargs)
        metrics["auth_depth"] = 1
        try:
            with measure("auth_ms"):
                return function(*args, **kwargs)
        finally:
            metrics["auth_depth"] = 0
    return timed
