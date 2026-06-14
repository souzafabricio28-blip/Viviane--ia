import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSettings(unittest.TestCase):
    def setUp(self):
        self.env_backup = {}
        for k in ("AI_PROVIDER", "GROQ_API_KEY", "GEMINI_API_KEY",
                   "OLLAMA_MODEL", "OLLAMA_URL", "USER_NAME",
                   "ASSISTANT_NAME", "LANGUAGE"):
            self.env_backup[k] = os.environ.get(k)
            if k in os.environ:
                del os.environ[k]

    def tearDown(self):
        for k, v in self.env_backup.items():
            if v is not None:
                os.environ[k] = v
            elif k in os.environ:
                del os.environ[k]

    def test_defaults(self):
        from core.settings import Settings
        s = Settings()
        self.assertEqual(s.ai_provider, "groq")
        self.assertEqual(s.ollama_model, "llama3")
        self.assertEqual(s.user_name, "Fabricio")
        self.assertEqual(s.language, "pt-BR")
        self.assertEqual(s.assistant_name, "DarkSON")

    def test_env_override(self):
        os.environ["AI_PROVIDER"] = "ollama"
        os.environ["OLLAMA_MODEL"] = "llama3.1:8b"
        os.environ["USER_NAME"] = "Maria"
        os.environ["ASSISTANT_NAME"] = "Jarvis"
        os.environ["LANGUAGE"] = "en-US"
        from core.settings import Settings
        s = Settings()
        self.assertEqual(s.ai_provider, "ollama")
        self.assertEqual(s.ollama_model, "llama3.1:8b")
        self.assertEqual(s.user_name, "Maria")
        self.assertEqual(s.assistant_name, "Jarvis")
        self.assertEqual(s.language, "en-US")

    def test_validacao_provider_invalido(self):
        os.environ["AI_PROVIDER"] = "invalid_provider"
        from core.settings import Settings
        s = Settings()
        erros = s.validar()
        self.assertTrue(any("invalido" in e for e in erros))

    def test_validacao_provider_valido(self):
        for p in ("groq", "gemini", "ollama"):
            os.environ["AI_PROVIDER"] = p
            from core.settings import Settings
            s = Settings()
            erros = s.validar()
            invalidos = [e for e in erros if "invalido" in e]
            self.assertEqual(len(invalidos), 0, f"Provider {p} deu erro")

    def test_validacao_groq_sem_key(self):
        os.environ["AI_PROVIDER"] = "groq"
        if "GROQ_API_KEY" in os.environ:
            del os.environ["GROQ_API_KEY"]
        from core.settings import Settings
        s = Settings()
        erros = s.validar()
        self.assertTrue(any("GROQ_API_KEY" in e for e in erros))

    def test_validacao_gemini_sem_key(self):
        os.environ["AI_PROVIDER"] = "gemini"
        if "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]
        from core.settings import Settings
        s = Settings()
        erros = s.validar()
        self.assertTrue(any("GEMINI_API_KEY" in e for e in erros))

    def test_data_dir_criado(self):
        from core.settings import Settings
        s = Settings()
        self.assertTrue(s.data_dir.exists())

    def test_ollama_url_default(self):
        from core.settings import Settings
        s = Settings()
        self.assertEqual(s.ollama_url, "http://localhost:11434")


if __name__ == "__main__":
    unittest.main()
