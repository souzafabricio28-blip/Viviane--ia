from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
import sys
import time

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="[DarkSON] %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("DarkSON")
# Suprime logs do Flask/werkzeug
logging.getLogger("werkzeug").setLevel(logging.ERROR)

from flask import Flask, jsonify, render_template, request, Response, send_file

app = Flask(__name__)

from core.amplitude import get_amplitude
from core.assistant import Assistente
from core.conhecimento import BaseConhecimento
from core.conversa import limpar, obter_historico, registrar
from core.memoria import memoria as db_memoria
from core.settings import settings
from core.transcricao import transcrever_wav
from core.voice import gerar_tts_bytes

def _autorizar() -> bool:
    if not settings.api_token:
        return False
    auth = request.headers.get("Authorization", "")
    return auth == f"Bearer {settings.api_token}"


_ORIGENS_PERMITIDAS = {
    o.strip() for o in settings.allow_origins.split(",") if o.strip()
}


@app.before_request
def verificar_origem():
    if request.path.startswith("/static/"):
        return
    origem = request.headers.get("Origin", "")
    if not origem:
        return
    if "localhost" in origem or "127.0.0.1" in origem:
        return
    if origem.rstrip("/") in _ORIGENS_PERMITIDAS:
        return
    if _ORIGENS_PERMITIDAS:
        return jsonify({"erro": "Origem nao autorizada"}), 403


@app.after_request
def add_cors(response):
    origem = request.headers.get("Origin", "")
    if "localhost" in origem or "127.0.0.1" in origem or not origem or origem.rstrip("/") in _ORIGENS_PERMITIDAS:
        response.headers["Access-Control-Allow-Origin"] = origem or "*"
    else:
        response.headers["Access-Control-Allow-Origin"] = ""
    response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


_assistente: Assistente | None = None


def get_assistente() -> Assistente:
    global _assistente
    if _assistente is None:
        _assistente = Assistente(modo_web=True)
    return _assistente


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/historico")
def api_historico():
    return jsonify(obter_historico())


@app.route("/api/enviar", methods=["POST"])
def api_enviar():
    data = request.get_json()
    texto = data.get("texto", "").strip()
    if not texto:
        return jsonify({"erro": "Texto vazio"}), 400
    registrar("usuario", texto)
    ass = get_assistente()
    resposta = ass.executar_comando(texto, falar_resposta=False)
    return jsonify({"ok": True, "resposta": resposta})


@app.route("/api/tts")
def api_tts():
    texto = request.args.get("texto", "").strip()
    if not texto:
        return jsonify({"erro": "Texto vazio"}), 400
    audio = gerar_tts_bytes(texto)
    if not audio:
        return jsonify({"erro": "Falha ao gerar audio"}), 500
    return Response(audio, mimetype="audio/mpeg", headers={
        "Cache-Control": "no-store",
        "Content-Disposition": 'inline; filename="tts.mp3"',
    })


@app.route("/api/falar", methods=["POST"])
def api_falar():
    data = request.get_json()
    texto = data.get("texto", "")
    if texto:
        falar(texto)
    return jsonify({"ok": True})


@app.route("/api/transcrever", methods=["POST"])
def api_transcrever():
    wav_bytes = request.get_data()
    texto = transcrever_wav(wav_bytes)
    return jsonify({"ok": True, "texto": texto})


@app.route("/api/parar_fala", methods=["POST"])
def api_parar_fala():
    parar_fala()
    return jsonify({"ok": True})


@app.route("/api/status")
def api_status():
    ass = get_assistente()
    return jsonify({"ativo": ass.ativo})


@app.route("/api/limpar", methods=["POST"])
def api_limpar():
    limpar()
    return jsonify({"ok": True})


@app.route("/api/conhecimento/buscar", methods=["POST"])
def api_conhecimento_buscar():
    data = request.get_json()
    termo = data.get("termo", "").strip()
    if not termo:
        return jsonify({"erro": "Termo vazio"}), 400
    base = BaseConhecimento()
    resultados = base.buscar(termo, limite=10)
    return jsonify({"ok": True, "resultados": resultados})


@app.route("/api/conhecimento/adicionar", methods=["POST"])
def api_conhecimento_adicionar():
    data = request.get_json()
    titulo = data.get("titulo", "").strip()
    conteudo = data.get("conteudo", "").strip()
    if not titulo or not conteudo:
        return jsonify({"erro": "Titulo e conteudo obrigatorios"}), 400
    bloco = data.get("bloco", "Geral").strip()
    tags = data.get("tags", "").strip()
    base = BaseConhecimento()
    base.adicionar(titulo, conteudo, bloco, tags)
    return jsonify({"ok": True})


@app.route("/api/conhecimento/blocos")
def api_conhecimento_blocos():
    base = BaseConhecimento()
    return jsonify({"ok": True, "blocos": base.listar_blocos()})


@app.route("/globo")
def globo():
    return render_template("globo.html")


@app.route("/api/amplitude")
def api_amplitude():
    return jsonify({"amplitude": get_amplitude()})

@app.route("/api/stream")
def api_stream():
    def gerar():
        ultima_amplitude = 0.0
        while True:
            amp = get_amplitude()
            if abs(amp - ultima_amplitude) > 0.01:
                yield f"data: {json.dumps({'amplitude': amp})}\n\n"
                ultima_amplitude = amp
            time.sleep(0.05)
    return Response(gerar(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })


# ─── Memória API ──────────────────────────────────────────────

@app.route("/api/memoria/memorias")
def api_memoria_memorias():
    tipo = request.args.get("tipo")
    limite = int(request.args.get("limite", 50))
    return jsonify({"ok": True, "memorias": db_memoria.listar_memorias(tipo, limite)})


@app.route("/api/memoria/buscar", methods=["POST"])
def api_memoria_buscar():
    data = request.get_json()
    termo = data.get("termo", "").strip()
    if not termo:
        return jsonify({"erro": "Termo vazio"}), 400
    return jsonify({"ok": True, "resultados": db_memoria.buscar_memorias(termo)})


@app.route("/api/memoria/salvar", methods=["POST"])
def api_memoria_salvar():
    data = request.get_json()
    titulo = data.get("titulo", "").strip()
    conteudo = data.get("conteudo", "").strip()
    if not titulo or not conteudo:
        return jsonify({"erro": "Titulo e conteudo obrigatorios"}), 400
    db_memoria.salvar_memoria(
        titulo=titulo,
        conteudo=conteudo,
        tipo=data.get("tipo", "facto"),
        tags=data.get("tags", ""),
        importancia=int(data.get("importancia", 2)),
    )
    return jsonify({"ok": True})


@app.route("/api/memoria/remover", methods=["POST"])
def api_memoria_remover():
    data = request.get_json()
    mid = data.get("id")
    if not mid:
        return jsonify({"erro": "ID obrigatorio"}), 400
    db_memoria.remover_memoria(mid)
    return jsonify({"ok": True})


@app.route("/api/memoria/conversas")
def api_memoria_conversas():
    limite = int(request.args.get("limite", 50))
    return jsonify({"ok": True, "conversas": db_memoria.historico_conversas(limite)})


@app.route("/api/memoria/perfil")
def api_memoria_perfil():
    return jsonify({"ok": True, "perfil": db_memoria.listar_perfil()})


@app.route("/api/memoria/perfil/definir", methods=["POST"])
def api_memoria_perfil_definir():
    data = request.get_json()
    chave = data.get("chave", "").strip()
    if not chave:
        return jsonify({"erro": "Chave obrigatoria"}), 400
    db_memoria.definir_perfil(chave, data.get("valor", ""), data.get("tipo", "texto"))
    return jsonify({"ok": True})


@app.route("/api/memoria/padroes")
def api_memoria_padroes():
    return jsonify({"ok": True, "padroes": db_memoria.comandos_frequentes()})


@app.route("/api/executar", methods=["POST"])
def api_executar():
    if not settings.api_token:
        return jsonify({
            "erro": "Rota desativada. Configure DARKSON_API_TOKEN no .env para habilitar execucao remota."
        }), 503
    if not _autorizar():
        return jsonify({"erro": "Token invalido. Envie Authorization: Bearer <token>"}), 401
    data = request.get_json()
    comando = data.get("comando", "").strip()
    if not comando:
        return jsonify({"erro": "Comando vazio"}), 400
    from skills.pc_control import ControladorPC
    pc = ControladorPC()
    resultado = pc.executar_comando(comando)
    log.info(f"Comando remoto executado: {comando[:80]}")
    return jsonify({"ok": True, "resultado": resultado})


@app.route("/api/comandos", methods=["GET"])
def api_comandos():
    limite = int(request.args.get("limite", 30))
    return jsonify({"ok": True, "comandos": db_memoria.ultimos_comandos(limite)})


@app.route("/api/comandos/limpar", methods=["POST"])
def api_comandos_limpar():
    with sqlite3.connect(str(settings.data_dir / "memoria.db")) as conn:
        conn.execute("DELETE FROM comandos_executados")
        conn.commit()
    return jsonify({"ok": True})


@app.route("/api/banco/download")
def api_banco_download():
    caminho = settings.data_dir / "memoria.db"
    if not caminho.exists():
        return jsonify({"erro": "Banco nao encontrado"}), 404
    return send_file(str(caminho), as_attachment=True, download_name="memoria.db")


@app.route("/api/banco/status")
def api_banco_status():
    mb = db_memoria.db_tamanho_mb()
    cont = db_memoria.db_contagem()
    return jsonify({
        "ok": True,
        "tamanho_mb": round(mb, 2),
        "contagem": cont,
        "caminho": str(settings.data_dir / "memoria.db"),
    })


def _abrir_edge(url: str) -> None:
    try:
        edge = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
        if os.path.exists(edge):
            subprocess.Popen([edge, "--new-window", url], shell=False)
        else:
            webbrowser.open(url)
    except Exception:
        webbrowser.open(url)


def iniciar_servidor(porta: int | None = None, host: str | None = None) -> None:
    if not sys.stdout or not hasattr(sys.stdout, "write"):
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")
    erros = settings.validar()
    if erros:
        for e in erros:
            log.warning(e)
    porta = porta or settings.api_port
    host = host or settings.api_host
    if host == "0.0.0.0":
        log.warning("Servidor exposto na rede (DARKSON_HOST=0.0.0.0). Use apenas em rede confiavel.")
    if not settings.api_token:
        log.warning("DARKSON_API_TOKEN nao configurado: /api/executar desativada.")
    log.info("DarkSON rodando em http://%s:%d (voz: %s)", host, porta, settings.tts_voice)
    log.info("Whisper carregado sob demanda na primeira transcricao.")
    app.run(host=host, port=porta, debug=False, threaded=True, use_reloader=False)


if __name__ == "__main__":
    iniciar_servidor()
