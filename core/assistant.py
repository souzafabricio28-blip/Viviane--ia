from __future__ import annotations

import json
import logging
import re
import threading
import time
from datetime import datetime
from typing import Any

import psutil

from core.brain import Cerebro
from core.conhecimento import BaseConhecimento
from core.conversa import registrar
from core.memoria import memoria as db_memoria
from core.settings import settings
from core.voice import GravadorVoz, falar
from skills.lembretes import GerenciadorLembretes
from skills.pc_control import ControladorPC
from skills.clima import PrevisaoTempo
from skills.noticias import Noticias
from skills.diagnostico import DiagnosticoSistema
from skills.sistema import InfoSistema
from skills.visao import analisar_ecra
from skills.gerar_imagem import ESTILOS_DISPONIVEIS, gerar_imagem
from skills.web_search import buscar_web, fetch_page
from skills.midia import listar_audio_devices, capturar_webcam, gravar_tela

log = logging.getLogger("DarkSON")


def _desligar_tudo() -> None:
    import os
    os._exit(0)


def _abrir_lista_estilos() -> None:
    import subprocess, tempfile, os
    linhas = "".join(
        f'    <li><strong>{e}</strong></li>\n' for e in ESTILOS_DISPONIVEIS
    )
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><title>Estilos DarkSON</title>
<style>
  body {{ font: 16px/1.6 Arial; background: #111; color: #eee; max-width: 500px; margin: 40px auto; padding: 20px; }}
  h1 {{ color: #0ff; }}
  li {{ padding: 4px 0; }}
</style></head>
<body><h1>Estilos de Imagem</h1><ul>{linhas}</ul></body></html>"""
    path = os.path.join(tempfile.gettempdir(), "darkson_estilos.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    os.startfile(path)


class Assistente:
    def __init__(self, *, modo_web: bool = False) -> None:
        self.modo_web = modo_web
        self.cerebro = Cerebro()
        self.voz = GravadorVoz()
        self.pc = ControladorPC()
        self.lembretes = GerenciadorLembretes()
        self.clima = PrevisaoTempo()
        self.noticias = Noticias()
        self.diagnostico = DiagnosticoSistema()
        self.info_sistema = InfoSistema()
        self.conhecimento = BaseConhecimento()
        self.ativo = True
        self._ultima_fala = 0.0
        self.thread_lembretes = threading.Thread(
            target=self._verificar_lembretes, daemon=True
        )
        self.thread_monitorizacao = threading.Thread(
            target=self._monitorizar_sistema, daemon=True
        )
        self.thread_varredura = threading.Thread(
            target=self._varredura_programas, daemon=True
        )
        self._ultima_varredura: list[dict] = []

    def iniciar(self) -> None:
        falar(f"Pronto.")
        self.thread_lembretes.start()
        self.thread_monitorizacao.start()
        self.thread_varredura.start()
        self._loop_principal()

    def _loop_principal(self) -> None:
        print("\nDarkSON aguardando comandos...")
        while self.ativo:
            try:
                comando = self.voz.ouvir_comando()
                if comando:
                    self._executar_comando(comando)
                time.sleep(0.3)
            except KeyboardInterrupt:
                self.parar()
            except Exception as exc:
                log.warning(f"Erro no loop: {exc}")

    def executar_comando(self, comando: str, *, falar_resposta: bool | None = None) -> str:
        if falar_resposta is None:
            falar_resposta = not self.modo_web
        log.debug("executar_comando: %r falar=%s", comando, falar_resposta)
        result = self._executar_comando(comando, falar_resposta=falar_resposta)
        log.debug("resposta: %r", result)
        return result

    def _falar_se_ativo(self, texto: str, *, falar_resposta: bool) -> None:
        if not texto or not falar_resposta:
            return
        try:
            falar(texto)
            self._ultima_fala = time.time()
        except Exception as e:
            log.warning("Fala falhou: %s", e)

    def _executar_comando(self, comando: str, *, falar_resposta: bool = True) -> str:
        try:
            if not comando:
                return ""
            log.info("Comando recebido: %s", comando[:80])

            comando_processar = comando.lower().strip()

            # "PARE DE FALAR" deve executar ANTES de qualquer fala
            if any(p in comando_processar for p in ("pare de falar", "cala a boca",
                                                     "silêncio", "silenciar", "para de falar")):
                from core.voice import parar_fala as pf
                pf()
                return "Falando parado."

            if not comando_processar:
                return self._oferecer_ajuda(falar_resposta=falar_resposta)

            registrar("usuario", comando)
            db_memoria.registrar_padrao(comando_processar)
            resposta = self._verificar_comandos_rapidos(
                comando_processar, falar_resposta=falar_resposta
            )
            if resposta:
                log.info("Comando rapido: %s", resposta)
                return resposta
            resultado = self._processar_com_ia(
                comando_processar, falar_resposta=falar_resposta
            )
            log.info("Resposta: %s", resultado[:80] if resultado else "")
            self._falar_se_ativo(resultado, falar_resposta=falar_resposta)
            return resultado or ""
        except Exception as e:
            log.exception("Falha na execucao")
            self._falar_se_ativo(
                "Desculpe, tive uma falha no sistema interno.",
                falar_resposta=falar_resposta,
            )
            return ""

    def _oferecer_ajuda(self, *, falar_resposta: bool = True) -> str:
        msg = "O que posso fazer por você?"
        self._falar_se_ativo(msg, falar_resposta=falar_resposta)
        return msg

    def _verificar_comandos_rapidos(
        self, comando: str, *, falar_resposta: bool = True
    ) -> str:
        cmd = comando.lower().strip()
        if any(p in cmd for p in ("pare de falar", "cala a boca", "silêncio", "silenciar", "para de falar")):
            from core.voice import parar_fala as pf
            pf()
            return "Falando parado."

        if any(p in cmd for p in ("desligar", "sair", "parar", "dormir", "descansar")):
            if any(p in cmd for p in ("assistente", "alexia", "programa", "sistema", "tudo")):
                self._falar_se_ativo("Desligando.", falar_resposta=falar_resposta)
                self.parar()
                _desligar_tudo()
                return "Desligando."

        if "hora" in cmd or "que horas" in cmd:
            hora = datetime.now().strftime("%H:%M")
            resposta = f"Agora são exatamente {hora}"
            registrar("assistente", resposta)
            return resposta

        if any(p in cmd for p in ("data", "que dia", "que dia é")):
            data = datetime.now().strftime("%d de %B de %Y")
            resposta = f"Hoje é {data}"
            registrar("assistente", resposta)
            return resposta

        if any(p in cmd for p in ("boa noite", "boa noite darkson")):
            resposta = "Boa noite"
            registrar("assistente", resposta)
            return resposta
        if any(p in cmd for p in ("bom dia", "bom dia darkson")):
            resposta = "Bom dia"
            registrar("assistente", resposta)
            return resposta
        if any(p in cmd for p in ("boa tarde", "boa tarde darkson")):
            resposta = "Boa tarde"
            registrar("assistente", resposta)
            return resposta
        palavras = set(cmd.split())
        if any(p in palavras for p in ("olá", "ola", "oi", "hey", "eai", "fala")) or "e aí" in cmd:
            saudacoes = ["Fala", "Oi", "Olá", "E aí"]
            import random
            resposta = random.choice(saudacoes)
            registrar("assistente", resposta)
            return resposta

        return ""

    def _processar_com_ia(self, comando: str, *, falar_resposta: bool = True) -> str:
        try:
            intencao = self.cerebro.detectar_intencao(comando)
            intent = intencao.get("intent", "conversa")
            params = intencao.get("parametros", {})

            if intent == "parar_fala":
                from core.voice import parar_fala as pf
                pf()
                return "Falando parado."

            if intent == "abrir_programa":
                programa = params.get("programa", comando)
                self.pc.abrir_programa(programa)
                return f"A abrir {programa}."
            elif intent == "buscar_web":
                termo = params.get("termo", comando)
                self._falar_se_ativo(
                    f"Pesquisando sobre {termo}.", falar_resposta=falar_resposta
                )
                resultado = buscar_web(termo)
                return resultado
            elif intent == "fetch_page":
                url = params.get("url", comando)
                self._falar_se_ativo(f"A aceder {url}.", falar_resposta=falar_resposta)
                resultado = fetch_page(url)
                return resultado[:1000]
            elif intent == "previsao_tempo":
                cidade = params.get("cidade", "São Paulo")
                return self.clima.obter_previsao(cidade)
            elif intent == "noticias":
                assunto = params.get("assunto", "")
                return self.noticias.obter_noticias(assunto)
            elif intent == "lembrete":
                texto = params.get("texto", comando)
                import re
                match = re.search(r'(\d+)\s*(minutos?|min|horas?|h|segundos?|seg|s)', texto, re.IGNORECASE)
                if match:
                    valor = int(match.group(1))
                    unidade = match.group(2).lower()
                    if unidade.startswith('h'):
                        minutos = valor * 60
                    elif unidade.startswith('s'):
                        minutos = max(1, valor // 60)
                    else:
                        minutos = valor
                    texto = re.sub(
                        r'\s*(?:em|daqui|após|dentro\s*de)?\s*\d+\s*(?:minutos?|min|horas?|h|segundos?|seg|s)\s*',
                        '', texto, flags=re.IGNORECASE
                    ).strip()
                else:
                    minutos = int(params.get("minutos", 5))
                self.lembretes.criar(texto, minutos)
                return f"Lembrete criado para daqui a {minutos} minutos: {texto}."
            elif intent == "tocar_musica":
                self.pc.abrir_programa("spotify")
                return "A abrir o Spotify."
            elif intent == "comando_sistema":
                acao = params.get("acao", "")
                self.pc.executar_comando_sistema(acao)
                return f"{acao} executado."
            elif intent == "diagnostico":
                return self.diagnostico.relatorio_completo()
            elif intent in ("ip_local", "ip_publico", "info_disco", "info_so", "info_rede"):
                mapa = {
                    "ip_local": self.info_sistema.ip_local,
                    "ip_publico": self.info_sistema.ip_publico,
                    "info_disco": self.info_sistema.disco,
                    "info_so": self.info_sistema.sistema_operacional,
                    "info_rede": self.info_sistema.rede,
                }
                return mapa[intent]()
            elif intent == "executar_cmd":
                cmd = params.get("comando", comando)
                resultado = self.pc.executar_comando(cmd)
                if resultado:
                    return f"Comando executado. {resultado[:200]}"
                return "Comando executado."
            elif intent == "configuracao":
                pagina = params.get("pagina", "")
                self.pc.abrir_configuracao(pagina)
                if pagina:
                    return f"A abrir configuração de {pagina}."
                return "A abrir configurações."
            elif intent == "info_processos":
                return self.pc.obter_processos()
            elif intent == "info_servicos":
                return self.pc.obter_servicos()
            elif intent == "db_status":
                return self._status_db()
            elif intent == "salvar_conhecimento":
                titulo = params.get("titulo") or params.get("assunto") or comando
                conteudo = params.get("conteudo") or params.get("descricao") or ""
                bloco = params.get("bloco") or params.get("categoria") or "Geral"
                tags = params.get("tags", "")
                if not conteudo:
                    self._falar_se_ativo(
                        "Qual a informacao?", falar_resposta=falar_resposta
                    )
                    conteudo = self.voz.ouvir_comando() or ""
                if conteudo and len(conteudo) > 10:
                    self.conhecimento.adicionar(titulo, conteudo, bloco, tags)
                    return f"Salvo em {bloco}: {titulo}."
                return "Conteudo muito curto."
            elif intent == "buscar_conhecimento":
                termo = params.get("termo") or params.get("assunto") or comando
                resultados = self.conhecimento.buscar(termo)
                if resultados:
                    r = resultados[0]
                    return f"[{r['bloco']}] {r['titulo']}: {r['conteudo'][:500]}"
                return f"Nada encontrado sobre {termo}."
            elif intent == "listar_conhecimento":
                bloco_nome = params.get("bloco") or params.get("categoria") or ""
                if bloco_nome:
                    items = self.conhecimento.listar_por_bloco(bloco_nome)
                    if items:
                        nomes = [i["titulo"] for i in items[:10]]
                        return f"Bloco '{bloco_nome}': " + ", ".join(nomes)
                    return f"Bloco '{bloco_nome}' vazio."
                blocos = self.conhecimento.listar_blocos()
                if blocos:
                    return "Blocos: " + ", ".join(f"{b['nome']}({b['topicos']})" for b in blocos)
                return "Base de conhecimento vazia."
            elif intent == "audio_devices":
                return listar_audio_devices()
            elif intent == "capturar_webcam":
                resultado = capturar_webcam()
                self._falar_se_ativo(resultado, falar_resposta=falar_resposta)
                return resultado
            elif intent == "gravar_tela":
                nums = re.findall(r"(\d+)", comando)
                segundos = int(nums[0]) if nums else 5
                resultado = gravar_tela(segundos)
                self._falar_se_ativo(resultado, falar_resposta=falar_resposta)
                return resultado
            elif intent == "tirar_print":
                from skills.pc_control import ControladorPC
                ControladorPC()._capturar_tela()
                return "Print salvo."
            elif intent == "listar_janelas":
                janelas = self.pc.listar_janelas()
                if not janelas:
                    return "Nenhuma janela aberta."
                return "Janelas abertas:\n" + "\n".join(
                    f"{'[ATIVA]' if j['ativa'] else ''} {j['titulo'][:60]}"
                    for j in janelas[:15]
                )
            elif intent == "alternar_janela":
                termo = params.get("termo", comando)
                if self.pc.alternar_para_janela(termo):
                    return f"Alternado para {termo}."
                return f"Janela '{termo}' nao encontrada."
            elif intent == "fechar_janela":
                termo = params.get("termo", comando)
                if self.pc.fechar_janela(termo):
                    return f"Janela '{termo}' fechada."
                return f"Janela '{termo}' nao encontrada."
            elif intent == "listar_sessoes_audio":
                sessoes = self.pc.listar_sessoes_audio()
                if not sessoes:
                    return "Nenhuma sessao de audio ativa."
                return "Sessoes de audio:\n" + "\n".join(
                    f"{s['processo']}: volume {s['volume']:.0%}{' (MUTADO)' if s['mutado'] else ''}"
                    for s in sessoes[:10]
                )
            elif intent == "volume_app":
                processo = params.get("processo", comando)
                return self.pc.volume_app(processo)
            elif intent == "programas_abertos":
                monitores = self.pc.programas_por_monitor()
                if not monitores:
                    return "Nenhum programa visivel na tela."
                linhas = []
                for mon in monitores:
                    if mon["programas"]:
                        linhas.append(f"Monitor {mon['monitor']}:")
                        linhas.extend(f"  - {p['nome']}" for p in mon["programas"][:10])
                return "\n".join(linhas) if linhas else "Nenhum programa visivel na tela."
            elif intent == "listar_servicos_windows":
                servicos = self.pc.listar_servicos_windows()
                if not servicos:
                    return "Nenhum servico encontrado."
                return "Servicos do Windows:\n" + "\n".join(
                    f"{s['exibicao']} [{s['status']}]"
                    for s in servicos[:15]
                )
            elif intent == "controle_servico":
                nome = params.get("nome", "")
                acao = params.get("acao", "iniciar")
                return self.pc.controle_servico(nome, acao)
            elif intent == "ler_registro":
                chave = params.get("chave", comando)
                return self.pc.ler_registro(chave)
            elif intent == "volume_total":
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = cast(interface, POINTER(IAudioEndpointVolume))
                atual = volume.GetMasterVolumeLevelScalar()
                if "aumentar" in comando:
                    novo = min(1.0, atual + 0.1)
                    volume.SetMasterVolumeLevelScalar(novo, None)
                    return f"Volume aumentado para {novo:.0%}"
                elif "diminuir" in comando or "abaixar" in comando:
                    novo = max(0.0, atual - 0.1)
                    volume.SetMasterVolumeLevelScalar(novo, None)
                    return f"Volume reduzido para {novo:.0%}"
                elif "mutar" in comando or "silenciar" in comando:
                    volume.SetMute(1, None)
                    return "Volume mutado."
                elif "ativar" in comando:
                    volume.SetMute(0, None)
                    return "Volume ativado."
                return f"Volume atual: {atual:.0%}"
            elif intent == "info_hardware":
                import platform
                import psutil
                so = platform.system()
                versao = platform.version()
                cpu = psutil.cpu_count(logical=False)
                ram = round(psutil.virtual_memory().total / (1024**3), 1)
                return f"Sistema: {so} {versao[:20]}, CPU: {cpu} nucleos, RAM: {ram}GB"
            elif intent == "matar_processo":
                import psutil
                termo = params.get("nome", comando)
                mortos = []
                for p in psutil.process_iter(["pid", "name"]):
                    try:
                        if termo.lower() in p.info["name"].lower():
                            p.kill()
                            mortos.append(p.info["name"])
                    except Exception:
                        pass
                if mortos:
                    return f"Processo(s) encerrados: {', '.join(mortos[:5])}"
                return f"Processo '{termo}' nao encontrado."
            elif intent == "verificar_programa":
                programa = params.get("programa", comando).lower().strip()
                # 1. Verifica janelas visiveis
                visiveis = self.pc.programas_visiveis()
                for v in visiveis:
                    if programa in v["nome"].lower() or programa in v["titulo"].lower():
                        return f"Sim, {v['nome']} esta aberto na tela."
                # 2. Fallback: analisa a tela com OCR/visao
                try:
                    from skills.visao import analisar_ecra
                    resultado = analisar_ecra(f"O programa {programa} esta visivel na tela? Responda apenas sim ou nao e o nome.")
                    if "sim" in resultado.lower():
                        return resultado
                except Exception:
                    pass
                return f"Nao encontrei {programa} na tela."
            elif intent == "analisar_ecra" or intent == "visualizar_ecra":
                pergunta = params.get("pergunta", comando)
                return analisar_ecra(pergunta)
            elif intent == "desligar_assistente":
                self._falar_se_ativo("Desligando.", falar_resposta=falar_resposta)
                _desligar_tudo()
                return "Encerrando..."
            elif intent == "gerar_imagem":
                prompt = params.get("prompt") or params.get("descricao") or comando
                estilo = None
                try:
                    from core.brain import carregar_perfil, salvar_perfil
                    perfil = carregar_perfil()
                    ultimo_estilo = perfil.get("ultimo_estilo")
                    _abrir_lista_estilos()
                    self._falar_se_ativo(
                        "Escolha um estilo na lista que abri, ou diga o nome.",
                        falar_resposta=falar_resposta,
                    )
                    resp_estilo = self.voz.ouvir_comando()
                    if resp_estilo:
                        resp_lower = resp_estilo.lower().strip()
                        for e in ESTILOS_DISPONIVEIS:
                            if e.lower() in resp_lower or resp_lower in e.lower():
                                estilo = e
                                break
                        if not estilo and ultimo_estilo:
                            estilo = ultimo_estilo
                            self._falar_se_ativo(
                                f"A usar o último estilo: {estilo}.",
                                falar_resposta=falar_resposta,
                            )
                    if estilo:
                        salvar_perfil("ultimo_estilo", estilo)
                        self.cerebro.aprendizado.aprender(
                            f"estilo {estilo.lower()}", "gerar_imagem",
                            {"prompt": prompt, "descricao": prompt}
                        )
                except Exception:
                    pass
                return gerar_imagem(prompt, estilo)
            else:
                self.cerebro.aprendizado.registrar_desconhecido(comando)
                ctx_extra = ""
                conhecimentos = self.conhecimento.buscar(comando, limite=3)
                if conhecimentos:
                    ctx_extra = "\nInformação da minha base de conhecimento:\n" + "\n".join(
                        f"- {c['titulo']}: {c['conteudo'][:300]}" for c in conhecimentos
                    )
                visiveis = self.pc.programas_visiveis()
                if visiveis:
                    ctx_extra += "\n[PROGRAMAS VISIVEIS NA TELA]\n" + "\n".join(f"- {p['nome']}" for p in visiveis[:20])
                resposta = intencao.get("resposta", "")
                if not resposta:
                    comando_completo = comando
                    if ctx_extra:
                        comando_completo = f"{comando}\n\n{ctx_extra}"
                    resposta = self.cerebro.processar(comando_completo)
                if resposta:
                    match = re.search(r'\[KNOWLEDGE:\s*(.*?)\|(.*?)\|(.*?)\]', resposta)
                    if match:
                        titulo = match.group(1).strip()
                        conteudo = match.group(2).strip()
                        bloco = match.group(3).strip()
                        resposta = re.sub(r'\s*\[KNOWLEDGE:.*?\]', '', resposta).strip()
                        self.conhecimento.adicionar(titulo, conteudo, bloco)
                        log.info(f"Auto-conhecimento salvo: {titulo}")
                    registrar("assistente", resposta)
                return resposta
        except Exception as exc:
            erro = str(exc)
            log.exception("Erro no processamento")
            registrar("assistente", f"Erro: {erro[:200]}")
            return f"Erro: {erro[:100]}"

    def _verificar_lembretes(self) -> None:
        while self.ativo:
            try:
                vencidos = self.lembretes.verificar()
                for lembrete in vencidos:
                    falar(f"Lembrete: {lembrete['texto']}")
            except Exception as exc:
                log.exception("Erro na verificacao de lembretes")
            time.sleep(10)

    def _monitorizar_sistema(self) -> None:
        while self.ativo:
            try:
                uso_cpu = psutil.cpu_percent(interval=1)
                if uso_cpu > 90.0:
                    alerta = f"CPU em {uso_cpu:.0f}%. Verifique os processos."
                    registrar("sistema", alerta)
                    falar(alerta)
                    time.sleep(300)
                else:
                    time.sleep(15)
            except Exception as exc:
                log.warning(f"Erro na monitorizacao: {exc}")
                time.sleep(60)

    def _varredura_programas(self) -> None:
        while self.ativo:
            try:
                dados = self.pc.escanear_programas()
                self._ultima_varredura = dados.get("processos", [])
                db_memoria.registrar_comando("varredura", f"{len(dados.get('janelas',[]))} janelas, {len(dados.get('processos',[]))} processos", "", success=True)
                time.sleep(50)
            except Exception as e:
                log.warning(f"Erro na varredura: {e}")
                time.sleep(50)

    def _status_db(self) -> str:
        mb = db_memoria.db_tamanho_mb()
        cont = db_memoria.db_contagem()
        return (f"Banco: {mb:.1f}MB. "
                f"{cont['conversas']} conversas, "
                f"{cont['memorias']} memorias, "
                f"{cont['comandos']} comandos, "
                f"{cont['padroes']} padroes.")

    def parar(self) -> None:
        self.ativo = False
        self.lembretes.salvar()
