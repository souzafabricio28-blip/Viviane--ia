// ---- CHAT STATE ----
const chatBox = document.getElementById('chat-box');
const statusDot = document.getElementById('status-dot');
const micBtn = document.getElementById('mic-btn');
const micLabel = document.getElementById('mic-label');
const textInput = document.getElementById('text-input');
const typingIndicator = document.getElementById('typing-indicator');

function addMsg(tipo, texto, hora) {
    const w = document.querySelector('.welcome-msg');
    if (w) w.remove();
    const m = document.createElement('div');
    m.className = `msg ${tipo}`;
    const h = hora ? `<span class="time">${hora}</span>` : '';
    m.innerHTML = `${texto}${h}`;
    chatBox.appendChild(m);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function setStatus(tipo) {
    statusDot.className = 'status-dot';
    if (tipo) statusDot.classList.add(tipo);
}

function mostrarTyping(m) {
    const el = document.getElementById('typing-indicator');
    if (el) el.style.display = m ? 'flex' : 'none';
}

// ---- WAV ENCODE ----
function encodeWAV(samples, sr) {
    const buf = new ArrayBuffer(44 + samples.length * 2);
    const v = new DataView(buf);
    const w = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    w(0, 'RIFF'); v.setUint32(4, 36 + samples.length * 2, true);
    w(8, 'WAVE'); w(12, 'fmt ');
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, sr, true); v.setUint32(28, sr * 2, true);
    v.setUint16(32, 2, true); v.setUint16(34, 16, true);
    w(36, 'data'); v.setUint32(40, samples.length * 2, true);
    let o = 44;
    for (let i = 0; i < samples.length; i++) {
        const s = Math.max(-1, Math.min(1, samples[i]));
        v.setInt16(o, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
        o += 2;
    }
    return new Blob([buf], { type: 'audio/wav' });
}

// ---- VOICE (push-to-talk PCM) ----
let gravando = false;
let gravStream = null;
let gravCtx = null;
let gravSource = null;
let gravProcessor = null;
let gravChunks = [];
let gravSR = 16000;

function mostrarAmplitude(v) {
    const bar = document.getElementById('amp-bar');
    if (bar) { bar.style.width = Math.min(100, v * 100) + '%'; }
}

async function iniciarGravacao() {
    if (gravando) return;
    try {
        gravStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        gravCtx = new AudioContext({ sampleRate: gravSR });
        if (gravCtx.state === 'suspended') await gravCtx.resume();
        gravSR = gravCtx.sampleRate;
        gravSource = gravCtx.createMediaStreamSource(gravStream);
        gravProcessor = gravCtx.createScriptProcessor(4096, 1, 1);
        gravChunks = [];

        gravProcessor.onaudioprocess = (e) => {
            gravChunks.push(e.inputBuffer.getChannelData(0).slice());
        };

        gravSource.connect(gravProcessor);
        gravProcessor.connect(gravCtx.destination);
        gravando = true;
        micBtn.classList.add('gravando');
        micLabel.textContent = 'Gravando...';
    } catch(e) {
        micLabel.textContent = 'Erro: ' + e.message;
        addMsg('action', 'Erro microfone: ' + e.message);
    }
}

function pararGravacao() {
    if (!gravando) return;
    gravando = false;
    micBtn.classList.remove('gravando');

    if (gravProcessor) gravProcessor.disconnect();
    if (gravSource) gravSource.disconnect();
    if (gravCtx) gravCtx.close();
    if (gravStream) gravStream.getTracks().forEach(t => t.stop());

    const len = gravChunks.reduce((a, c) => a + c.length, 0);
    if (len < 1000) {
        micLabel.textContent = 'Audio muito curto';
        setTimeout(() => { micLabel.textContent = 'Segure para falar'; }, 1500);
        return;
    }

    const all = new Float32Array(len);
    let off = 0;
    for (const c of gravChunks) { all.set(c, off); off += c.length; }

    let maxAmp = 0;
    for (let i = 0; i < all.length; i++) {
        const v = Math.abs(all[i]);
        if (v > maxAmp) maxAmp = v;
    }
    mostrarAmplitude(maxAmp);
    if (maxAmp < 0.003) {
        micLabel.textContent = 'Nada detectado';
        setTimeout(() => { micLabel.textContent = 'Segure para falar'; }, 1500);
        return;
    }

    let down = all;
    if (gravSR !== 16000) {
        const downLen = Math.floor(all.length * 16000 / gravSR);
        down = new Float32Array(downLen);
        for (let i = 0; i < downLen; i++) {
            down[i] = all[Math.min(Math.floor(i * gravSR / 16000), all.length - 1)];
        }
    }

    const wav = encodeWAV(down, 16000);
    processarAudio(wav);
}

async function processarAudio(wavBlob) {
    micLabel.textContent = 'Transcrevendo...';
    try {
        const r = await fetch('/api/transcrever', { method: 'POST', body: wavBlob });
        const d = await r.json();
        if (d.texto && d.texto.trim()) {
            textInput.value = d.texto;
            micLabel.textContent = 'Processando...';
            await enviarTexto();
            micLabel.textContent = 'Segure para falar';
        } else {
            micLabel.textContent = 'Nao entendi';
            setTimeout(() => { micLabel.textContent = 'Segure para falar'; }, 2000);
        }
    } catch(e) {
        console.error('transcricao', e);
        micLabel.textContent = 'Erro transcricao';
    }
}

// ---- SEND ----
let ttsAudio = null;

function playTTS(texto) {
    if (!texto || !texto.trim()) return;
    if (ttsAudio) { ttsAudio.pause(); ttsAudio = null; }
    const url = '/api/tts?texto=' + encodeURIComponent(texto.slice(0, 300));
    ttsAudio = new Audio(url);
    ttsAudio.play().catch(() => {});
}

async function enviarTexto() {
    const texto = textInput.value.trim();
    if (!texto) return;
    textInput.value = '';
    const agora = new Date().toLocaleTimeString('pt-BR', {hour:'2-digit',minute:'2-digit'});
    addMsg('user', texto, agora);
    setStatus('thinking');
    mostrarTyping(true);
    try {
        const r = await fetch('/api/enviar', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({texto})
        });
        mostrarTyping(false);
        const d = await r.json();
        if (d.resposta) {
            addMsg('assistant', d.resposta, agora);
            playTTS(d.resposta);
        }
        setStatus('');
    } catch(e) {
        mostrarTyping(false);
        addMsg('action', 'Erro de conexao.');
        setStatus('');
    }
}

// ---- COMMANDS ----
let comandosOverlay = null;

function abrirComandos() {
    fecharOverlays();
    const body = document.getElementById('ov-body-comandos');
    if (!body) return;
    comandosOverlay = document.getElementById('overlay-comandos');
    comandosOverlay.classList.add('open');
    body.innerHTML = '<div class="ov-empty">Carregando...</div>';
    fetch('/api/comandos?limite=50')
        .then(r => r.json())
        .then(d => {
            if (!d.comandos || d.comandos.length === 0) {
                body.innerHTML = '<div class="ov-empty">Nenhum comando executado ainda.</div>';
                return;
            }
            body.innerHTML = d.comandos.map(c => `
                <div class="cmd-item">
                    <span class="cmd-type ${c.success ? '' : 'erro'}">${c.tipo}</span>
                    <div class="cmd-text">
                        <div class="cmd-comando">${esc(c.comando)}</div>
                        <div class="cmd-resultado">${esc((c.resultado||'').slice(0,80))}</div>
                    </div>
                    <span class="cmd-time">${c.data ? new Date(c.data+'Z').toLocaleTimeString('pt-BR', {hour:'2-digit',minute:'2-digit'}) : ''}</span>
                </div>
            `).join('');
        })
        .catch(() => { body.innerHTML = '<div class="ov-empty">Erro ao carregar.</div>'; });
}

// ---- MEMORIES ----
let memoriasTab = 'memorias';

function abrirMemorias() {
    fecharOverlays();
    document.getElementById('overlay-memorias').classList.add('open');
    memoriasTab = 'memorias';
    ativarTabMemorias('memorias');
    carregarMemorias();
}

function ativarTabMemorias(tab) {
    memoriasTab = tab;
    document.querySelectorAll('#overlay-memorias .overlay-tab').forEach(t => {
        t.classList.toggle('active', t.dataset.tab === tab);
    });
    document.querySelectorAll('#overlay-memorias .overlay-content').forEach(c => {
        c.classList.toggle('active', c.id === `ov-mem-${tab}`);
    });
    if (tab === 'memorias') carregarMemorias();
    else if (tab === 'conversas') carregarConversas();
    else if (tab === 'perfil') carregarPerfil();
}

function carregarMemorias() {
    const body = document.getElementById('ov-mem-memorias');
    if (!body) return;
    body.innerHTML = '<div class="ov-empty">Carregando...</div>';
    fetch('/api/memoria/memorias?limite=30')
        .then(r => r.json())
        .then(d => {
            if (!d.memorias || d.memorias.length === 0) {
                body.innerHTML = '<div class="ov-empty">Nenhuma memória salva.</div>';
                return;
            }
            body.innerHTML = d.memorias.map(m => `
                <div class="mem-item">
                    <div class="mem-titulo">${esc(m.titulo)}</div>
                    <div class="mem-conteudo">${esc(m.conteudo)}</div>
                    <div class="mem-meta">
                        <span>${esc(m.tipo)}</span>
                        <span>${m.importancia ? '★'.repeat(m.importancia) : ''}</span>
                        <span>${esc(m.tags)}</span>
                    </div>
                </div>
            `).join('');
        })
        .catch(() => { body.innerHTML = '<div class="ov-empty">Erro ao carregar.</div>'; });
}

function carregarConversas() {
    const body = document.getElementById('ov-mem-conversas');
    if (!body) return;
    body.innerHTML = '<div class="ov-empty">Carregando...</div>';
    fetch('/api/memoria/conversas?limite=50')
        .then(r => r.json())
        .then(d => {
            if (!d.conversas || d.conversas.length === 0) {
                body.innerHTML = '<div class="ov-empty">Nenhuma conversa registrada.</div>';
                return;
            }
            body.innerHTML = d.conversas.map(c => `
                <div class="mem-item">
                    <div class="mem-titulo" style="color:${c.role === 'user' ? '#00ffc8' : '#c0c0c0'}">
                        ${c.role === 'user' ? '>' : 'D'}: ${esc(c.conteudo.slice(0,120))}
                    </div>
                    <div class="mem-meta">${new Date(c.data+'Z').toLocaleString('pt-BR')}</div>
                </div>
            `).join('');
        })
        .catch(() => { body.innerHTML = '<div class="ov-empty">Erro ao carregar.</div>'; });
}

function carregarPerfil() {
    const body = document.getElementById('ov-mem-perfil');
    if (!body) return;
    body.innerHTML = '<div class="ov-empty">Carregando...</div>';
    fetch('/api/memoria/perfil')
        .then(r => r.json())
        .then(d => {
            if (!d.perfil || Object.keys(d.perfil).length === 0) {
                body.innerHTML = '<div class="ov-empty">Nenhum dado de perfil.</div>';
                return;
            }
            body.innerHTML = Object.entries(d.perfil).map(([k, v]) => `
                <div class="mem-item">
                    <div class="mem-titulo">${esc(k)}</div>
                    <div class="mem-conteudo">${esc(typeof v === 'string' ? v : JSON.stringify(v))}</div>
                </div>
            `).join('');
        })
        .catch(() => { body.innerHTML = '<div class="ov-empty">Erro ao carregar.</div>'; });
}

// ---- KNOWLEDGE ----
function abrirConhecimento() {
    fecharOverlays();
    const body = document.getElementById('ov-body-conhecimento');
    if (!body) return;
    document.getElementById('overlay-conhecimento').classList.add('open');
    body.innerHTML = '<div class="ov-empty">Carregando...</div>';
    fetch('/api/conhecimento/blocos')
        .then(r => r.json())
        .then(d => {
            if (!d.blocos || d.blocos.length === 0) {
                body.innerHTML = '<div class="ov-empty">Base de conhecimento vazia.</div>';
                return;
            }
            body.innerHTML = d.blocos.map(b => `
                <div class="cmd-item" style="cursor:pointer" onclick="buscarConhecimento('${esc(b.nome)}')">
                    <span class="cmd-type">${esc(b.nome)}</span>
                    <div class="cmd-text">
                        <div class="cmd-comando">${b.topicos} tópico(s)</div>
                    </div>
                </div>
            `).join('');
        })
        .catch(() => { body.innerHTML = '<div class="ov-empty">Erro ao carregar.</div>'; });
}

function buscarConhecimento(termo) {
    const body = document.getElementById('ov-body-conhecimento');
    body.innerHTML = '<div class="ov-empty">Buscando...</div>';
    fetch('/api/conhecimento/buscar', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({termo})
    })
        .then(r => r.json())
        .then(d => {
            if (!d.resultados || d.resultados.length === 0) {
                body.innerHTML = `<div class="ov-empty">Nada encontrado para "${esc(termo)}".</div>`;
                return;
            }
            body.innerHTML = d.resultados.map(r => `
                <div class="mem-item">
                    <div class="mem-titulo">${esc(r.titulo)}</div>
                    <div class="mem-conteudo">${esc(r.conteudo.slice(0,200))}</div>
                    <div class="mem-meta"><span>${esc(r.bloco)}</span></div>
                </div>
            `).join('');
        })
        .catch(() => { body.innerHTML = '<div class="ov-empty">Erro ao buscar.</div>'; });
}

// ---- UTILS ----
function esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

function fecharOverlays() {
    document.querySelectorAll('.overlay').forEach(o => o.classList.remove('open'));
}

// ---- TEST MIC ----
async function testarMic() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach(t => t.stop());
        addMsg('action', 'Microfone OK');
    } catch(e) {
        addMsg('action', 'Microfone: ' + e.message);
    }
}

// ---- THEME ----
function toggleTema() {
    document.body.classList.toggle('light');
    const btn = document.querySelector('.theme-btn');
    if (btn) btn.textContent = document.body.classList.contains('light') ? '☀' : '☾';
}

// ---- DOWNLOAD ----
async function downloadBanco() {
    try {
        const r = await fetch('/api/banco/status');
        const d = await r.json();
        if (!d.ok) { addMsg('action', 'Erro ao obter status do banco.'); return; }
        addMsg('action', `Banco: ${d.tamanho_mb}MB. Fazendo download...`);
        const a = document.createElement('a');
        a.href = '/api/banco/download';
        a.download = 'memoria.db';
        a.click();
    } catch(e) {
        addMsg('action', 'Erro ao baixar banco.');
    }
}

// ---- AUTOCOMPLETE ----
const SUGESTOES = [
    "abrir chrome", "abrir spotify", "abrir vscode", "abrir calculadora",
    "desligar pc", "desligar em 30 minutos", "reiniciar pc", "bloquear pc",
    "hibernar", "suspender", "sair da conta",
    "aumentar volume", "diminuir volume", "mutar", "proxima musica",
    "print", "fechar janela", "minimizar tudo",
    "qual meu ip", "ip publico", "espaco em disco", "versao do windows",
    "quais processos", "quais servicos", "info rede",
    "tocar musica", "previsao do tempo", "noticias",
    "gerar imagem", "analisar ecra",
    "tamanho do banco", "diagnostico",
    "o que pode fazer", "lembrete",
];

let autocompleteIdx = -1;

function mostrarAutocomplete() {
    const list = document.getElementById('autocomplete-list');
    if (!list) return;
    const val = textInput.value.toLowerCase().trim();
    if (!val || val.length < 1) { list.classList.remove('open'); list.innerHTML = ''; return; }
    const match = SUGESTOES.filter(s => s.startsWith(val) && s !== val).slice(0, 6);
    if (match.length === 0) { list.classList.remove('open'); list.innerHTML = ''; return; }
    list.innerHTML = match.map((s, i) =>
        `<div class="autocomplete-item ${i === 0 ? 'selected' : ''}" data-idx="${i}" onclick="usarAutocomplete('${esc(s)}')">${esc(s)}</div>`
    ).join('');
    list.classList.add('open');
    autocompleteIdx = 0;
}

textInput.addEventListener('input', () => { autocompleteIdx = -1; mostrarAutocomplete(); });
textInput.addEventListener('keydown', (e) => {
    const list = document.getElementById('autocomplete-list');
    if (!list || !list.classList.contains('open')) return;
    const items = list.querySelectorAll('.autocomplete-item');
    if (e.key === 'ArrowDown') {
        e.preventDefault();
        items.forEach(i => i.classList.remove('selected'));
        autocompleteIdx = Math.min(autocompleteIdx + 1, items.length - 1);
        items[autocompleteIdx]?.classList.add('selected');
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        items.forEach(i => i.classList.remove('selected'));
        autocompleteIdx = Math.max(autocompleteIdx - 1, 0);
        items[autocompleteIdx]?.classList.add('selected');
    } else if (e.key === 'Tab' || e.key === 'Enter') {
        const sel = list.querySelector('.selected');
        if (sel) { e.preventDefault(); usarAutocomplete(sel.textContent); }
    }
});

function usarAutocomplete(texto) {
    textInput.value = texto;
    document.getElementById('autocomplete-list')?.classList.remove('open');
    autocompleteIdx = -1;
    textInput.focus();
}

// ---- LIMPAR ----
async function limparConversa() {
    await fetch('/api/limpar', {method:'POST'});
    chatBox.querySelectorAll('.msg').forEach(m => m.remove());
    mostrarTyping(false);
    if (!chatBox.querySelector('.welcome-msg')) {
        const w = document.createElement('div');
        w.className = 'welcome-msg';
        w.textContent = '_ DarkSON aguarda comando _';
        chatBox.insertBefore(w, document.getElementById('typing-indicator'));
    }
}

// ---- KEYBOARD ----
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') fecharOverlays();
});
