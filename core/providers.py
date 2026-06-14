from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

import requests

from core.settings import settings

log = logging.getLogger("DarkSON")

_MEMORIAS_CACHE: str | None = None


def _memorias_msg() -> str:
    global _MEMORIAS_CACHE
    from core.memoria import memoria as db_memoria
    ctx = db_memoria.contexto_para_ia(limite_conversas=0, limite_memorias=15)
    result = "[MEMORIAS]\n" + ctx if ctx.strip() else ""
    return result


class AIProvider(ABC):
    @abstractmethod
    def completar(self, prompt: str, temperatura: float = 0.3) -> str: ...

    @abstractmethod
    def historico(
        self, texto: str, memoria: list[dict[str, str]], persona: str
    ) -> str: ...


class GroqProvider(AIProvider):
    def __init__(self) -> None:
        from groq import Groq
        self._cliente = Groq(api_key=settings.groq_api_key)
        self._modelo = "llama-3.3-70b-versatile"

    def completar(self, prompt: str, temperatura: float = 0.3) -> str:
        try:
            resposta = self._cliente.chat.completions.create(
                model=self._modelo,
                messages=[
                    {"role": "system", "content": "Você é um classificador de intenções. Responda APENAS com JSON puro, sem formatação, sem markdown, sem explicações."},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperatura,
                max_tokens=300,
            )
            return resposta.choices[0].message.content or ""
        except Exception as e:
            log.warning("Groq API error: %s", e)
            return '{"intent": "conversa", "parametros": {}}'

    def historico(
        self, texto: str, memoria: list[dict[str, str]], persona: str
    ) -> str:
        messages = [{"role": "system", "content": persona}]
        for item in memoria:
            messages.append({"role": "user", "content": item["u"]})
            messages.append({"role": "assistant", "content": item["d"]})
        mem = _memorias_msg()
        if mem:
            messages.append({"role": "system", "content": mem})
        messages.append({"role": "user", "content": texto})
        resposta = self._cliente.chat.completions.create(
            model=self._modelo,
            messages=messages,
            temperature=0.7,
            max_tokens=256,
        )
        return resposta.choices[0].message.content or ""


class GeminiProvider(AIProvider):
    def __init__(self) -> None:
        from google import genai
        from google.genai import types
        self._cliente = genai.Client(api_key=settings.gemini_api_key)
        self._modelo = "gemini-2.0-flash"
        self._types = types

    def completar(self, prompt: str, temperatura: float = 0.7) -> str:
        try:
            resposta = self._cliente.models.generate_content(
                model=self._modelo,
                contents=prompt,
                config=self._types.GenerateContentConfig(
                    temperature=temperatura,
                    max_output_tokens=256,
                    response_mime_type="application/json",
                ),
            )
            return resposta.text or ""
        except Exception as e:
            log.warning("Gemini API error: %s", e)
            return '{"intent": "conversa", "parametros": {}}'

    def historico(
        self, texto: str, memoria: list[dict[str, str]], persona: str
    ) -> str:
        contents: list[Any] = []
        for item in memoria:
            contents.append(
                self._types.Content(role="user", parts=[self._types.Part.from_text(text=item["u"])])
            )
            contents.append(
                self._types.Content(role="model", parts=[self._types.Part.from_text(text=item["d"])])
            )
        mem = _memorias_msg()
        if mem:
            contents.append(
                self._types.Content(role="user", parts=[self._types.Part.from_text(text=mem)])
            )
        contents.append(
            self._types.Content(role="user", parts=[self._types.Part.from_text(text=texto)])
        )
        resposta = self._cliente.models.generate_content(
            model=self._modelo,
            contents=contents,
            config=self._types.GenerateContentConfig(
                system_instruction=persona,
                temperature=0.7,
                max_output_tokens=512,
            ),
        )
        return resposta.text or ""


class OllamaProvider(AIProvider):
    def __init__(self) -> None:
        self._url = settings.ollama_url
        self._modelo = settings.ollama_model

    def completar(self, prompt: str, temperatura: float = 0.7) -> str:
        try:
            resp = requests.post(
                f"{self._url}/api/chat",
                json={
                    "model": self._modelo,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": temperatura, "num_predict": 256},
                    "format": "json",
                },
                timeout=30,
            )
            data = resp.json()
            return data.get("message", {}).get("content", "") or ""
        except requests.ConnectionError:
            return '{"intent": "conversa", "parametros": {}, "resposta": "Erro de conexão com Ollama."}'
        except Exception as e:
            return f'{{"intent": "conversa", "parametros": {{}}, "resposta": "Erro no Ollama: {str(e)[:50]}"}}'

    def historico(
        self, texto: str, memoria: list[dict[str, str]], persona: str
    ) -> str:
        messages = [{"role": "system", "content": persona}]
        for item in memoria:
            messages.append({"role": "user", "content": item["u"]})
            messages.append({"role": "assistant", "content": item["d"]})
        mem = _memorias_msg()
        if mem:
            messages.append({"role": "system", "content": mem})
        messages.append({"role": "user", "content": texto})
        try:
            resp = requests.post(
                f"{self._url}/api/chat",
                json={
                    "model": self._modelo,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.7, "num_predict": 512},
                },
                timeout=60,
            )
            data = resp.json()
            return data.get("message", {}).get("content", "") or ""
        except requests.ConnectionError:
            return "Erro: Não foi possível conectar ao Ollama. Certifique-se de que o servidor está a correr em " + self._url
        except Exception as e:
            return f"Erro no Ollama: {str(e)[:100]}"


_PROVIDERS: dict[str, type[AIProvider]] = {
    "groq": GroqProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
}


def criar_provedor(provider: str | None = None) -> AIProvider:
    nome = (provider or settings.ai_provider).lower()
    classe = _PROVIDERS.get(nome)
    if not classe:
        log.warning(f"Provider desconhecido '{nome}', usando GroqProvider")
        return GroqProvider()
    return classe()
