import gc
import time
from collections.abc import Callable


def measure_ms(fn: Callable[[], object], *, runs: int = 100, warmup: int = 5) -> list[float]:
    """Run fn repeatedly and return sorted durations in milliseconds, after warm-up.

    Garbage collection is paused while timing, as `timeit` does: a collection pass
    landing inside one run measures the interpreter, not the code, and was enough to
    push an 8 ms p50 past 50 ms at p95 on slower machines."""
    for _ in range(warmup):
        fn()
    times = []
    gc_was_enabled = gc.isenabled()
    gc.collect()
    gc.disable()
    try:
        for _ in range(runs):
            start = time.perf_counter()
            fn()
            times.append((time.perf_counter() - start) * 1000)
    finally:
        if gc_was_enabled:
            gc.enable()
    return sorted(times)


def percentile(sorted_times: list[float], p: float) -> float:
    index = min(len(sorted_times) - 1, int(len(sorted_times) * p))
    return sorted_times[index]