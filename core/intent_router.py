from __future__ import annotations

import importlib.util
import json
import logging
import random
import re as _re
from datetime import datetime
from pathlib import Path

import yaml

log = logging.getLogger("DarkSON")

_RULES_PATH = Path(__file__).parent / "rules.yaml"

_ACCENT_MAP = str.maketrans({
    "á": "a", "à": "a", "â": "a", "ã": "a", "ä": "a",
    "é": "e", "è": "e", "ê": "e", "ë": "e",
    "í": "i", "ì": "i", "î": "i", "ï": "i",
    "ó": "o", "ò": "o", "ô": "o", "õ": "o", "ö": "o",
    "ú": "u", "ù": "u", "û": "u", "ü": "u",
    "ç": "c", "ñ": "n",
    "Á": "a", "À": "a", "Â": "a", "Ã": "a", "Ä": "a",
    "É": "e", "È": "e", "Ê": "e", "Ë": "e",
    "Í": "i", "Ì": "i", "Î": "i", "Ï": "i",
    "Ó": "o", "Ò": "o", "Ô": "o", "Õ": "o", "Ö": "o",
    "Ú": "u", "Ù": "u", "Û": "u", "Ü": "u",
    "Ç": "c", "Ñ": "n",
})


def _normalize(texto: str) -> str:
    return texto.translate(_ACCENT_MAP)

_CARREGADO: list[dict] | None = None


def _carregar_regras() -> list[dict]:
    global _CARREGADO
    if _CARREGADO is not None:
        return _CARREGADO
    try:
        with open(_RULES_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        _CARREGADO = data.get("intents", [])
    except Exception as e:
        log.warning(f"Erro ao carregar rules.yaml: {e}")
        _CARREGADO = []
    return _CARREGADO


def _match_keyword(c: str, rule: dict) -> dict | None:
    words = [_normalize(w) if isinstance(w, str) else w for w in rule["words"]]
    if not any(p in c for p in words):
        return None
    params = dict(rule.get("params", {}))
    extra = rule.get("extract", {})
    for nome, cfg in extra.items():
        marker = cfg.get("marker", "")
        if isinstance(marker, str):
            marker = f" {marker} " if marker else ""
        if marker and marker in c:
            valor = c.split(marker)[-1].strip()
            if cfg.get("transform") == "title":
                valor = valor.title()
            params[nome] = valor
        else:
            params[nome] = cfg.get("default", "")
    mapa = rule.get("map")
    if mapa:
        for k, v in mapa.items():
            if k in c:
                params[rule.get("param", "programa")] = v
                break
    return {"intent": rule["name"], "parametros": params}


def _match_prefix(c: str, rule: dict) -> dict | None:
    param = rule["param"]
    stopwords = [_normalize(w) for w in rule.get("stopwords", [])]
    excluir = [_normalize(w) for w in rule.get("exclude", [])]

    for prefixo in [_normalize(p) for p in rule["prefixes"]]:
        prefixo_lower = prefixo.lower()
        if not c.startswith(prefixo_lower):
            continue
        resto = c[len(prefixo_lower):].strip()
        if stopwords:
            padrao = r"^(?:" + "|".join(stopwords) + r")\s+"
            resto = _re.sub(padrao, "", resto).strip()
        if resto and resto not in excluir:
            return {"intent": rule["name"], "parametros": {param: resto}}
    return None


def _match_hora(c: str) -> dict | None:
    if any(p in c for p in ("horas", "hora", "que horas", "horario")):
        hora = datetime.now().strftime("%H:%M")
        return {"intent": "conversa", "parametros": {}, "resposta": f"Sao {hora}"}
    return None


def _match_data(c: str) -> dict | None:
    if any(p in c for p in ("data", "que dia", "dia e hoje", "dia de hoje")):
        data = datetime.now().strftime("%d de %B de %Y")
        return {"intent": "conversa", "parametros": {}, "resposta": f"Hoje e {data}"}
    return None


def _match_cumprimento(c: str) -> dict | None:
    palavras = set(c.split())
    if not (any(p in c for p in ("boa noite", "boa tarde", "bom dia", "e ai", "e aí")) or
            any(p in palavras for p in ("ola", "oi", "hey", "fala"))):
        return None
    fixas = {"boa noite": "Boa noite", "boa tarde": "Boa tarde", "bom dia": "Bom dia"}
    for k, v in fixas.items():
        if k in c:
            return {"intent": "conversa", "parametros": {}, "resposta": v}
    return {"intent": "conversa", "parametros": {}, "resposta": random.choice(["Oi", "Fala", "E aí"])}


def _match_shutdown_timer(c: str) -> dict | None:
    if "desligar" in c and any(p in c for p in (" em ", " daqui ")):
        nums = _re.findall(r"(\d+)", c)
        if nums:
            return {"intent": "comando_sistema", "parametros": {"acao": f"desligar em {nums[0]} minutos"}}
        return {"intent": "comando_sistema", "parametros": {"acao": "desligar pc"}}
    return None


def _match_sistema_controle(c: str) -> dict | None:
    # Ordem import: checar primeiro os específicos
    acoes = [
        (["desligar pc", "desligar computador", "desligar o pc"], "desligar pc"),
        (["bloquear pc", "bloquear computador", "trancar pc", "tela"], "bloquear"),
        (["reiniciar"], "reiniciar"),
        (["aumentar volume", "aumentar som", "volume mais alto"], "aumentar volume"),
        (["diminuir volume", "diminuir som", "volume mais baixo", "abaixar"], "diminuir volume"),
        (["mutar", "silenciar", "sem som", "mudo"], "mutar"),
        (["print", "capturar tela", "tirar print", "screenshot", "foto da tela"], "print"),
        (["minimizar tudo", "mostrar area de trabalho", "mostrar área de trabalho", "limpar tela"], "minimizar tudo"),
        (["fechar janela", "fechar programa", "fechar"], "fechar janela"),
        (["pausar", "pausa", "parar musica", "play pause"], "pausar"),
        (["proxima musica", "proxima faixa", "pular musica", "avançar", "avancar", "próxima"], "proxima"),
        (["anterior", "voltar", "voltar faixa", "faixa anterior"], "anterior"),
        (["sair da conta", "encerrar sessao", "logoff", "logout", "sair do windows", "sair do pc", "deslogar"], "sair"),
        (["hibernar", "hibernar pc", "hibernar computador"], "hibernar"),
        (["suspender", "dormir"], "suspender"),
        (["desligar agora", "desliga agora", "desligar ja"], "desligar agora"),
        (["cancelar desligamento", "cancelar shutdown"], "cancelar desligamento"),
    ]

    # "reiniciar" precisa de contexto extra
    if "reiniciar" in c and any(p in c for p in ("pc", "computador", "maquina")):
        return {"intent": "comando_sistema", "parametros": {"acao": "reiniciar"}}

    for palavras, acao in acoes:
        if any(p in c for p in palavras):
            return {"intent": "comando_sistema", "parametros": {"acao": acao}}
    return None


def _match_conhecimento_listar(c: str) -> dict | None:
    if any(p in c for p in ("o que voce conhece", "liste os temas", "mostre o que sabe",
                             "liste conhecimento", "categorias",
                             "o que voce tem", "quais temas", "mostre temas")):
        return {"intent": "listar_conhecimento", "parametros": {}}
    return None


def _match_verificar_programa(c: str) -> dict | None:
    padroes = [
        r"(esta|tá|está)\s+(\w+)\s+(aberto|rodando|executando|ativo)",
        r"(\w+)\s+(esta|tá|está)\s+(aberto|rodando|executando|ativo)",
        r"verificar\s+(estado|status)\s+(de|do|da)\s+(\w+)",
        r"checar\s+(se\s+)?(\w+)\s+(esta|tá|está)",
    ]
    for padrao in padroes:
        m = _re.search(padrao, c)
        if m:
            grupos = [g for g in m.groups() if g and g not in ("esta", "tá", "está", "aberto", "rodando", "executando", "ativo", "de", "do", "da", "se", "verificar", "estado", "status")]
            if grupos:
                return {"intent": "verificar_programa", "parametros": {"programa": grupos[-1]}}
    return None


_HANDLERS_COMPLEXOS = [
    _match_shutdown_timer,
    _match_hora,
    _match_data,
    _match_sistema_controle,
    _match_cumprimento,
    _match_conhecimento_listar,
    _match_verificar_programa,
]


def detectar(comando: str, aprendidos: dict[str, dict] | None = None) -> dict | None:
    """Tenta detectar intencao do comando. Retorna dict ou None se nada encaixar."""
    c = _normalize(comando.lower().strip())

    # 1. Comandos aprendidos (memoria)
    if aprendidos and c in aprendidos:
        return dict(aprendidos[c])

    # 2. Regras YAML
    for rule in _carregar_regras():
        tipo = rule.get("type", "keyword")
        if tipo == "keyword":
            resultado = _match_keyword(c, rule)
        elif tipo == "extract":
            resultado = _match_keyword(c, rule)
        elif tipo == "prefix":
            resultado = _match_prefix(c, rule)
        else:
            continue
        if resultado:
            return resultado

    # 3. Handlers complexos (Python)
    for handler in _HANDLERS_COMPLEXOS:
        resultado = handler(c)
        if resultado:
            return resultado

    return None


def recarregar() -> None:
    global _CARREGADO
    _CARREGADO = None
    _carregar_regras()
