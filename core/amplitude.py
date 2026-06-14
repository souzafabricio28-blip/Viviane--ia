import threading

_current_amplitude = 0.0
_lock = threading.Lock()


def set_amplitude(valor: float) -> None:
    global _current_amplitude
    with _lock:
        _current_amplitude = max(0.0, min(1.0, valor))


def get_amplitude() -> float:
    with _lock:
        return _current_amplitude


def reset() -> None:
    set_amplitude(0.0)
