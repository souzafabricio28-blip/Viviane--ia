from __future__ import annotations

import json
import logging
from pathlib import Path

from core.intents import chave_aprendivel, intent_valido, normalizar_intent, sanitizar_comandos
from core.settings import settings

log = logging.getLogger("DarkSON")


class Aprendizado:
    def __init__(self) -> None:
        self.caminho = settings.data_dir / "comandos_aprendidos.json"
        self.pendentes = settings.data_dir / "comandos_pendentes.txt"
        if not self.caminho.exists():
            with open(self.caminho, "w", encoding="utf-8") as f:
                json.dump({}, f)
        self._sanitizar_arquivo()

    def _sanitizar_arquivo(self) -> None:
        dados = self._ler_raw()
        limpo = sanitizar_comandos(dados)
        if limpo != dados:
            removidos = len(dados) - len(limpo)
            log.info("Comandos aprendidos: %d entradas inválidas removidas", removidos)
            self._gravar(limpo)

    def _ler_raw(self) -> dict:
        try:
            with open(self.caminho, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _gravar(self, dados: dict) -> None:
        with open(self.caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)

    def carregar(self) -> dict[str, dict]:
        return self._ler_raw()

    def aprender(self, comando: str, intent: str, parametros: dict) -> bool:
        chave = comando.lower().strip()
        if not chave_aprendivel(chave):
            log.debug("Comando não aprendível ignorado: %r", chave[:40])
            return False

        norm = normalizar_intent(intent, parametros)
        if norm is None:
            log.warning("Intent inválido não gravado: %s -> %s", chave[:40], intent)
            return False

        intent_ok, params_ok = norm
        if not intent_valido(intent_ok):
            return False

        dados = self.carregar()
        dados[chave] = {"intent": intent_ok, "parametros": params_ok}
        try:
            self._gravar(dados)
            log.info("Comando aprendido: %r -> %s", chave[:50], intent_ok)
            return True
        except Exception as e:
            log.warning("Erro ao aprender: %s", e)
            return False

    def registrar_desconhecido(self, comando: str) -> None:
        if not chave_aprendivel(comando):
            return
        try:
            with open(self.pendentes, "a", encoding="utf-8") as f:
                f.write(f"{comando}\n")
        except Exception:
            pass
