"""Best-effort observation of real engine checkpoints.

Snapshots contain only scalar counts, dimensions, phases and property names.
They expose neither theories nor mutable solver/report objects. Observers are
synchronous; their own work should be short. No clock is read for progress.
"""


def notify(observer, phase, **fields):
    """Send a detached snapshot; an observer error must not abort checking."""
    if observer is None:
        return
    try:
        observer({'phase': phase, **fields})
    except Exception:
        # Progress is auxiliary. Solver/checker exceptions are handled by their
        # normal callers; exceptions from this observer do not change a result.
        pass
