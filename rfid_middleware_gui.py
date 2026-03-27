"""
rfid_middleware_gui.py — MOOUI
Interface gráfica minimalista para o simulador de middleware RFID.
"""

import tkinter as tk
from tkinter import scrolledtext
import os
import time
import threading
import glob
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configuração
RFID_DIR = r"C:\RFID"
ARQUIVO_INICIAR = "RFIDIniciar.txt"
ARQUIVO_PARAR = "RFIDParar.txt"
ARQUIVO_TAGS = "ListaTagtxt.txt"

# Códigos de barras RFID
BARCODES = [f"00392800010000#{i:05d}" for i in range(1, 11)]

# Tema (baseado no rfid_terminal.py)
BG    = "#0d0d0d"
BG2   = "#111111"
BRD   = "#2a2a2a"
CYAN  = "#00e5ff"
GREEN = "#00ff88"
RED   = "#ff4444"
YEL   = "#ffcc00"
GRAY  = "#444444"
LGRAY = "#888888"
WHITE = "#e0e0e0"
F     = "Courier New"


def ean13_to_sgtin96(ean13_no_check: str, serial: int) -> str:
    """Converte EAN-13 + serial para EPC SGTIN-96 (hex)."""
    header = 0x30
    filter_value = 1
    partition = 6
    filter_partition = (filter_value << 3) | partition
    company_prefix = int(ean13_no_check[:7])
    item_ref = int(ean13_no_check[7:])
    serial_number = serial & 0x3FFFFFFFFF
    sgtin = (header << 88) | (filter_partition << 82) | (company_prefix << 52) | (item_ref << 38) | serial_number
    return f"{sgtin:024X}"


def generate_rfid_tags() -> list:
    """Gera lista de 10 EPCs SGTIN-96."""
    tags = []
    for barcode in BARCODES:
        ean_part, serial_part = barcode.split("#")
        serial = int(serial_part)
        epc = ean13_to_sgtin96(ean_part, serial)
        tags.append(epc)
    return tags


class RFIDMiddlewareGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("RFID Middleware Simulator")
        self.root.configure(bg=BG)
        self.root.resizable(False, True)

        self.observer = None
        self.running = False
        self.portal_aberto = False

        self.var_middleware = tk.StringVar(value="Offline")
        self.var_portal = tk.StringVar(value="Fechado")

        self._build()
        Path(RFID_DIR).mkdir(parents=True, exist_ok=True)

        # Centraliza janela
        self.root.update()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _div(self, p):
        """Cria divisor horizontal."""
        tk.Frame(p, bg=BRD, height=1).pack(fill="x", pady=3)

    def _lbl(self, p, t, fg=LGRAY, size=8):
        """Label de seção."""
        tk.Label(p, text=t, font=(F, size), bg=BG2, fg=fg).pack(anchor="w")

    def _row(self, p, label, var, color=CYAN):
        """Linha de informação com tree-like prefix."""
        r = tk.Frame(p, bg=BG2)
        r.pack(anchor="w", pady=1)
        tk.Label(r, text="├─ ", font=(F, 9), bg=BG2, fg=GRAY).pack(side="left")
        tk.Label(r, text=label, font=(F, 9), bg=BG2, fg=LGRAY).pack(side="left")
        tk.Label(r, textvariable=var, font=(F, 9, "bold"), bg=BG2, fg=color).pack(side="left")

    def _build(self):
        """Constrói a interface."""
        outer = tk.Frame(self.root, bg=BRD, padx=1, pady=1)
        outer.pack(padx=10, pady=10, fill="both", expand=True)
        m = tk.Frame(outer, bg=BG2, padx=18, pady=14)
        m.pack(fill="both", expand=True)

        # Header
        tk.Label(m, text="RFID Middleware Simulator",
                font=(F, 11, "bold"), bg=BG2, fg=WHITE).pack(pady=(0, 12))
        self._div(m)

        # Status Middleware
        r1 = tk.Frame(m, bg=BG2)
        r1.pack(fill="x", pady=2)
        tk.Label(r1, text="Middleware:", font=(F, 9), bg=BG2, fg=LGRAY,
                width=12, anchor="w").pack(side="left")
        self.dot_middleware = tk.Label(r1, text="● ", font=(F, 9), bg=BG2, fg=RED)
        self.dot_middleware.pack(side="left")
        self.lbl_middleware = tk.Label(r1, textvariable=self.var_middleware,
                                      font=(F, 9), bg=BG2, fg=RED, anchor="w")
        self.lbl_middleware.pack(side="left")

        # Status Portal
        r2 = tk.Frame(m, bg=BG2)
        r2.pack(fill="x", pady=2)
        tk.Label(r2, text="Portal:", font=(F, 9), bg=BG2, fg=LGRAY,
                width=12, anchor="w").pack(side="left")
        self.dot_portal = tk.Label(r2, text="● ", font=(F, 9), bg=BG2, fg=GRAY)
        self.dot_portal.pack(side="left")
        self.lbl_portal = tk.Label(r2, textvariable=self.var_portal,
                                   font=(F, 9), bg=BG2, fg=GRAY, anchor="w")
        self.lbl_portal.pack(side="left")

        tk.Frame(m, bg=BG2, height=8).pack()
        self._div(m)

        # Controles
        br = tk.Frame(m, bg=BG2)
        br.pack(fill="x", pady=8)

        self.btn_start = tk.Label(br, text="[INICIAR]",
                                 font=(F, 9, "bold"), bg=BG2, fg=GREEN, cursor="hand2")
        self.btn_start.pack(side="left", padx=(0, 8))
        self.btn_start.bind("<Button-1>", lambda e: self.start_middleware())
        self.btn_start.bind("<Enter>", lambda e: self.btn_start.config(fg=WHITE))
        self.btn_start.bind("<Leave>", lambda e: self.btn_start.config(
            fg=GREEN if not self.running else GRAY))

        self.btn_stop = tk.Label(br, text="[PARAR]",
                                font=(F, 9, "bold"), bg=BG2, fg=GRAY, cursor="hand2")
        self.btn_stop.pack(side="left", padx=(0, 8))
        self.btn_stop.bind("<Button-1>", lambda e: self.stop_middleware())
        self.btn_stop.bind("<Enter>", lambda e: self.btn_stop.config(
            fg=WHITE if self.running else GRAY))
        self.btn_stop.bind("<Leave>", lambda e: self.btn_stop.config(
            fg=RED if self.running else GRAY))

        self.btn_clear = tk.Label(br, text="[LIMPAR]",
                                 font=(F, 9), bg=BG2, fg=CYAN, cursor="hand2")
        self.btn_clear.pack(side="left")
        self.btn_clear.bind("<Button-1>", lambda e: self.clear_logs())
        self.btn_clear.bind("<Enter>", lambda e: self.btn_clear.config(fg=WHITE))
        self.btn_clear.bind("<Leave>", lambda e: self.btn_clear.config(fg=CYAN))

        self._div(m)

        # Tags RFID
        self._lbl(m, "Tags RFID (10x SGTIN-96):")
        self.tags_text = scrolledtext.ScrolledText(
            m, height=7, wrap=tk.NONE, font=(F, 8),
            bg="#0a0a0a", fg=GREEN, insertbackground=CYAN,
            relief="flat", bd=0, padx=8, pady=6
        )
        self.tags_text.pack(fill="x", pady=(4, 8))
        self.show_tags()

        self._div(m)

        # Logs
        self._lbl(m, "Logs do sistema:")
        self.log_text = scrolledtext.ScrolledText(
            m, height=12, wrap=tk.WORD, font=(F, 8),
            bg="#0a0a0a", fg=LGRAY, insertbackground=CYAN,
            relief="flat", bd=0, padx=8, pady=6
        )
        self.log_text.pack(fill="both", expand=True, pady=(4, 0))

        # Footer
        tk.Frame(m, bg=BG2, height=4).pack()
        self._div(m)
        tk.Label(m, text=f"Monitoring: {RFID_DIR}",
                font=(F, 7), bg=BG2, fg=GRAY).pack(anchor="w")

    def show_tags(self):
        """Mostra as tags RFID."""
        tags = generate_rfid_tags()
        self.tags_text.config(state=tk.NORMAL)
        self.tags_text.delete(1.0, tk.END)
        for i, tag in enumerate(tags, 1):
            barcode = BARCODES[i-1]
            self.tags_text.insert(tk.END, f"{i:02d} │ {tag} │ {barcode}\n")
        self.tags_text.config(state=tk.DISABLED)

    def log(self, message, level="INFO"):
        """Adiciona mensagem ao log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {
            "INFO": CYAN,
            "SUCCESS": GREEN,
            "WARNING": YEL,
            "ERROR": RED
        }
        color = colors.get(level, LGRAY)

        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
        self.log_text.insert(tk.END, f"{message}\n", level.lower())
        self.log_text.tag_config("timestamp", foreground=GRAY)
        self.log_text.tag_config(level.lower(), foreground=color)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def clear_logs(self):
        """Limpa os logs."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.log("Logs cleared", "INFO")

    def limpar_arquivos_txt(self):
        """Remove todos os .txt do diretório RFID."""
        self.log("Cleaning .txt files...", "INFO")
        arquivos = glob.glob(os.path.join(RFID_DIR, "*.txt"))
        for arquivo in arquivos:
            try:
                os.remove(arquivo)
                self.log(f"├─ Removed: {os.path.basename(arquivo)}", "SUCCESS")
            except Exception as e:
                self.log(f"├─ Error: {os.path.basename(arquivo)} - {e}", "ERROR")

    def criar_lista_tags(self):
        """Cria ListaTagtxt.txt com as tags."""
        tags = generate_rfid_tags()
        caminho = os.path.join(RFID_DIR, ARQUIVO_TAGS)

        try:
            with open(caminho, "w", encoding="utf-8") as f:
                for tag in tags:
                    f.write(tag + "\n")
            self.log(f"Created {ARQUIVO_TAGS} with {len(tags)} tags", "SUCCESS")
            return True
        except Exception as e:
            self.log(f"Error creating {ARQUIVO_TAGS}: {e}", "ERROR")
            return False

    def start_middleware(self):
        """Inicia o middleware."""
        if self.running:
            return

        self.running = True
        self.var_middleware.set("Online")
        self.dot_middleware.config(fg=GREEN)
        self.lbl_middleware.config(fg=GREEN)
        self.btn_start.config(fg=GRAY)
        self.btn_stop.config(fg=RED)

        self.log("=" * 50, "INFO")
        self.log("Middleware started", "SUCCESS")
        self.log(f"Monitoring: {RFID_DIR}", "INFO")
        self.log("=" * 50, "INFO")

        self.limpar_arquivos_txt()

        def run_observer():
            self.observer = Observer()
            handler = RFIDEventHandlerGUI(self)
            self.observer.schedule(handler, RFID_DIR, recursive=False)
            self.observer.start()

            try:
                while self.running:
                    time.sleep(0.1)
            except Exception as e:
                self.log(f"Observer error: {e}", "ERROR")

        thread = threading.Thread(target=run_observer, daemon=True)
        thread.start()

    def stop_middleware(self):
        """Para o middleware."""
        if not self.running:
            return

        self.running = False
        self.var_middleware.set("Offline")
        self.dot_middleware.config(fg=RED)
        self.lbl_middleware.config(fg=RED)
        self.var_portal.set("Fechado")
        self.dot_portal.config(fg=GRAY)
        self.lbl_portal.config(fg=GRAY)
        self.portal_aberto = False
        self.btn_start.config(fg=GREEN)
        self.btn_stop.config(fg=GRAY)

        if self.observer:
            self.observer.stop()
            self.observer.join()

        self.log("Middleware stopped", "WARNING")


class RFIDEventHandlerGUI(FileSystemEventHandler):
    """Handler de eventos do filesystem."""

    def __init__(self, gui):
        self.gui = gui

    def on_created(self, event):
        if event.is_directory:
            return

        nome = os.path.basename(event.src_path)

        if nome == ARQUIVO_INICIAR:
            self.gui.log(">>> Portal opened (RFIDIniciar.txt detected)", "SUCCESS")
            self.gui.var_portal.set("Aberto")
            self.gui.dot_portal.config(fg=GREEN)
            self.gui.lbl_portal.config(fg=GREEN)
            self.gui.portal_aberto = True

            time.sleep(0.1)
            self.gui.criar_lista_tags()

        elif nome == ARQUIVO_PARAR:
            self.gui.log(">>> Portal closed (RFIDParar.txt detected)", "WARNING")
            self.gui.var_portal.set("Fechado")
            self.gui.dot_portal.config(fg=RED)
            self.gui.lbl_portal.config(fg=RED)
            self.gui.portal_aberto = False
            self.gui.log(f"├─ {ARQUIVO_TAGS} kept in directory", "INFO")


def main():
    root = tk.Tk()
    app = RFIDMiddlewareGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
