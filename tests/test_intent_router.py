"""Testes do roteador de intenções."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.intent_router import detectar
from core.intents import sanitizar_comandos, intent_valido, normalizar_intent


@pytest.mark.parametrize(
    "comando, intent_esperado",
    [
        ("abrir chrome", "abrir_programa"),
        ("pesquisar dolar hoje", "buscar_web"),
        ("qual meu ip", "ip_local"),
        ("espaco em disco", "info_disco"),
        ("tocar musica", "tocar_musica"),
        ("diagnostico do pc", "diagnostico"),
        ("pare de falar", "parar_fala"),
        ("desligar assistente", "desligar_assistente"),
        ("gerar imagem de um gato", "gerar_imagem"),
        ("tirar print", "tirar_print"),
        ("quais processos", "info_processos"),
        ("aumentar volume", "volume_total"),
        ("bom dia", "conversa"),
        ("que horas sao", "conversa"),
    ],
)
def test_detectar_intents(comando: str, intent_esperado: str) -> None:
    resultado = detectar(comando, {})
    assert resultado is not None
    assert resultado["intent"] == intent_esperado


def test_detectar_abrir_programa_param() -> None:
    r = detectar("abrir spotify", {})
    assert r is not None
    assert r["intent"] == "abrir_programa"
    assert "spotify" in r["parametros"].get("programa", "")


def test_detectar_buscar_web_param() -> None:
    r = detectar("pesquisar cambio dolar", {})
    assert r is not None
    assert r["intent"] == "buscar_web"
    assert r["parametros"].get("termo")


def test_sanitizar_remove_invalidos() -> None:
    sujo = {
        "": {"intent": "ola", "parametros": {}},
        "sim": {"intent": "confirmar", "parametros": {}},
        "dolar agora": {"intent": "pesquisar_web", "parametros": {"pesquisa": "dolar"}},
        "crie imagem de gato": {"intent": "criar_imagem", "parametros": {"descricao": "gato"}},
    }
    limpo = sanitizar_comandos(sujo)
    assert "" not in limpo
    assert "sim" not in limpo
    assert limpo["dolar agora"]["intent"] == "buscar_web"
    assert limpo["dolar agora"]["parametros"]["termo"] == "dolar"
    assert limpo["crie imagem de gato"]["intent"] == "gerar_imagem"


def test_intent_valido() -> None:
    assert intent_valido("buscar_web")
    assert not intent_valido("pesquisar_web")
    assert not intent_valido("ola")


def test_normalizar_alias() -> None:
    n = normalizar_intent("pesquisar_web", {"pesquisa": "brasil"})
    assert n is not None
    intent, params = n
    assert intent == "buscar_web"
    assert params["termo"] == "brasil"
