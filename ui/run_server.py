"""Inicia o servidor web e grava o PID para encerramento seguro."""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.settings import settings
from ui.web_app import iniciar_servidor

if __name__ == "__main__":
    pid_path = settings.data_dir / "web_server.pid"
    with open(pid_path, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    try:
        iniciar_servidor()
    finally:
        try:
            pid_path.unlink(missing_ok=True)
        except Exception:
            pass
