from __future__ import annotations

import time
from datetime import datetime, timedelta
from urllib.parse import quote

import requests

from core.conversa import registrar
from core.settings import settings
from core.voice import falar

_CACHE: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 300


class PrevisaoTempo:
    def __init__(self) -> None:
        self.api_key = settings.weather_api_key
        self._sessao = requests.Session()

    def obter_previsao(self, cidade: str = "São Paulo") -> str:
        if not self.api_key:
            msg = "Previsão do tempo não disponível. Configure WEATHER_API_KEY no .env"
            falar(msg)
            return msg

        cidade_normalizada = cidade.strip().title()
        agora = time.time()

        if cidade_normalizada in _CACHE:
            texto, timestamp = _CACHE[cidade_normalizada]
            if agora - timestamp < _CACHE_TTL:
                falar(texto)
                return texto

        try:
            falar(f"A verificar o clima em {cidade_normalizada}...")

            cidade_encoded = quote(cidade_normalizada)
            url = (
                "https://api.openweathermap.org/data/2.5/weather"
                f"?q={cidade_encoded}&appid={self.api_key}&lang=pt_br&units=metric"
            )

            resp = self._sessao.get(url, timeout=4)
            dados = resp.json()

            if resp.status_code == 404:
                msg = f"Não encontrei a cidade {cidade_normalizada}"
                falar(msg)
                return msg
            if resp.status_code == 401:
                msg = "Chave da API do clima inválida"
                falar(msg)
                return msg
            if resp.status_code != 200:
                msg = f"Erro ao obter clima: {dados.get('message', 'erro desconhecido')}"
                falar(msg)
                return msg

            temp = dados["main"]["temp"]
            sensacao = dados["main"]["feels_like"]
            desc = dados["weather"][0]["description"]
            umidade = dados["main"]["humidity"]
            vento = dados["wind"]["speed"]

            texto = (
                f"Em {cidade_normalizada}, temperatura de {temp:.0f} graus, "
                f"sensacão térmica de {sensacao:.0f}. "
                f"{desc.capitalize()}. "
                f"Umidade {umidade}%, vento {vento:.1f} m/s."
            )

            _CACHE[cidade_normalizada] = (texto, time.time())
            registrar("assistente", f"[Clima] {texto}")
            falar(texto)
            return texto

        except requests.ConnectionError:
            msg = "Sem conexão com a internet para obter a previsão do tempo"
            falar(msg)
            return msg
        except requests.Timeout:
            msg = "O serviço do clima demorou muito para responder"
            falar(msg)
            return msg
        except requests.RequestException as exc:
            msg = f"Erro ao obter previsão do tempo: {str(exc)[:60]}"
            falar(msg)
            return msg
