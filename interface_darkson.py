from __future__ import annotations

import os
import sys
import threading

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import customtkinter as ctk

from core.assistant import Assistente


class DarksonApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("DarkSON")
        self.geometry("400x700")
        self.minsize(350, 500)

        ctk.set_appearance_mode("dark")

        self.assistente = Assistente()
        self.thread_ia = None

        self._iniciar_servidor_flask()
        self._build_ui()

        self.after(500, lambda: self._add_resposta("DarkSON", "Olá! Como posso ajudar?"))

    def _build_ui(self):
        self.configure(fg_color="#0D0D0D")

        self.chat_area = ctk.CTkScrollableFrame(
            self, fg_color="#0D0D0D", corner_radius=0
        )
        self.chat_area.pack(fill="both", expand=True, padx=8, pady=(8, 0))

        input_frame = ctk.CTkFrame(self, fg_color="#0D0D0D", corner_radius=0)
        input_frame.pack(fill="x", side="bottom", padx=8, pady=(4, 8))

        self.entry_box = ctk.CTkEntry(
            input_frame,
            height=38,
            corner_radius=19,
            font=ctk.CTkFont(size=12),
            fg_color="#1A1A1A",
            border_width=0,
            text_color="#E0E0E0",
            placeholder_text="Digite algo...",
            placeholder_text_color="#555",
        )
        self.entry_box.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry_box.bind("<Return>", lambda e: self.enviar_comando())

        self.send_button = ctk.CTkButton(
            input_frame,
            text="➤",
            width=38,
            height=38,
            corner_radius=19,
            font=ctk.CTkFont(size=14),
            fg_color="#333",
            hover_color="#444",
            text_color="#CCC",
            command=self.enviar_comando,
        )
        self.send_button.pack(side="right")

    def _add_resposta(self, remetente, texto):
        cor_nome = "#888" if remetente == "DarkSON" else "#666"
        prefixo = "DarkSON" if remetente == "DarkSON" else "Você"

        frame = ctk.CTkFrame(self.chat_area, fg_color="transparent")
        frame.pack(fill="x", pady=(6, 0))

        label_nome = ctk.CTkLabel(
            frame,
            text=prefixo,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=cor_nome,
        )
        label_nome.pack(anchor="w", padx=(4, 0))

        label_msg = ctk.CTkLabel(
            frame,
            text=texto,
            font=ctk.CTkFont(size=13),
            text_color="#E0E0E0",
            wraplength=350,
            justify="left",
        )
        label_msg.pack(anchor="w", padx=(12, 0), pady=(0, 2))

        self.after(50, lambda: self._scroll_to_bottom())

    def _scroll_to_bottom(self):
        self.chat_area._parent_canvas.yview_moveto(1.0)

    def enviar_comando(self, texto=None):
        if texto is None:
            texto = self.entry_box.get()
        if not texto or not texto.strip():
            return

        comando = texto.strip()
        self._add_resposta("Você", comando)
        self.entry_box.delete(0, "end")

        if self.thread_ia and self.thread_ia.is_alive():
            self._add_resposta("DarkSON", "Ainda processando o anterior.")
            return

        self.thread_ia = threading.Thread(
            target=self._processar, args=(comando,), daemon=True
        )
        self.thread_ia.start()

    def _processar(self, comando):
        try:
            resposta = self.assistente.executar_comando(comando)
            if resposta:
                self.after(0, self._add_resposta, "DarkSON", resposta)
        except Exception as e:
            self.after(0, self._add_resposta, "DarkSON", f"Erro: {str(e)[:100]}")

    def _iniciar_servidor_flask(self):
        try:
            from ui.web_app import app

            threading.Thread(
                target=lambda: app.run(
                    host="127.0.0.1",
                    port=5000,
                    debug=False,
                    threaded=True,
                    use_reloader=False,
                ),
                daemon=True,
            ).start()
        except Exception:
            pass

    def parar(self):
        self.assistente.parar()


if __name__ == "__main__":
    app = DarksonApp()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        app.parar()
