"""
rfid_middleware_gui.py — MOOUI
Middleware RFID com interface gráfica.
Integração real via LLRP (sllurp) com leitor Zebra FX7500.

pip install watchdog sllurp
"""

import glob
import os
import queue
import struct
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import scrolledtext, simpledialog, messagebox

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# ── Tentativa de importar sllurp ──────────────────────────────────────────────
try:
    from sllurp import llrp
    from sllurp.llrp import LLRPReaderConfig, LLRPReaderClient
    SLLURP_DISPONIVEL = True
except ImportError:
    SLLURP_DISPONIVEL = False

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

RFID_DIR        = r"C:\RFID"
ARQUIVO_INICIAR = "RFIDIniciar.txt"
ARQUIVO_PARAR   = "RFIDParar.txt"
ARQUIVO_TAGS    = "ListaTagtxt.txt"
TAGS_TEMPLATE   = "data/tags_template.txt"

# Leitor RFID
LEITOR_IP       = "127.0.0.1"       # ← localhost para simulador | IP real do FX7500 em produção
LEITOR_PORTA    = 5084              # Porta LLRP padrão
LEITURA_TIMEOUT = 5.0               # Segundos de leitura após RFIDIniciar.txt
POTENCIA_TX     = 3100              # mDBm (31 dBm — ajustar conforme ambiente)

# ── Tema visual ───────────────────────────────────────────────────────────────
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

# ============================================================================
# LLRP — LEITURA REAL
# ============================================================================

class LeitorRFID:
    """
    Abstração do leitor RFID via LLRP (sllurp).
    Suporta modo real (FX7500) e modo simulação (tags_template.txt).
    """

    def __init__(self, ip: str, porta: int = 5084, timeout: float = 5.0,
                 potencia: int = 3100, log_fn=None):
        self.ip       = ip
        self.porta    = porta
        self.timeout  = timeout
        self.potencia = potencia
        self._log     = log_fn or print
        self._epcs    = []
        self._lock    = threading.Lock()

    def _tag_callback(self, reader, tag_reports):
        """Callback chamado pelo sllurp a cada leitura de tag."""
        with self._lock:
            for report in tag_reports:
                for tag in report.get('TagReportData', []):
                    epc_raw = tag.get('EPCData', {}).get('EPC', b'')
                    if isinstance(epc_raw, bytes):
                        epc_hex = epc_raw.hex().upper()
                    else:
                        epc_hex = str(epc_raw).upper()
                    if epc_hex and epc_hex not in self._epcs:
                        self._epcs.append(epc_hex)

    def ler(self) -> list:
        """
        Conecta no leitor, lê por self.timeout segundos e retorna lista de EPCs.
        Retorna lista vazia em caso de erro.
        """
        if not SLLURP_DISPONIVEL:
            self._log("sllurp não instalado — usando modo simulação", "WARNING")
            return self._ler_simulado()

        self._epcs = []
        self._log(f"Conectando ao leitor {self.ip}:{self.porta}...", "INFO")

        try:
            config = LLRPReaderConfig({
                'antennas':          [1, 2, 3, 4],
                'tx_power':          self.potencia,
                'mode_identifier':   0,
                'session':           2,
                'tag_population':    4,
                'duration':          self.timeout,
                'tag_content_selector': {
                    'EnableROSpecID':        False,
                    'EnableSpecIndex':       False,
                    'EnableInventoryParamSpecID': False,
                    'EnableAntennaID':       True,
                    'EnableChannelIndex':    False,
                    'EnablePeakRSSI':        True,
                    'EnableFirstSeenTimestamp': True,
                    'EnableLastSeenTimestamp': True,
                    'EnableTagSeenCount':    True,
                    'EnableAccessSpecID':    False,
                }
            })

            reader = LLRPReaderClient(self.ip, self.porta, config)
            reader.add_tag_report_callback(self._tag_callback)

            self._log(f"├─ Iniciando leitura por {self.timeout}s...", "INFO")
            reader.connect()
            time.sleep(self.timeout + 0.5)
            reader.disconnect()

            epcs = list(self._epcs)
            self._log(f"├─ {len(epcs)} tags lidas", "SUCCESS")
            return epcs

        except ConnectionRefusedError:
            self._log(f"├─ Leitor não acessível em {self.ip}:{self.porta}", "ERROR")
            self._log("├─ Verifique IP e conexão de rede", "ERROR")
            return []
        except (struct.error, Exception) as e:
            # Erro de decodificação LLRP ou outro erro genérico
            error_type = type(e).__name__
            self._log(f"├─ Erro LLRP ({error_type}): {e}", "ERROR")
            self._log("├─ Problema de compatibilidade com simulador", "WARNING")
            self._log("├─ Usando modo simulação como fallback...", "WARNING")
            return self._ler_simulado()

    def _ler_simulado(self) -> list:
        """Lê tags do arquivo template (modo simulação)."""
        script_dir    = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(script_dir, TAGS_TEMPLATE)
        tags = []
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                for line in f:
                    tag = line.strip()
                    if tag:
                        tags.append(tag)
            self._log(f"├─ Simulação: {len(tags)} tags do template", "WARNING")
        except FileNotFoundError:
            self._log(f"├─ Template não encontrado: {template_path}", "ERROR")
        return tags

    def testar_conexao(self) -> bool:
        """Testa se o leitor está acessível."""
        if not SLLURP_DISPONIVEL:
            return False
        import socket
        try:
            s = socket.create_connection((self.ip, self.porta), timeout=3)
            s.close()
            return True
        except Exception:
            return False

# ============================================================================
# INTERFACE GRÁFICA
# ============================================================================

class RFIDMiddlewareGUI:

    def __init__(self, root):
        self.root = root
        self.root.title("RFID Middleware — MOOUI")
        self.root.configure(bg=BG)
        self.root.resizable(False, True)

        self.observer      = None
        self.running       = False
        self.portal_aberto = False
        # FORÇA modo simulação por padrão (simulador Zebra tem problemas LLRP)
        self.modo_simulacao = True

        # IP configurável em runtime
        self.leitor_ip = LEITOR_IP

        # Armazena última leitura para gravar quando portal fechar
        self.ultima_leitura_epcs = []

        self.var_middleware = tk.StringVar(value="Offline")
        self.var_portal     = tk.StringVar(value="Fechado")
        self.var_modo       = tk.StringVar(
            value="SIMULAÇÃO" if self.modo_simulacao else "REAL"
        )
        self.var_leitor_ip  = tk.StringVar(value=self.leitor_ip)
        self.var_tags_count = tk.StringVar(value="0 tags")

        # Fila para logs thread-safe
        self._log_queue = queue.Queue()

        self._build()
        self._processar_log_queue()
        Path(RFID_DIR).mkdir(parents=True, exist_ok=True)

        # Centraliza janela
        self.root.update()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        x = (self.root.winfo_screenwidth()  - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ── Helpers de layout ────────────────────────────────────────────────────

    def _div(self, p):
        tk.Frame(p, bg=BRD, height=1).pack(fill="x", pady=3)

    def _lbl(self, p, t, fg=LGRAY, size=8):
        tk.Label(p, text=t, font=(F, size), bg=BG2, fg=fg).pack(anchor="w")

    def _row(self, p, label, var, color=CYAN):
        r = tk.Frame(p, bg=BG2)
        r.pack(anchor="w", pady=1)
        tk.Label(r, text="├─ ", font=(F, 9), bg=BG2, fg=GRAY).pack(side="left")
        tk.Label(r, text=label, font=(F, 9), bg=BG2, fg=LGRAY).pack(side="left")
        tk.Label(r, textvariable=var, font=(F, 9, "bold"), bg=BG2, fg=color).pack(side="left")

    def _btn(self, parent, texto, fg, comando):
        b = tk.Label(parent, text=texto, font=(F, 9, "bold"), bg=BG2, fg=fg, cursor="hand2")
        b.pack(side="left", padx=(0, 8))
        b.bind("<Button-1>", lambda e: comando())
        b.bind("<Enter>",    lambda e: b.config(fg=WHITE))
        b.bind("<Leave>",    lambda e: b.config(fg=fg))
        return b

    # ── Build da interface ────────────────────────────────────────────────────

    def _build(self):
        outer = tk.Frame(self.root, bg=BRD, padx=1, pady=1)
        outer.pack(padx=10, pady=10, fill="both", expand=True)
        m = tk.Frame(outer, bg=BG2, padx=18, pady=14)
        m.pack(fill="both", expand=True)

        # Header
        tk.Label(m, text="RFID Middleware — MOOUI",
                 font=(F, 11, "bold"), bg=BG2, fg=WHITE).pack(pady=(0, 4))

        # Modo (real ou simulação)
        self.lbl_modo = tk.Label(m, textvariable=self.var_modo,
                                 font=(F, 8), bg=BG2,
                                 fg=YEL if self.modo_simulacao else GREEN)
        self.lbl_modo.pack()

        self._div(m)

        # Status middleware
        r1 = tk.Frame(m, bg=BG2); r1.pack(fill="x", pady=2)
        tk.Label(r1, text="Middleware:", font=(F, 9), bg=BG2, fg=LGRAY,
                 width=14, anchor="w").pack(side="left")
        self.dot_middleware = tk.Label(r1, text="● ", font=(F, 9), bg=BG2, fg=RED)
        self.dot_middleware.pack(side="left")
        self.lbl_middleware = tk.Label(r1, textvariable=self.var_middleware,
                                       font=(F, 9), bg=BG2, fg=RED, anchor="w")
        self.lbl_middleware.pack(side="left")

        # Status portal
        r2 = tk.Frame(m, bg=BG2); r2.pack(fill="x", pady=2)
        tk.Label(r2, text="Portal:", font=(F, 9), bg=BG2, fg=LGRAY,
                 width=14, anchor="w").pack(side="left")
        self.dot_portal = tk.Label(r2, text="● ", font=(F, 9), bg=BG2, fg=GRAY)
        self.dot_portal.pack(side="left")
        self.lbl_portal = tk.Label(r2, textvariable=self.var_portal,
                                   font=(F, 9), bg=BG2, fg=GRAY, anchor="w")
        self.lbl_portal.pack(side="left")

        # IP do leitor
        r3 = tk.Frame(m, bg=BG2); r3.pack(fill="x", pady=2)
        tk.Label(r3, text="Leitor IP:", font=(F, 9), bg=BG2, fg=LGRAY,
                 width=14, anchor="w").pack(side="left")
        self.lbl_ip = tk.Label(r3, textvariable=self.var_leitor_ip,
                               font=(F, 9), bg=BG2, fg=CYAN, anchor="w", cursor="hand2")
        self.lbl_ip.pack(side="left")
        self.lbl_ip.bind("<Button-1>", lambda e: self._configurar_ip())

        # Tags count
        r4 = tk.Frame(m, bg=BG2); r4.pack(fill="x", pady=2)
        tk.Label(r4, text="Última leitura:", font=(F, 9), bg=BG2, fg=LGRAY,
                 width=14, anchor="w").pack(side="left")
        tk.Label(r4, textvariable=self.var_tags_count,
                 font=(F, 9, "bold"), bg=BG2, fg=GREEN, anchor="w").pack(side="left")

        tk.Frame(m, bg=BG2, height=6).pack()
        self._div(m)

        # Botões
        br = tk.Frame(m, bg=BG2); br.pack(fill="x", pady=8)
        self.btn_start  = self._btn(br, "[INICIAR]",  GREEN, self.start_middleware)
        self.btn_stop   = self._btn(br, "[PARAR]",    GRAY,  self.stop_middleware)
        self.btn_clear  = self._btn(br, "[LIMPAR]",   CYAN,  self.clear_logs)
        self.btn_test   = self._btn(br, "[TESTAR]",   YEL,   self.test_flow)
        self.btn_ping   = self._btn(br, "[PING]",     LGRAY, self.ping_leitor)

        # Segunda linha de botões
        br2 = tk.Frame(m, bg=BG2); br2.pack(fill="x", pady=(0, 8))
        modo_inicial = "SIMULAÇÃO" if self.modo_simulacao else "REAL"
        cor_inicial = YEL if self.modo_simulacao else GREEN
        self.btn_toggle_modo = self._btn(br2, f"[MODO: {modo_inicial}]", cor_inicial, self.toggle_modo_simulacao)

        self._div(m)

        # Tags
        self._lbl(m, "Última leitura — EPCs:")
        self.tags_text = scrolledtext.ScrolledText(
            m, height=7, wrap=tk.NONE, font=(F, 8),
            bg="#0a0a0a", fg=GREEN, insertbackground=CYAN,
            relief="flat", bd=0, padx=8, pady=6
        )
        self.tags_text.pack(fill="x", pady=(4, 8))
        self.tags_text.config(state=tk.DISABLED)

        self._div(m)

        # Logs
        self._lbl(m, "Logs do sistema:")
        self.log_text = scrolledtext.ScrolledText(
            m, height=14, wrap=tk.WORD, font=(F, 8),
            bg="#0a0a0a", fg=LGRAY, insertbackground=CYAN,
            relief="flat", bd=0, padx=8, pady=6
        )
        self.log_text.pack(fill="both", expand=True, pady=(4, 0))

        for level, color in [("timestamp", GRAY), ("info", CYAN),
                              ("success", GREEN), ("warning", YEL), ("error", RED)]:
            self.log_text.tag_config(level, foreground=color)

        # Footer
        tk.Frame(m, bg=BG2, height=4).pack()
        self._div(m)
        tk.Label(m, text=f"Monitorando: {RFID_DIR}  |  LLRP porta {LEITOR_PORTA}",
                 font=(F, 7), bg=BG2, fg=GRAY).pack(anchor="w")

    # ── Log thread-safe ───────────────────────────────────────────────────────

    def log(self, message, level="INFO"):
        """Enfileira mensagem de log (thread-safe)."""
        self._log_queue.put((message, level))

    def _processar_log_queue(self):
        """Processa fila de logs na thread principal (tkinter)."""
        try:
            while True:
                message, level = self._log_queue.get_nowait()
                self._escrever_log(message, level)
        except queue.Empty:
            pass
        self.root.after(50, self._processar_log_queue)

    def _escrever_log(self, message, level="INFO"):
        colors = {"INFO": CYAN, "SUCCESS": GREEN, "WARNING": YEL, "ERROR": RED}
        color  = colors.get(level, LGRAY)
        ts     = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{ts}] ", "timestamp")
        self.log_text.insert(tk.END, f"{message}\n", level.lower())
        self.log_text.tag_config(level.lower(), foreground=color)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _atualizar_tags_display(self, epcs: list):
        """Atualiza painel de tags lidas."""
        self.tags_text.config(state=tk.NORMAL)
        self.tags_text.delete(1.0, tk.END)
        for i, epc in enumerate(epcs, 1):
            self.tags_text.insert(tk.END, f"{i:03d} │ {epc}\n")
        self.tags_text.config(state=tk.DISABLED)
        self.var_tags_count.set(f"{len(epcs)} tags")

    # ── Ações ─────────────────────────────────────────────────────────────────

    def clear_logs(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.log("Logs limpos", "INFO")

    def _configurar_ip(self):
        """Permite alterar o IP do leitor em runtime."""
        novo_ip = simpledialog.askstring(
            "IP do Leitor",
            "Digite o IP do FX7500:",
            initialvalue=self.leitor_ip,
            parent=self.root
        )
        if novo_ip:
            self.leitor_ip = novo_ip.strip()
            self.var_leitor_ip.set(self.leitor_ip)
            self.log(f"IP do leitor atualizado: {self.leitor_ip}", "INFO")

    def ping_leitor(self):
        """Testa conexão com o leitor."""
        def _ping():
            self.log(f"Testando conexão com {self.leitor_ip}:{LEITOR_PORTA}...", "INFO")
            leitor = LeitorRFID(
                ip=self.leitor_ip, porta=LEITOR_PORTA,
                log_fn=self.log
            )
            ok = leitor.testar_conexao()
            if ok:
                self.log(f"✓ Leitor acessível em {self.leitor_ip}", "SUCCESS")
            else:
                self.log(f"✗ Leitor não responde em {self.leitor_ip}:{LEITOR_PORTA}", "ERROR")
                if not SLLURP_DISPONIVEL:
                    self.log("  sllurp não instalado — rode: pip install sllurp", "WARNING")

        threading.Thread(target=_ping, daemon=True).start()

    def toggle_modo_simulacao(self):
        """Alterna entre modo REAL e SIMULAÇÃO forçada."""
        if self.running:
            messagebox.showwarning(
                "Middleware Ativo",
                "Pare o middleware antes de alterar o modo.",
                parent=self.root
            )
            return

        self.modo_simulacao = not self.modo_simulacao
        modo_texto = "SIMULAÇÃO" if self.modo_simulacao else "REAL"
        modo_cor = YEL if self.modo_simulacao else GREEN

        self.var_modo.set(modo_texto)
        self.lbl_modo.config(fg=modo_cor)
        self.btn_toggle_modo.config(
            text=f"[MODO: {modo_texto}]",
            fg=modo_cor
        )
        self.log(f"Modo alterado para: {modo_texto}", "INFO")

    def limpar_arquivos_txt(self):
        """Remove todos os .txt do diretório RFID."""
        self.log(f"Limpando arquivos em {RFID_DIR}...", "INFO")
        for arquivo in glob.glob(os.path.join(RFID_DIR, "*.txt")):
            try:
                os.remove(arquivo)
                self.log(f"├─ Removido: {os.path.basename(arquivo)}", "SUCCESS")
            except Exception as e:
                self.log(f"├─ Erro: {os.path.basename(arquivo)} — {e}", "ERROR")

    def executar_leitura(self) -> list:
        """
        Executa leitura RFID real (LLRP) ou simulada.
        No modo simulação, lê instantaneamente do template.
        Retorna lista de EPCs.
        """
        # Modo simulação: leitura instantânea do template
        if self.modo_simulacao:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            template_path = os.path.join(script_dir, TAGS_TEMPLATE)
            tags = []

            try:
                with open(template_path, "r", encoding="utf-8") as f:
                    for line in f:
                        tag = line.strip()
                        if tag:
                            tags.append(tag)
                self.log(f"├─ Modo SIMULAÇÃO: {len(tags)} tags do template", "INFO")
                return tags
            except FileNotFoundError:
                self.log(f"├─ ERRO: Template não encontrado!", "ERROR")
                self.log(f"├─ Caminho: {template_path}", "ERROR")
                return []

        # Modo REAL: conecta no leitor via LLRP
        leitor = LeitorRFID(
            ip=self.leitor_ip,
            porta=LEITOR_PORTA,
            timeout=LEITURA_TIMEOUT,
            potencia=POTENCIA_TX,
            log_fn=self.log
        )
        return leitor.ler()

    def gravar_lista_tags(self, epcs: list) -> bool:
        """Grava EPCs em C:\\RFID\\ListaTagtxt.txt"""
        destino = os.path.join(RFID_DIR, ARQUIVO_TAGS)
        try:
            Path(RFID_DIR).mkdir(parents=True, exist_ok=True)
            with open(destino, "w", encoding="utf-8") as f:
                for epc in epcs:
                    f.write(f"{epc}\n")
            self.log(f"├─ ListaTagtxt.txt gravado: {len(epcs)} tags", "SUCCESS")
            self.log(f"├─ Destino: {destino}", "INFO")
            return True
        except Exception as e:
            self.log(f"├─ Erro ao gravar: {e}", "ERROR")
            return False

    # ── Middleware (watchdog) ─────────────────────────────────────────────────

    def start_middleware(self):
        if self.running:
            return

        self.running = True
        self.var_middleware.set("Online")
        self.dot_middleware.config(fg=GREEN)
        self.lbl_middleware.config(fg=GREEN)
        self.btn_start.config(fg=GRAY)
        self.btn_stop.config(fg=RED)

        self.log("=" * 50, "INFO")
        self.log("Middleware iniciado", "SUCCESS")
        self.log(f"├─ Monitorando: {RFID_DIR}", "INFO")
        self.log(f"├─ Leitor: {self.leitor_ip}:{LEITOR_PORTA}", "INFO")
        self.log(f"├─ Timeout leitura: {LEITURA_TIMEOUT}s", "INFO")
        if self.modo_simulacao:
            self.log("├─ Modo: SIMULAÇÃO (sllurp não instalado)", "WARNING")
        else:
            self.log("├─ Modo: REAL (LLRP)", "SUCCESS")
        self.log("=" * 50, "INFO")

        self.limpar_arquivos_txt()

        def run_observer():
            self.observer = Observer()
            handler = RFIDEventHandler(self)
            self.observer.schedule(handler, RFID_DIR, recursive=False)
            self.observer.start()
            try:
                while self.running:
                    time.sleep(0.1)
            except Exception as e:
                self.log(f"Observer error: {e}", "ERROR")

        threading.Thread(target=run_observer, daemon=True).start()

    def stop_middleware(self):
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

        self.log("Middleware parado", "WARNING")

    # ── Fluxo completo ────────────────────────────────────────────────────────

    def processar_portal_aberto(self):
        """
        Chamado quando RFIDIniciar.txt é detectado.
        Lê AUTOMATICAMENTE as tags do template (caixa no compartimento).
        """
        self.log("=" * 50, "SUCCESS")
        self.log(">>> PORTAL ABERTO — lendo tags automaticamente <<<", "SUCCESS")

        self.var_portal.set("Lendo...")
        self.dot_portal.config(fg=YEL)
        self.lbl_portal.config(fg=YEL)
        self.portal_aberto = True

        def _ler():
            # Leitura automática e instantânea
            epcs = self.executar_leitura()

            # Armazena EPCs para gravar quando o portal fechar
            self.ultima_leitura_epcs = epcs

            if epcs:
                self._atualizar_tags_display(epcs)
                self.log(f"├─ {len(epcs)} tags lidas do template", "SUCCESS")
                self.log("├─ Aguardando RFIDParar.txt para gravar...", "INFO")
            else:
                self.log("├─ ERRO: Nenhuma tag no template!", "ERROR")
                self.log(f"├─ Verifique: {TAGS_TEMPLATE}", "WARNING")

            self.var_portal.set("Pronto")
            self.dot_portal.config(fg=GREEN)
            self.lbl_portal.config(fg=GREEN)
            self.log("=" * 50, "SUCCESS")

        threading.Thread(target=_ler, daemon=True).start()

    def processar_portal_fechado(self):
        """
        Chamado quando RFIDParar.txt é detectado.
        O TOTVS sinaliza fim de sessão.
        AGORA grava o arquivo ListaTagtxt.txt com as tags lidas.
        """
        self.log("=" * 50, "WARNING")
        self.log(">>> PORTAL FECHADO pelo TOTVS <<<", "WARNING")

        # Grava arquivo com as tags lidas quando o portal abriu
        if self.ultima_leitura_epcs:
            self.log(f"├─ Gravando arquivo com {len(self.ultima_leitura_epcs)} tags...", "INFO")
            self.gravar_lista_tags(self.ultima_leitura_epcs)
        else:
            self.log("├─ Nenhuma tag para gravar", "WARNING")

        self.log("=" * 50, "WARNING")

        self.var_portal.set("Fechado")
        self.dot_portal.config(fg=GRAY)
        self.lbl_portal.config(fg=GRAY)
        self.portal_aberto = False

    # ── Teste ─────────────────────────────────────────────────────────────────

    def test_flow(self):
        """Simula criação de RFIDIniciar.txt e RFIDParar.txt."""
        if not self.running:
            self.log("ERRO: Inicie o middleware primeiro!", "ERROR")
            return

        def _test():
            self.log("─" * 40, "WARNING")
            self.log("TESTE: Simulando abertura do portal...", "WARNING")
            time.sleep(0.5)

            with open(os.path.join(RFID_DIR, ARQUIVO_INICIAR), "w") as f:
                f.write("")

            self.log("TESTE: RFIDIniciar.txt criado", "INFO")

            # Aguarda leitura + 2s
            time.sleep(LEITURA_TIMEOUT + 2)

            self.log("TESTE: Simulando fechamento do portal...", "WARNING")
            with open(os.path.join(RFID_DIR, ARQUIVO_PARAR), "w") as f:
                f.write("")

            self.log("TESTE: RFIDParar.txt criado", "INFO")
            self.log("TESTE: Fluxo completo concluído!", "SUCCESS")
            self.log("─" * 40, "WARNING")

        threading.Thread(target=_test, daemon=True).start()

# ============================================================================
# WATCHDOG — MONITOR DE ARQUIVOS
# ============================================================================

class RFIDEventHandler(FileSystemEventHandler):
    """Monitora C:\\RFID e reage aos arquivos do TOTVS."""

    def __init__(self, gui: RFIDMiddlewareGUI):
        self.gui = gui

    def on_created(self, event):
        if event.is_directory:
            return

        nome = os.path.basename(event.src_path)
        self.gui.log(f"Arquivo detectado: {nome}", "INFO")

        if nome == ARQUIVO_INICIAR:
            # TOTVS sinalizou início — ler RFID agora
            self.gui.processar_portal_aberto()

        elif nome == ARQUIVO_PARAR:
            # TOTVS sinalizou fim de sessão
            self.gui.processar_portal_fechado()

        elif nome == ARQUIVO_TAGS:
            self.gui.log(f"├─ ListaTagtxt.txt detectado pelo watchdog", "INFO")

# ============================================================================
# MAIN
# ============================================================================

def main():
    root = tk.Tk()
    app  = RFIDMiddlewareGUI(root)

    if not SLLURP_DISPONIVEL:
        root.after(500, lambda: app.log(
            "sllurp não instalado — rode: pip install sllurp", "WARNING"
        ))
        root.after(600, lambda: app.log(
            "Rodando em modo SIMULAÇÃO (tags_template.txt)", "WARNING"
        ))

    root.mainloop()


if __name__ == "__main__":
    main()
