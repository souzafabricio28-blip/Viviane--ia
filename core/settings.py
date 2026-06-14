from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from dotenv import load_dotenv
from os import environ

_DOTENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(_DOTENV_PATH)

_CONFIG_KEYS = {
    "groq": ("GROQ_API_KEY",),
    "gemini": ("GEMINI_API_KEY",),
    "ollama": (),
}

_REQUIRED_KEYS = {
    "groq": ("GROQ_API_KEY",),
    "gemini": ("GEMINI_API_KEY",),
}

_PLACEHOLDER_PATTERNS = [
    r"^sk-[a-zA-Z0-9]{5,8}$",
    r"^gsk_[a-zA-Z0-9]{5,8}$",
    r"^r8_[a-zA-Z0-9]{5,10}$",
    r"^AQ\.[a-zA-Z0-9]{5,10}$",
    r"^sua[_-]",
    r"^your[_-]",
    r"^<.*>$",
]

_ENV_KEY_NAMES = [
    "GROQ_API_KEY", "GEMINI_API_KEY", "REPLICATE_API_KEY",
    "WEATHER_API_KEY", "NEWS_API_KEY", "DARKSON_API_TOKEN",
]

_VOZ_MASCULINA_PADRAO = "pt-BR-AntonioNeural"
_VOZES_FEMININAS = (
    "pt-BR-FranciscaNeural",
    "pt-BR-ThalitaNeural",
    "Microsoft Maria Desktop",
    "Microsoft Zira Desktop",
)


@dataclass
class Settings:
    BASE_DIR: ClassVar[Path] = Path(__file__).parent.parent

    ai_provider: str = field(
        default_factory=lambda: environ.get("AI_PROVIDER", "groq")
    )
    groq_api_key: str = field(
        default_factory=lambda: environ.get("GROQ_API_KEY", "")
    )
    gemini_api_key: str = field(
        default_factory=lambda: environ.get("GEMINI_API_KEY", "")
    )
    language: str = field(default_factory=lambda: environ.get("LANGUAGE", "pt-BR"))
    assistant_name: str = field(
        default_factory=lambda: environ.get("ASSISTANT_NAME", "DarkSON")
    )
    user_name: str = field(
        default_factory=lambda: environ.get("USER_NAME", "Fabricio")
    )
    weather_api_key: str = field(
        default_factory=lambda: environ.get("WEATHER_API_KEY", "")
    )
    news_api_key: str = field(
        default_factory=lambda: environ.get("NEWS_API_KEY", "")
    )
    replicate_api_key: str = field(
        default_factory=lambda: environ.get("REPLICATE_API_KEY", "")
    )
    ollama_model: str = field(
        default_factory=lambda: environ.get("OLLAMA_MODEL", "llama3")
    )
    ollama_url: str = field(
        default_factory=lambda: environ.get("OLLAMA_URL", "http://localhost:11434")
    )
    tts_voice: str = field(
        default_factory=lambda: environ.get("TTS_VOICE", "pt-BR-AntonioNeural")
    )
    tts_engine: str = field(
        default_factory=lambda: environ.get("TTS_ENGINE", "edge")
    )
    api_host: str = field(
        default_factory=lambda: environ.get("DARKSON_HOST", "127.0.0.1")
    )
    api_port: int = field(
        default_factory=lambda: int(environ.get("DARKSON_PORT", "5000"))
    )
    api_token: str = field(
        default_factory=lambda: environ.get("DARKSON_API_TOKEN", "")
    )
    data_dir: Path = field(default_factory=lambda: Settings.BASE_DIR / "data")

    def __post_init__(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if (
            self.tts_voice in _VOZES_FEMININAS
            or "Francisca" in self.tts_voice
            or "Maria" in self.tts_voice
            or "Zira" in self.tts_voice
        ):
            self.tts_voice = _VOZ_MASCULINA_PADRAO
        if self.tts_engine not in ("edge", "sapi"):
            self.tts_engine = "edge"
        erros = self.validar()
        if erros:
            for e in erros:
                print(f"[CONFIG] {e}", file=sys.stderr)
        seguranca = self.auditar_seguranca()
        if seguranca:
            for s in seguranca:
                print(f"[SEGURANCA] {s}", file=sys.stderr)

    def auditar_seguranca(self) -> list[str]:
        avisos = []
        if not _DOTENV_PATH.exists():
            return avisos
        try:
            with open(_DOTENV_PATH, encoding="utf-8") as f:
                conteudo = f.read()
        except Exception:
            return avisos
        for nome_chave in _ENV_KEY_NAMES:
            valor = getattr(self, nome_chave.lower(), "")
            if not valor:
                continue
            resp = re.match(rf"^{nome_chave}=(.+)$", conteudo, re.MULTILINE)
            if not resp:
                continue
            if any(re.match(p, valor) for p in _PLACEHOLDER_PATTERNS):
                continue
        return avisos

    def validar(self) -> list[str]:
        erros = []
        if self.ai_provider not in ("groq", "gemini", "ollama"):
            erros.append(f"AI_PROVIDER invalido: '{self.ai_provider}'. Use groq, gemini ou ollama.")
        required = _REQUIRED_KEYS.get(self.ai_provider, ())
        for k in required:
            if not getattr(self, k.lower(), ""):
                erros.append(f"{k} nao configurada no .env (necessario para provider '{self.ai_provider}')")
        return erros


settings = Settings()
