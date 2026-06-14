from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

_lock = threading.Lock()
_historico: list[dict] = []


def registrar(tipo: str, texto: str) -> None:
    with _lock:
        _historico.append({
            "tipo": tipo,
            "texto": texto,
            "hora": datetime.now().strftime("%H:%M:%S"),
        })
        if len(_historico) > 200:
            _historico.pop(0)


def obter_historico() -> list[dict]:
    with _lock:
        return list(_historico)


def limpar() -> None:
    with _lock:
        _historico.clear()
