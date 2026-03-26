"""
rfid_middleware_gui.py — MOOUI
Interface gráfica para o simulador de middleware RFID.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
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

# Códigos de barras RFID: 00392800010000#00001 até #00010
BARCODES = [f"00392800010000#{i:05d}" for i in range(1, 11)]


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
        self.root.title("RFID Middleware Simulator - MOOUI")
        self.root.geometry("700x600")
        self.root.resizable(True, True)

        self.observer = None
        self.event_handler = None
        self.running = False

        self.setup_ui()
        Path(RFID_DIR).mkdir(parents=True, exist_ok=True)

    def setup_ui(self):
        """Configura a interface gráfica."""
        # Frame superior - Configuração
        config_frame = ttk.LabelFrame(self.root, text="Configuração", padding=10)
        config_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(config_frame, text="Diretório RFID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.dir_entry = ttk.Entry(config_frame, width=50)
        self.dir_entry.insert(0, RFID_DIR)
        self.dir_entry.grid(row=0, column=1, padx=5, pady=5)

        # Frame de status
        status_frame = ttk.LabelFrame(self.root, text="Status", padding=10)
        status_frame.pack(fill=tk.X, padx=10, pady=5)

        self.status_label = ttk.Label(status_frame, text="● Parado", foreground="red", font=("Arial", 12, "bold"))
        self.status_label.pack(anchor=tk.W)

        self.portal_status = ttk.Label(status_frame, text="Portal: Fechado", foreground="gray")
        self.portal_status.pack(anchor=tk.W)

        # Frame de controle
        control_frame = ttk.Frame(self.root, padding=10)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        self.start_button = ttk.Button(control_frame, text="Iniciar Middleware", command=self.start_middleware, width=20)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(control_frame, text="Parar Middleware", command=self.stop_middleware, state=tk.DISABLED, width=20)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.clear_button = ttk.Button(control_frame, text="Limpar Logs", command=self.clear_logs, width=15)
        self.clear_button.pack(side=tk.LEFT, padx=5)

        # Frame de tags
        tags_frame = ttk.LabelFrame(self.root, text="Tags RFID Geradas (10)", padding=10)
        tags_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Lista de tags
        tags_text = scrolledtext.ScrolledText(tags_frame, height=8, wrap=tk.WORD, state=tk.DISABLED, font=("Courier New", 9))
        tags_text.pack(fill=tk.BOTH, expand=True)
        self.tags_text = tags_text

        # Preenche tags
        self.show_tags()

        # Frame de logs
        log_frame = ttk.LabelFrame(self.root, text="Logs de Eventos", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def show_tags(self):
        """Mostra as tags RFID na interface."""
        tags = generate_rfid_tags()
        self.tags_text.config(state=tk.NORMAL)
        self.tags_text.delete(1.0, tk.END)
        for i, tag in enumerate(tags, 1):
            barcode = BARCODES[i-1]
            self.tags_text.insert(tk.END, f"{i:2d}. {tag}  ({barcode})\n")
        self.tags_text.config(state=tk.DISABLED)

    def log(self, message, level="INFO"):
        """Adiciona mensagem ao log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {"INFO": "black", "SUCCESS": "green", "WARNING": "orange", "ERROR": "red"}
        color = colors.get(level, "black")

        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
        self.log_text.insert(tk.END, f"{message}\n", level.lower())
        self.log_text.tag_config("timestamp", foreground="gray")
        self.log_text.tag_config("info", foreground=color)
        self.log_text.tag_config("success", foreground=color)
        self.log_text.tag_config("warning", foreground=color)
        self.log_text.tag_config("error", foreground=color)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def clear_logs(self):
        """Limpa o texto dos logs."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

    def limpar_arquivos_txt(self):
        """Remove todos os arquivos .txt do diretório RFID."""
        self.log("Limpando arquivos .txt...", "INFO")
        arquivos = glob.glob(os.path.join(RFID_DIR, "*.txt"))
        for arquivo in arquivos:
            try:
                os.remove(arquivo)
                self.log(f"  Removido: {os.path.basename(arquivo)}", "SUCCESS")
            except Exception as e:
                self.log(f"  Erro ao remover {os.path.basename(arquivo)}: {e}", "ERROR")

    def criar_lista_tags(self):
        """Cria o arquivo ListaTagtxt.txt com as tags RFID."""
        tags = generate_rfid_tags()
        caminho_tags = os.path.join(RFID_DIR, ARQUIVO_TAGS)

        try:
            with open(caminho_tags, "w", encoding="utf-8") as f:
                for tag in tags:
                    f.write(tag + "\n")
            self.log(f"Arquivo {ARQUIVO_TAGS} criado com {len(tags)} tags", "SUCCESS")
            return True
        except Exception as e:
            self.log(f"Erro ao criar {ARQUIVO_TAGS}: {e}", "ERROR")
            return False

    def start_middleware(self):
        """Inicia o middleware."""
        if self.running:
            return

        self.running = True
        self.status_label.config(text="● Rodando", foreground="green")
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)

        self.log("=" * 50, "INFO")
        self.log("RFID Middleware Simulator INICIADO", "SUCCESS")
        self.log(f"Monitorando: {RFID_DIR}", "INFO")
        self.log("=" * 50, "INFO")

        # Limpa arquivos
        self.limpar_arquivos_txt()

        # Inicia observador em thread separada
        def run_observer():
            self.event_handler = RFIDEventHandlerGUI(self)
            self.observer = Observer()
            self.observer.schedule(self.event_handler, RFID_DIR, recursive=False)
            self.observer.start()

            try:
                while self.running:
                    time.sleep(0.5)
            except Exception as e:
                self.log(f"Erro no observador: {e}", "ERROR")

        thread = threading.Thread(target=run_observer, daemon=True)
        thread.start()

    def stop_middleware(self):
        """Para o middleware."""
        if not self.running:
            return

        self.running = False
        self.status_label.config(text="● Parado", foreground="red")
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.portal_status.config(text="Portal: Fechado", foreground="gray")

        if self.observer:
            self.observer.stop()
            self.observer.join()

        self.log("Middleware PARADO", "WARNING")


class RFIDEventHandlerGUI(FileSystemEventHandler):
    """Handler de eventos do filesystem para a GUI."""

    def __init__(self, gui):
        self.gui = gui
        self.ativo = False

    def on_created(self, event):
        if event.is_directory:
            return

        nome_arquivo = os.path.basename(event.src_path)

        if nome_arquivo == ARQUIVO_INICIAR:
            self.gui.log("Portal TOTVS INICIADO", "SUCCESS")
            self.gui.portal_status.config(text="Portal: Aberto", foreground="green")
            if not self.ativo:
                self.ativo = True
                self.gui.criar_lista_tags()
            else:
                self.gui.log("  Middleware já estava ativo", "WARNING")

        elif nome_arquivo == ARQUIVO_PARAR:
            self.gui.log("Portal TOTVS PARADO", "WARNING")
            self.gui.portal_status.config(text="Portal: Fechado", foreground="gray")
            if self.ativo:
                self.ativo = False
                self.gui.log(f"  Middleware desativado (arquivo {ARQUIVO_TAGS} mantido)", "INFO")
            else:
                self.gui.log("  Middleware já estava inativo", "WARNING")


def main():
    root = tk.Tk()
    app = RFIDMiddlewareGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
