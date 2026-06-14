import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.memoria import Memoria


class TestMemoria(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = Path(self.tmp) / "test.db"
        import core.memoria as mod
        mod.settings.data_dir = Path(self.tmp)
        self.m = Memoria()
        self.m.arquivo = self.db_path
        self.m._inicializar()

    def test_conversa_cycle(self):
        mid = self.m.registrar_conversa("user", "ola")
        self.assertIsInstance(mid, int)
        hist = self.m.historico_conversas()
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["role"], "user")
        self.assertEqual(hist[0]["conteudo"], "ola")

    def test_conversa_com_metadata(self):
        mid = self.m.registrar_conversa("assistant", "teste", {"fonte": "groq"})
        hist = self.m.historico_conversas()
        self.assertEqual(hist[0]["role"], "assistant")

    def test_memoria_save_and_search(self):
        mid = self.m.salvar_memoria("Teste", "Conteudo de teste", "facto", "teste", 2)
        self.assertIsInstance(mid, int)
        resultados = self.m.buscar_memorias("teste")
        self.assertGreaterEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["titulo"], "Teste")

    def test_memoria_varios_tipos(self):
        self.m.salvar_memoria("Pref", "Gosta de cafe", "preferencia", "cafe", 3)
        self.m.salvar_memoria("Pessoa", "Joao amigo", "pessoa", "amigos", 2)
        facts = self.m.listar_memorias("preferencia")
        self.assertGreaterEqual(len(facts), 1)
        pessoas = self.m.listar_memorias("pessoa")
        self.assertGreaterEqual(len(pessoas), 1)

    def test_memoria_remover(self):
        mid = self.m.salvar_memoria("Temp", "Temporario", "facto")
        self.assertTrue(self.m.remover_memoria(mid))
        resultados = self.m.buscar_memorias("Temporario")
        self.assertEqual(len(resultados), 0)

    def test_perfil(self):
        self.m.definir_perfil("nome", "Joao")
        self.assertEqual(self.m.obter_perfil("nome"), "Joao")
        perfil = self.m.listar_perfil()
        self.assertIn("nome", perfil)

    def test_perfil_json(self):
        dados = {"idade": 30, "cidade": "SP"}
        self.m.definir_perfil("dados", dados, "json")
        self.assertEqual(self.m.obter_perfil("dados"), dados)

    def test_perfil_remover(self):
        self.m.definir_perfil("temp", "valor")
        self.assertTrue(self.m.remover_perfil("temp"))
        self.assertIsNone(self.m.obter_perfil("temp"))

    def test_padroes(self):
        self.m.registrar_padrao("abrir chrome", "abrir_programa", True)
        freq = self.m.comandos_frequentes()
        self.assertGreaterEqual(len(freq), 1)
        self.assertEqual(freq[0]["comando"], "abrir chrome")

    def test_comandos_executados(self):
        self.m.registrar_comando("powershell", "Get-Process", "saida", "detalhes", True)
        cmds = self.m.ultimos_comandos()
        self.assertGreaterEqual(len(cmds), 1)
        self.assertEqual(cmds[0]["tipo"], "powershell")

    def test_db_tamanho(self):
        mb = self.m.db_tamanho_mb()
        self.assertIsInstance(mb, float)
        self.assertGreaterEqual(mb, 0)

    def test_db_contagem(self):
        c = self.m.db_contagem()
        self.assertIn("conversas", c)
        self.assertIn("memorias", c)
        self.assertIn("comandos", c)

    def test_extrair_knowledge(self):
        texto = "Joao prefere cafe. [KNOWLEDGE: Pref Cafe|cafe preto|Preferencias]"
        result = Memoria.extrair_knowledge(texto)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["titulo"], "Pref Cafe")

    def test_extrair_knowledge_multiplo(self):
        texto = "[KNOWLEDGE: A|desc A|Bloco] e [KNOWLEDGE: B|desc B|Bloco]"
        result = Memoria.extrair_knowledge(texto)
        self.assertEqual(len(result), 2)

    def test_remover_knowledge(self):
        texto = "Info. [KNOWLEDGE: T|C|B]"
        limpo = Memoria.remover_knowledge(texto)
        self.assertEqual(limpo, "Info.")

    def test_contexto_para_ia(self):
        self.m.registrar_conversa("user", "ola")
        ctx = self.m.contexto_para_ia(limite_conversas=5, limite_memorias=0)
        self.assertIn("ola", ctx)


if __name__ == "__main__":
    unittest.main()
