"""
rfid_middleware_gui.py — MOOUI
Interface gráfica DARK para o simulador de middleware RFID.
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

# Tema Dark Industrial
COLORS = {
    'bg': '#1a1a1a',           # Preto escuro
    'fg': '#00ff00',           # Verde terminal
    'panel': '#2b2b2b',        # Cinza escuro
    'button_bg': '#3a3a3a',    # Cinza médio
    'button_active': '#4a4a4a',# Cinza claro
    'status_on': '#00ff00',    # Verde neon
    'status_off': '#ff0000',   # Vermelho
    'warning': '#ffaa00',      # Laranja
    'info': '#00aaff',         # Azul
    'border': '#00ff00',       # Verde neon
}


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


class IndustrialButton(tk.Canvas):
    """Botão customizado estilo industrial."""

    def __init__(self, parent, text, command, width=200, height=50, **kwargs):
        super().__init__(parent, width=width, height=height, bg=COLORS['bg'],
                        highlightthickness=2, highlightbackground=COLORS['border'])
        self.command = command
        self.text = text
        self.enabled = True

        # Desenha o botão
        self.rect = self.create_rectangle(2, 2, width-2, height-2,
                                          fill=COLORS['button_bg'],
                                          outline=COLORS['border'], width=2)
        self.text_id = self.create_text(width//2, height//2,
                                        text=text, fill=COLORS['fg'],
                                        font=('Consolas', 11, 'bold'))

        # Eventos
        self.bind("<Button-1>", self.on_click)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def on_click(self, event):
        if self.enabled and self.command:
            self.command()

    def on_enter(self, event):
        if self.enabled:
            self.itemconfig(self.rect, fill=COLORS['button_active'])

    def on_leave(self, event):
        if self.enabled:
            self.itemconfig(self.rect, fill=COLORS['button_bg'])

    def set_enabled(self, enabled):
        self.enabled = enabled
        if enabled:
            self.itemconfig(self.text_id, fill=COLORS['fg'])
            self.itemconfig(self.rect, outline=COLORS['border'])
        else:
            self.itemconfig(self.text_id, fill='#555555')
            self.itemconfig(self.rect, outline='#555555')


class RFIDMiddlewareGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("RFID MIDDLEWARE SIMULATOR - MOOUI")
        self.root.geometry("900x700")
        self.root.configure(bg=COLORS['bg'])

        self.observer = None
        self.running = False
        self.portal_aberto = False

        self.setup_ui()
        Path(RFID_DIR).mkdir(parents=True, exist_ok=True)

    def setup_ui(self):
        """Configura a interface dark industrial."""

        # Header
        header = tk.Frame(self.root, bg=COLORS['panel'], height=80)
        header.pack(fill=tk.X, padx=0, pady=0)

        title = tk.Label(header, text="█ RFID MIDDLEWARE SIMULATOR █",
                        bg=COLORS['panel'], fg=COLORS['status_on'],
                        font=('Consolas', 18, 'bold'))
        title.pack(pady=10)

        subtitle = tk.Label(header, text="MOOUI INDUSTRIAL SYSTEMS",
                           bg=COLORS['panel'], fg=COLORS['fg'],
                           font=('Consolas', 9))
        subtitle.pack()

        # Status Panel
        status_frame = tk.Frame(self.root, bg=COLORS['bg'])
        status_frame.pack(fill=tk.X, padx=20, pady=15)

        # Middleware Status
        middleware_panel = tk.Frame(status_frame, bg=COLORS['panel'],
                                   highlightthickness=2,
                                   highlightbackground=COLORS['border'])
        middleware_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        tk.Label(middleware_panel, text="MIDDLEWARE STATUS",
                bg=COLORS['panel'], fg=COLORS['fg'],
                font=('Consolas', 10, 'bold')).pack(pady=5)

        self.middleware_status = tk.Label(middleware_panel, text="● OFFLINE",
                                         bg=COLORS['panel'],
                                         fg=COLORS['status_off'],
                                         font=('Consolas', 16, 'bold'))
        self.middleware_status.pack(pady=10)

        # Portal Status
        portal_panel = tk.Frame(status_frame, bg=COLORS['panel'],
                               highlightthickness=2,
                               highlightbackground=COLORS['border'])
        portal_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        tk.Label(portal_panel, text="PORTAL TOTVS",
                bg=COLORS['panel'], fg=COLORS['fg'],
                font=('Consolas', 10, 'bold')).pack(pady=5)

        self.portal_status = tk.Label(portal_panel, text="● FECHADO",
                                      bg=COLORS['panel'],
                                      fg='#666666',
                                      font=('Consolas', 16, 'bold'))
        self.portal_status.pack(pady=10)

        # Controls
        controls_frame = tk.Frame(self.root, bg=COLORS['bg'])
        controls_frame.pack(fill=tk.X, padx=20, pady=10)

        self.btn_start = IndustrialButton(controls_frame, "START MIDDLEWARE",
                                         self.start_middleware, width=200, height=50)
        self.btn_start.pack(side=tk.LEFT, padx=10)

        self.btn_stop = IndustrialButton(controls_frame, "STOP MIDDLEWARE",
                                        self.stop_middleware, width=200, height=50)
        self.btn_stop.pack(side=tk.LEFT, padx=10)
        self.btn_stop.set_enabled(False)

        self.btn_clear = IndustrialButton(controls_frame, "CLEAR LOGS",
                                         self.clear_logs, width=150, height=50)
        self.btn_clear.pack(side=tk.LEFT, padx=10)

        # Tags Panel
        tags_frame = tk.Frame(self.root, bg=COLORS['panel'],
                             highlightthickness=2,
                             highlightbackground=COLORS['border'])
        tags_frame.pack(fill=tk.BOTH, expand=False, padx=20, pady=10)

        tk.Label(tags_frame, text="TAGS RFID GERADAS (10x SGTIN-96)",
                bg=COLORS['panel'], fg=COLORS['fg'],
                font=('Consolas', 10, 'bold')).pack(pady=5, anchor=tk.W, padx=10)

        self.tags_text = scrolledtext.ScrolledText(
            tags_frame, height=6, wrap=tk.WORD,
            bg='#0a0a0a', fg=COLORS['status_on'],
            font=('Consolas', 9), insertbackground=COLORS['fg'],
            highlightthickness=0, borderwidth=0
        )
        self.tags_text.pack(fill=tk.BOTH, expand=False, padx=10, pady=5)
        self.show_tags()

        # Log Panel
        log_frame = tk.Frame(self.root, bg=COLORS['panel'],
                            highlightthickness=2,
                            highlightbackground=COLORS['border'])
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        tk.Label(log_frame, text="SYSTEM LOGS",
                bg=COLORS['panel'], fg=COLORS['fg'],
                font=('Consolas', 10, 'bold')).pack(pady=5, anchor=tk.W, padx=10)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD,
            bg='#0a0a0a', fg=COLORS['fg'],
            font=('Consolas', 9), insertbackground=COLORS['fg'],
            highlightthickness=0, borderwidth=0
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Footer
        footer = tk.Frame(self.root, bg=COLORS['panel'], height=30)
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        tk.Label(footer, text=f"Monitoring: {RFID_DIR}",
                bg=COLORS['panel'], fg=COLORS['fg'],
                font=('Consolas', 8)).pack(side=tk.LEFT, padx=10)

    def show_tags(self):
        """Mostra as tags RFID."""
        tags = generate_rfid_tags()
        self.tags_text.config(state=tk.NORMAL)
        self.tags_text.delete(1.0, tk.END)
        for i, tag in enumerate(tags, 1):
            barcode = BARCODES[i-1]
            self.tags_text.insert(tk.END, f"{i:02d} | {tag} | {barcode}\n")
        self.tags_text.config(state=tk.DISABLED)

    def log(self, message, level="INFO"):
        """Adiciona mensagem ao log com cores."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        colors = {
            "INFO": COLORS['info'],
            "SUCCESS": COLORS['status_on'],
            "WARNING": COLORS['warning'],
            "ERROR": COLORS['status_off']
        }
        color = colors.get(level, COLORS['fg'])

        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
        self.log_text.insert(tk.END, f"{message}\n", level.lower())

        self.log_text.tag_config("timestamp", foreground='#666666')
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
                self.log(f"  Removed: {os.path.basename(arquivo)}", "SUCCESS")
            except Exception as e:
                self.log(f"  Error removing {os.path.basename(arquivo)}: {e}", "ERROR")

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
        self.middleware_status.config(text="● ONLINE", fg=COLORS['status_on'])
        self.btn_start.set_enabled(False)
        self.btn_stop.set_enabled(True)

        self.log("="*60, "INFO")
        self.log("MIDDLEWARE STARTED", "SUCCESS")
        self.log(f"Monitoring: {RFID_DIR}", "INFO")
        self.log("="*60, "INFO")

        # Limpa arquivos
        self.limpar_arquivos_txt()

        # Inicia watchdog
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
        self.middleware_status.config(text="● OFFLINE", fg=COLORS['status_off'])
        self.portal_status.config(text="● FECHADO", fg='#666666')
        self.portal_aberto = False
        self.btn_start.set_enabled(True)
        self.btn_stop.set_enabled(False)

        if self.observer:
            self.observer.stop()
            self.observer.join()

        self.log("MIDDLEWARE STOPPED", "WARNING")


class RFIDEventHandlerGUI(FileSystemEventHandler):
    """Handler de eventos do filesystem."""

    def __init__(self, gui):
        self.gui = gui

    def on_created(self, event):
        if event.is_directory:
            return

        nome = os.path.basename(event.src_path)

        if nome == ARQUIVO_INICIAR:
            self.gui.log(">>> PORTAL OPENED (RFIDIniciar.txt detected)", "SUCCESS")
            self.gui.portal_status.config(text="● ABERTO", fg=COLORS['status_on'])
            self.gui.portal_aberto = True

            # Cria arquivo de tags
            time.sleep(0.1)  # Pequeno delay para garantir que o arquivo foi criado
            self.gui.criar_lista_tags()

        elif nome == ARQUIVO_PARAR:
            self.gui.log(">>> PORTAL CLOSED (RFIDParar.txt detected)", "WARNING")
            self.gui.portal_status.config(text="● FECHADO", fg=COLORS['status_off'])
            self.gui.portal_aberto = False
            self.gui.log(f"  {ARQUIVO_TAGS} kept in directory", "INFO")


def main():
    root = tk.Tk()
    app = RFIDMiddlewareGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
