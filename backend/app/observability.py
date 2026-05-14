import logging
import time
from contextlib import contextmanager
from typing import Optional

PHASE_LOGGER_NAME = "rabbitpedia.phase"

_phase_logger = logging.getLogger(PHASE_LOGGER_NAME)
if not _phase_logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] phase=%(phase)s sid=%(session_id)s ms=%(elapsed_ms)d ok=%(ok)s %(message)s"
    ))
    _phase_logger.addHandler(_h)
_phase_logger.setLevel(logging.INFO)
_phase_logger.propagate = True  # so caplog/pytest can see records


def log_phase(
    phase: str,
    session_id: str,
    elapsed_ms: int,
    ok: bool,
    extra: Optional[dict] = None,
    message: str = "",
) -> None:
    payload = {
        "phase": phase,
        "session_id": session_id,
        "elapsed_ms": int(elapsed_ms),
        "ok": ok,
    }
    if extra:
        for k, v in extra.items():
            if k not in payload:
                payload[k] = v
    level = logging.INFO if ok else logging.WARNING
    _phase_logger.log(level, message or phase, extra=payload)


@contextmanager
def phase_timer(phase: str, session_id: str, extra: Optional[dict] = None):
    start = time.time()
    state = {"ok": True, "extra": dict(extra or {})}
    try:
        yield state
    except Exception as e:
        state["ok"] = False
        state["extra"]["err"] = f"{type(e).__name__}: {e}"
        raise
    finally:
        elapsed_ms = int((time.time() - start) * 1000)
        log_phase(phase, session_id, elapsed_ms, state["ok"], state["extra"])
