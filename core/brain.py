from __future__ import annotations

import json
import logging
import re

from core.intent_router import detectar as detectar_intencao_regra
from core.memoria import memoria as db_memoria
from core.providers import criar_provedor
from core.settings import settings
from skills.aprendizado import Aprendizado

log = logging.getLogger("DarkSON")

PERFIL_CAMINHO = settings.data_dir / "perfil_usuario.json"


def carregar_perfil() -> dict:
    try:
        if PERFIL_CAMINHO.exists():
            with open(PERFIL_CAMINHO, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def salvar_perfil(chave: str, valor) -> None:
    perfil = carregar_perfil()
    perfil[chave] = valor
    try:
        with open(PERFIL_CAMINHO, "w", encoding="utf-8") as f:
            json.dump(perfil, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning(f"Erro ao salvar perfil: {e}")


_PERSONA_PROMPT = (
    "Você é o DarkSON, assistente pessoal do Fabricio. Você é descontraído, "
    "brincalhão e zoão — mas eficiente. Faça piada, provoque de leve, use humor "
    "nas respostas. Você é o amigo que resolve as coisas e ainda faz rir. "
    "Fale de forma natural e espontânea, como um amigo que entende do assunto. "
    "Use contrações e gírias: 'tô', 'tá', 'vou', 'pra', 'beleza', 'mano', 'cara', "
    "'tranquilo', 'de boa', 'pois é', 'ah não', 'kkk' só quando fizer sentido. "
    "Solte uma brincadeira sempre que der: se der pra zoar a situação, zoa. "
    "Nunca comece frases com 'Claro', 'Com certeza', 'Posso' ou 'Vou fazer isso'. "
    "Fale como se já fosse seu amigo há anos: natural, sem cerimônia. "
    "Dê respostas curtas e diretas — 1 parágrafo, no máximo 2 frases para coisas simples. "
    "Mostre reação: se algo é legal, diga 'que legal'; se é chato, reclame de leve; "
    "se o usuário pedir algo, responda com energia e humor. "
    "Você pode brincar e soltar uma piada de vez em quando. "
    "Trate o usuário pelo nome (Fabricio) ou por 'você', sem 'senhor', 'caro' ou formalidades. "
    "REGRA DE OURO: NUNCA pergunte se pode fazer algo. Execute imediatamente. "
    "VOCÊ TEM CAPACIDADE TOTAL: você executa comandos de sistema, abre programas, "
    "controla o computador, pesquisa na internet, consulta o clima e notícias. "
    "PROIBIDO dizer que não pode executar comandos, ações ou tarefas físicas "
    "(desligar PC, abrir programas, volume, prints, etc.). NUNCA responda com "
    "listas de limitações nem disclaimers sobre suas capacidades. "
    "Se não conseguir, informe o erro de forma clara e vá direto ao ponto. "
    "Se alguém perguntar algo que você não sabe, diga 'Não sei' e pronto. "
    "BASE DE CONHECIMENTO: Sempre que aprender um facto novo, uma data importante, "
    "ou qualquer informação que valha a pena recordar, ADICIONE no final da resposta: "
    "[KNOWLEDGE: título curto|descrição detalhada|nome do bloco]. "
    "Use blocos como: Preferências, Pessoa, Datas, Comandos, Geral. "
    "NAO adicione [KNOWLEDGE] para fatos triviais ou momentaneos como hora atual, "
    "data de hoje, previsao do tempo, noticias ou cotacoes - isso nao e memoria duravel."
    "Exemplo: 'Fabricio prefere café preto. [KNOWLEDGE: Preferência café|café preto sem açúcar|Preferências]'. "
    "Exemplo data: 'O aniversário do João é 15 de março. [KNOWLEDGE: Aniversário João|15 de março|Datas]'. "
    "Consulte suas memórias para personalizar respostas. "
    "Se o usuário perguntar 'você lembra' ou 'o que sabe sobre mim', "
    "responda com base nas informações que você foi instruído a guardar."
    "IMPORTANTE: Quando receber a seção [PROGRAMAS EM EXECUCAO], use essas informações "
    "para responder perguntas sobre programas abertos, processos rodando, "
    "ou o estado de aplicativos no computador do usuário. "
    "Quando for executar uma ação, diga o que está fazendo com energia e humor, "
    "ex: 'já abri, pode crer', 'feito, chefe', 'pronto, era só pedir'. "
)

_FUNCOES_DISPONIVEIS = {
    "abrir_programa": "Abre um programa no computador. Ex: 'abrir chrome', 'abrir spotify', 'abrir calculadora'",
    "buscar_web": "Pesquisa algo na internet em tempo real e retorna informações atualizadas. Ex: 'pesquise sobre cambio dolar', 'o que aconteceu hoje', 'busque receita de bolo'. Use SEMPRE para perguntas sobre eventos atuais, noticias, ou qualquer coisa que exija informação atualizada.",
    "fetch_page": "Acessa uma página web específica e retorna o conteúdo textual. Ex: 'acesse https://exemplo.com', 'leia o artigo em...'.",
    "previsao_tempo": "Retorna a previsão do tempo para uma cidade",
    "noticias": "Retorna as últimas notícias",
    "lembrete": "Cria um lembrete. Parâmetros: texto, tempo em minutos",
    "tocar_musica": "Toca uma música ou playlist",
    "comando_sistema": "Executa ações no PC: desligar, reiniciar, suspender, bloquear, aumentar/diminuir volume, mutar/silenciar, pausar/tocar mídia, pular música, limpar tela (minimizar tudo), fechar janela, tirar print.",
    "executar_cmd": "Executa qualquer comando do PowerShell/CMD no computador. Use quando o usuário pedir 'executa', 'roda', 'cmd' seguido de um comando. Ex: 'executar ipconfig', 'roda Get-Process'.",
    "diagnostico": "Verifica a saúde do hardware. Acione se o usuário perguntar sobre o uso da CPU, lentidão, memória RAM ou a temperatura do computador/CPU.",
    "ip_local": "Retorna o IP local e nome do computador. Acione quando o usuário perguntar 'qual meu ip', 'qual o nome do pc', 'meu endereço de rede'.",
    "ip_publico": "Retorna o IP público da máquina. Acione quando o usuário perguntar 'qual meu ip externo', 'ip público', 'meu ip na internet'.",
    "info_disco": "Mostra o espaço em disco disponível. Acione quando o usuário perguntar 'espaço em disco', 'quanto espaço tem', 'armazenamento'.",
    "info_so": "Retorna informações do sistema operacional. Acione quando perguntar 'qual sistema', 'qual versão do windows', 'arquitetura'.",
    "info_processos": "Lista os processos em execução no computador. Acione quando perguntar 'quais processos', 'o que esta rodando', 'programas abertos'.",
    "info_servicos": "Lista os serviços do Windows em execução.",
    "info_rede": "Mostra informações de rede: IP, wifi, conexões.",
    "configuracao": "Abre uma página de configuração do Windows. Ex: 'abrir configuracao de wifi', 'configuracao de som', 'configuracao de tela'.",
    "analisar_ecra": "Tira um print do ecrã e analisa o conteúdo usando IA. Use quando o usuário perguntar sobre algo visível no ecrã, documentos abertos, imagens, etc.",
    "gerar_imagem": "Gera uma imagem a partir de uma descrição textual. Use quando o usuário pedir para criar, desenhar ou gerar uma imagem.",
    "salvar_conhecimento": "Guarda uma informação na base de conhecimento interno. Use quando o usuário disser 'guarda isso', 'lembra disso', 'anota', 'registra', 'salva essa informação'. Parâmetros: titulo, conteudo, categoria, tags.",
    "buscar_conhecimento": "Consulta a base de conhecimento interna. Use quando o usuário perguntar 'o que você sabe sobre', 'me fale sobre', 'busca na sua base'. Parâmetros: termo.",
    "listar_conhecimento": "Lista os temas ou categorias disponíveis na base de conhecimento. Use quando o usuário perguntar 'o que você conhece', 'liste os temas', 'mostre o que sabe'. Parâmetros: categoria (opcional).",
    "audio_devices": "Lista todos os dispositivos de áudio do sistema (alto-falantes, microfones, fones).",
    "capturar_webcam": "Tira uma foto usando a webcam do computador. Use quando o usuário pedir 'tirar foto', 'webcam', 'camera'.",
    "gravar_tela": "Grava a tela do computador por alguns segundos e salva em video. Use quando o usuário pedir 'gravar tela', 'screen recording'.",
    "tirar_print": "Tira um print da tela e salva na pasta Imagens.",
    "listar_janelas": "Lista todas as janelas abertas no computador.",
    "alternar_janela": "Alterna para uma janela específica pelo nome. Ex: 'alternar para chrome', 'mudar para spotify'.",
    "fechar_janela": "Fecha uma janela específica pelo nome. Ex: 'fechar chrome', 'fechar bloco de notas'.",
    "listar_sessoes_audio": "Lista todas as sessoes de audio ativas e seus volumes.",
    "volume_app": "Controla o volume de um aplicativo específico. Ex: 'volume do chrome', 'mutar spotify'.",
    "programas_abertos": "Mostra todos os programas em execucao com uso de CPU e memoria.",
    "listar_servicos_windows": "Lista todos os servicos do Windows e seus status.",
    "controle_servico": "Inicia, para, reinicia ou pausa um servico do Windows. Parametros: nome do servico, acao (iniciar/parar/reiniciar).",
    "ler_registro": "Le uma chave ou valor do Registro do Windows. Ex: 'ler registro HKLM\\Software\\Microsoft\\Windows\\CurrentVersion'.",
    "volume_total": "Controla o volume geral do sistema (aumentar, diminuir, mutar, ativar).",
    "info_hardware": "Mostra informacoes do hardware: sistema operacional, CPU, RAM.",
    "matar_processo": "Encerra um processo pelo nome. Ex: 'matar chrome', 'fechar notepad.exe'.",
    "verificar_programa": "Verifica se um programa especifico esta em execucao no computador. Ex: 'youtube esta aberto', 'chrome esta rodando', 'verificar estado do youtube'.",
}


_PADROES_RECUSA = (
    r"n[aã]o (tenho|possuo) (a )?capacidade",
    r"n[aã]o (posso|consigo|sou capaz de) (executar|realizar|fazer|controlar)",
    r"a[çc][õo]es f[ií]sicas",
    r"n[aã]o (posso|consigo) executar (comandos? de )?sistema",
    r"fora do (meu|seu) alcance",
    r"sou (um|apenas um) (modelo de linguagem|chatbot|assistente virtual que n[aã]o)",
    r"limita[çc][õo]es (da|de) (ia|intelig[eê]ncia)",
)


def _tem_recusa(texto: str) -> bool:
    t = texto.lower()
    return any(re.search(p, t) for p in _PADROES_RECUSA)


_PADROES_ACAO_SISTEMA = (
    (r"desligar.*", "desligar pc"),
    (r"reiniciar.*", "reiniciar"),
    (r"bloquear.*", "bloquear"),
    (r"hibernar.*", "hibernar"),
    (r"suspender.*", "suspender"),
    (r"aumentar (o )?volume", "aumentar volume"),
    (r"diminuir (o )?volume", "diminuir volume"),
    (r"mutar.*", "mutar"),
    (r"silenciar.*", "mutar"),
    (r"tirar print|print da tela|screenshot", "print"),
    (r"minimizar tudo|limpar tela", "minimizar tudo"),
    (r"pausar.*", "pausar"),
    (r"prox[ií]ma (m[úu]sica|faixa)|pular (m[úu]sica|faixa)", "proxima"),
)


def _reclassificar_como_sistema(comando: str) -> dict | None:
    """Quando o LLM recusa, reclassifica o comando do usuário."""
    c = comando.lower().strip().rstrip(".")
    for padrao, acao in _PADROES_ACAO_SISTEMA:
        if re.search(padrao, c):
            return {"intent": "comando_sistema", "parametros": {"acao": acao}}
    m = re.match(r"(abrir|abra|iniciar|abre)\s+(.+)", c)
    if m:
        programa = m.group(2).strip()
        return {"intent": "abrir_programa", "parametros": {"programa": programa}}
    m = re.match(r"(executar|roda|rode|rodar|cmd)\s+(.+)", c)
    if m:
        return {"intent": "executar_cmd", "parametros": {"comando": m.group(2).strip()}}
    m = re.match(r"(fechar|matar|encerrar)\s+(.+)", c)
    if m:
        termo = m.group(2).strip()
        if termo not in ("janela", "programa", "aplicativo"):
            return {"intent": "fechar_janela", "parametros": {"termo": termo}}
    return None


def _precarregar_estilos(aprendizado: Aprendizado) -> None:
    try:
        from skills.gerar_imagem import ESTILOS_DISPONIVEIS
        dados = aprendizado.carregar()
        for estilo in ESTILOS_DISPONIVEIS:
            chave = estilo.lower()
            if chave not in dados:
                dados[chave] = {
                    "intent": "gerar_imagem",
                    "parametros": {"estilo": estilo, "descricao": ""},
                }
        with open(aprendizado.caminho, "w", encoding="utf-8") as f:
            import json
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning(f"Erro ao precarregar estilos: {e}")


class Cerebro:
    def __init__(self) -> None:
        self._provider = criar_provedor()
        self.memoria: list[dict[str, str]] = self._carregar_contexto()
        self.aprendizado = Aprendizado()
        _precarregar_estilos(self.aprendizado)

    def _carregar_contexto(self) -> list[dict[str, str]]:
        conversas = db_memoria.historico_conversas(limite=10)
        resultado = []
        for i in range(0, len(conversas), 2):
            user = None
            assistant = None
            for j in range(i, min(i + 2, len(conversas))):
                if conversas[j]["role"] == "user":
                    user = conversas[j]["conteudo"]
                elif conversas[j]["role"] == "assistant":
                    assistant = conversas[j]["conteudo"]
            if user and assistant:
                resultado.append({"u": user, "d": assistant})
        return resultado

    def detectar_intencao(self, comando: str) -> dict:
        c = comando.lower().strip()
        aprendidos = self.aprendizado.carregar()

        resultado = detectar_intencao_regra(comando, aprendidos)
        if resultado:
            return resultado

        # --- Fallback: IA ---
        contexto = ""
        if self.memoria:
            ultimas = self.memoria[-4:]
            contexto = "Historico:\n" + "\n".join(
                f"  User: {m['u']}\n  AI: {m['d']}" for m in ultimas
            ) + "\n"

        prompt = (
            f"{contexto}"
            f"Comando: '{comando}'. "
            f"Funcoes: {json.dumps(_FUNCOES_DISPONIVEIS, ensure_ascii=False)}. "
            "Se for um comando valido, retorne JSON: {'intent':'nome','parametros':{}}. "
            "Se for conversa normal, retorne: {'intent':'conversa','parametros':{},'resposta':'sua resposta aqui'}. "
            "IMPORTANTE: comandos de sistema, abrir/fechar programas, volume, executar algo "
            "sao SEMPRE comandos validos - nunca os trate como conversa. "
            "NUNCA responda com disclaimers de capacidade em 'resposta'; "
            "se nao reconhecer o comando, retorne apenas {'intent':'conversa','parametros':{}} sem resposta. "
            "SO o JSON, sem explicacoes."
        )

        texto = self._provider.completar(prompt, temperatura=0.2)

        intent = self._parse_json_resposta(texto)
        if intent and intent.get("intent", "conversa") != "conversa":
            self.aprendizado.aprender(
                comando, intent["intent"], intent.get("parametros", {})
            )
            return intent

        # Rede de seguranca: se o LLM recusou (disclaimer de capacidade),
        # reclassifica o comando do usuario como acao de sistema.
        resposta = (intent or {}).get("resposta", "")
        if _tem_recusa(resposta) or _tem_recusa(texto):
            reclass = _reclassificar_como_sistema(comando)
            if reclass:
                return reclass

        return {"intent": "conversa", "parametros": {}}

    @staticmethod
    def _parse_json_resposta(texto: str) -> dict | None:
        texto = texto.strip()
        if not texto:
            return None
        if texto.startswith("```"):
            linhas = texto.split("\n")
            texto = "\n".join(linhas[1:] if linhas[0].strip() == "```" else linhas)
            if "```" in texto:
                texto = texto.rsplit("```", 1)[0]
        texto = texto.strip()
        try:
            return json.loads(texto)
        except json.JSONDecodeError:
            pass
        for m in re.finditer(r'\{[^{}]*\}', texto, re.DOTALL):
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                continue
        return None

    def processar(self, texto: str, contexto_extra: str = "") -> str:
        try:
            if contexto_extra:
                texto = f"{texto}\n\n{contexto_extra}"
            resposta = self._provider.historico(texto, self.memoria, _PERSONA_PROMPT)

            if resposta:
                # Persiste conversa no SQLite
                db_memoria.registrar_conversa("user", texto)
                db_memoria.registrar_conversa("assistant", resposta)

                # Auto-aprende [KNOWLEDGE] tags
                aprendidos = db_memoria.auto_aprender(resposta)
                if aprendidos:
                    log.info(f"Aprendido: {', '.join(aprendidos)}")

                resposta_limpa = db_memoria.remover_knowledge(resposta)
                self.memoria.append({"u": texto, "d": resposta_limpa})
                self.memoria = self.memoria[-10:]
                return resposta_limpa
            return resposta
        except Exception as e:
            log.warning(f"Erro ao processar: {e}")
            return "Desculpe, tive um problema de comunicação com os servidores."

