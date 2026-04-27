"""
fx7500_simulator.py — MOOUI
Simulador do leitor RFID Zebra FX7500.

Abre um servidor LLRP na porta 5084 (localhost) e responde
como se fosse o leitor real — o middleware não distingue.

Uso:
    1. Rode este script primeiro
    2. Rode rfid_middleware_gui.py (LEITOR_IP = '127.0.0.1')
    3. Configure as tags que quer enviar por sessão
    4. Dispare o teste pelo middleware ou pelo botão aqui

pip install (nenhuma dependência extra — só stdlib)
"""

import json
import os
import queue
import random
import socket
import struct
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import scrolledtext, simpledialog, messagebox

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

LLRP_PORT      = 5084
HOST           = "0.0.0.0"        # Aceita conexões locais e de rede
TAGS_TEMPLATE  = "data/tags_template.txt"
SESSAO_DB      = "data/sessoes.json"  # Persiste sessões entre execuções

# Velocidade de simulação
INTERVALO_TAG  = 0.05   # segundos entre cada tag enviada (simula leitura gradual)
RSSI_MIN       = -65    # dBm mínimo simulado
RSSI_MAX       = -45    # dBm máximo simulado

# ── Tema visual (igual ao middleware) ────────────────────────────────────────
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
PURP  = "#cc88ff"
F     = "Courier New"

# ============================================================================
# PROTOCOLO LLRP — IMPLEMENTAÇÃO MÍNIMA
# ============================================================================
#
# O LLRP usa mensagens binárias com header de 10 bytes:
#   [2B versão+tipo] [4B tamanho total] [4B ID da mensagem]
#
# Mensagens que o simulador precisa tratar:
#   KEEPALIVE_ACK      (tipo 72)  → cliente confirmou keepalive
#   GET_READER_CONFIG  (tipo 2)   → cliente pede config
#   ADD_ROSPEC         (tipo 20)  → cliente adiciona spec de leitura
#   ENABLE_ROSPEC      (tipo 24)  → cliente habilita spec
#   START_ROSPEC       (tipo 26)  → cliente inicia leitura
#   STOP_ROSPEC        (tipo 28)  → cliente para leitura
#   DELETE_ROSPEC      (tipo 22)  → cliente remove spec
#   CLOSE_CONNECTION   (tipo 14)  → cliente encerra
#
# Mensagens que o simulador envia:
#   READER_EVENT_NOTIFICATION (tipo 1023) → conexão estabelecida
#   GET_READER_CONFIG_RESPONSE (tipo 11)  → resposta de config
#   ADD_ROSPEC_RESPONSE        (tipo 30)  → confirmação
#   ENABLE_ROSPEC_RESPONSE     (tipo 34)  → confirmação
#   START_ROSPEC_RESPONSE      (tipo 36)  → confirmação
#   STOP_ROSPEC_RESPONSE       (tipo 38)  → confirmação
#   DELETE_ROSPEC_RESPONSE     (tipo 32)  → confirmação
#   RO_ACCESS_REPORT           (tipo 61)  → TAGS LIDAS
#   KEEPALIVE                  (tipo 62)  → keepalive periódico
#   CLOSE_CONNECTION_RESPONSE  (tipo 4)   → confirmação de encerramento

class LLRPMessage:
    """Utilitários para montar/desmontar mensagens LLRP."""

    VERSION = 1  # LLRP 1.0.1

    # Tipos de mensagem
    CLOSE_CONNECTION          = 14
    CLOSE_CONNECTION_RESPONSE = 4
    GET_READER_CONFIG         = 2
    GET_READER_CONFIG_RESPONSE= 11
    ADD_ROSPEC                = 20
    ADD_ROSPEC_RESPONSE       = 30
    DELETE_ROSPEC             = 22
    DELETE_ROSPEC_RESPONSE    = 32
    ENABLE_ROSPEC             = 24
    ENABLE_ROSPEC_RESPONSE    = 34
    START_ROSPEC              = 26
    START_ROSPEC_RESPONSE     = 36
    STOP_ROSPEC               = 28
    STOP_ROSPEC_RESPONSE      = 38
    RO_ACCESS_REPORT          = 61
    KEEPALIVE                 = 62
    KEEPALIVE_ACK             = 72
    READER_EVENT_NOTIFICATION = 1023
    ERROR_MESSAGE             = 100

    @staticmethod
    def parse_header(data: bytes):
        """Extrai (tipo, tamanho, msg_id) do header de 10 bytes."""
        if len(data) < 10:
            return None, 0, 0
        ver_type = struct.unpack('!H', data[0:2])[0]
        msg_type = ver_type & 0x03FF
        length   = struct.unpack('!I', data[2:6])[0]
        msg_id   = struct.unpack('!I', data[6:10])[0]
        return msg_type, length, msg_id

    @staticmethod
    def build_header(msg_type: int, payload: bytes, msg_id: int = 0) -> bytes:
        """Monta header LLRP de 10 bytes."""
        ver_type = (LLRPMessage.VERSION << 10) | (msg_type & 0x03FF)
        length   = 10 + len(payload)
        return struct.pack('!HII', ver_type, length, msg_id) + payload

    @classmethod
    def simple_response(cls, msg_type: int, msg_id: int, status: int = 0) -> bytes:
        """Resposta simples com status code (Success = 0)."""
        # LLRPStatus TLV: tipo=287, len=8, statusCode(2)+errorDesc(2+0)
        status_tlv = struct.pack('!HHH', 287, 8, status) + b'\x01\x00'
        return cls.build_header(msg_type, status_tlv, msg_id)

    @classmethod
    def reader_event_notification(cls, msg_id: int = 1) -> bytes:
        """Notificação de conexão estabelecida."""
        # ReaderEventNotificationData TLV: tipo=246
        # ConnectionAttemptEvent TLV: tipo=256, status=0 (Success)
        conn_event = struct.pack('!HHH', 256, 6, 0)
        # Timestamp TLV: tipo=128
        ts_us = int(time.time() * 1e6)
        timestamp = struct.pack('!HHQ', 128, 12, ts_us)
        payload = struct.pack('!HH', 246, 4 + len(timestamp) + len(conn_event))
        payload += timestamp + conn_event
        return cls.build_header(cls.READER_EVENT_NOTIFICATION, payload, msg_id)

    @classmethod
    def keepalive(cls, msg_id: int) -> bytes:
        """Mensagem keepalive."""
        return cls.build_header(cls.KEEPALIVE, b'', msg_id)

    @classmethod
    def ro_access_report(cls, epcs: list, msg_id: int) -> bytes:
        """
        Relatório com as tags lidas.
        Cada tag vira um TagReportData TLV com EPC + RSSI.
        """
        payload = b''
        for epc_hex in epcs:
            try:
                epc_bytes = bytes.fromhex(epc_hex)
            except ValueError:
                continue

            # EPCData TLV (tipo=241): wordCount(2) + epc_bytes
            bit_count  = len(epc_bytes) * 8
            epc_tlv    = struct.pack('!HHH', 241, 4 + len(epc_bytes), bit_count) + epc_bytes

            # PeakRSSI TLV (tipo=135): valor int8 em dBm
            rssi_val   = random.randint(RSSI_MIN, RSSI_MAX)
            rssi_tlv   = struct.pack('!HHb', 135, 5, rssi_val)

            # AntennaID TLV (tipo=132)
            ant_id     = random.choice([1, 2])
            ant_tlv    = struct.pack('!HHH', 132, 6, ant_id)

            # TagReportData TLV (tipo=240)
            tag_data   = epc_tlv + rssi_tlv + ant_tlv
            tag_tlv    = struct.pack('!HH', 240, 4 + len(tag_data)) + tag_data
            payload   += tag_tlv

        return cls.build_header(cls.RO_ACCESS_REPORT, payload, msg_id)


# ============================================================================
# SERVIDOR LLRP
# ============================================================================

class LLRPServer:
    """
    Servidor TCP que simula o FX7500.
    Aceita uma conexão por vez (igual ao leitor real).
    """

    def __init__(self, host: str, port: int, log_fn, on_client_connect, on_client_disconnect):
        self.host               = host
        self.port               = port
        self._log               = log_fn
        self._on_connect        = on_client_connect
        self._on_disconnect     = on_client_disconnect
        self._running           = False
        self._server_sock       = None
        self._client_sock       = None
        self._client_thread     = None
        self._leitura_ativa     = False
        self._tags_sessao       = []   # EPCs a enviar na próxima leitura
        self._msg_id_counter    = 100
        self._keepalive_thread  = None

    def _next_id(self):
        self._msg_id_counter += 1
        return self._msg_id_counter

    def start(self):
        self._running     = True
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.host, self.port))
        self._server_sock.listen(1)
        self._server_sock.settimeout(1.0)
        self._log(f"Servidor LLRP aguardando em {self.host}:{self.port}", "INFO")
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def stop(self):
        self._running = False
        if self._client_sock:
            try: self._client_sock.close()
            except: pass
        if self._server_sock:
            try: self._server_sock.close()
            except: pass

    def set_tags_sessao(self, tags: list):
        """Define quais EPCs serão enviados na próxima leitura."""
        self._tags_sessao = list(tags)

    def disparar_leitura(self):
        """Envia os EPCs configurados para o cliente conectado."""
        if not self._client_sock:
            self._log("Nenhum cliente conectado", "WARNING")
            return
        if not self._tags_sessao:
            self._log("Nenhuma tag configurada para esta sessão", "WARNING")
            return
        threading.Thread(target=self._enviar_tags, daemon=True).start()

    def _enviar_tags(self):
        """Envia tags gradualmente (simula leitura real)."""
        self._leitura_ativa = True
        self._log(f"Iniciando envio de {len(self._tags_sessao)} tags...", "SUCCESS")

        enviadas = []
        for i, epc in enumerate(self._tags_sessao):
            if not self._running or not self._client_sock:
                break
            enviadas.append(epc)

            # Envia em lotes de 5 (simula múltiplas leituras chegando)
            if len(enviadas) % 5 == 0 or i == len(self._tags_sessao) - 1:
                try:
                    msg = LLRPMessage.ro_access_report(enviadas[-5:] if len(enviadas) >= 5 else enviadas, self._next_id())
                    self._client_sock.sendall(msg)
                    self._log(f"├─ Enviadas {len(enviadas)}/{len(self._tags_sessao)} tags", "INFO")
                except Exception as e:
                    self._log(f"├─ Erro ao enviar: {e}", "ERROR")
                    break
            time.sleep(INTERVALO_TAG)

        # Relatório final completo
        if enviadas and self._client_sock:
            try:
                msg = LLRPMessage.ro_access_report(enviadas, self._next_id())
                self._client_sock.sendall(msg)
                self._log(f"✓ Relatório final: {len(enviadas)} tags enviadas", "SUCCESS")
            except Exception as e:
                self._log(f"Erro no relatório final: {e}", "ERROR")

        self._leitura_ativa = False

    def _accept_loop(self):
        """Loop principal — aceita conexões."""
        while self._running:
            try:
                client_sock, addr = self._server_sock.accept()
                self._log(f"Cliente conectado: {addr[0]}:{addr[1]}", "SUCCESS")
                self._client_sock = client_sock
                self._on_connect(addr)

                # Envia notificação de conexão
                client_sock.sendall(LLRPMessage.reader_event_notification(self._next_id()))

                # Inicia keepalive
                self._keepalive_thread = threading.Thread(
                    target=self._keepalive_loop, args=(client_sock,), daemon=True
                )
                self._keepalive_thread.start()

                # Processa mensagens
                self._handle_client(client_sock)

                self._client_sock = None
                self._on_disconnect()
                self._log("Cliente desconectado", "WARNING")

            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    self._log(f"Erro no servidor: {e}", "ERROR")

    def _keepalive_loop(self, sock):
        """Envia keepalive a cada 10 segundos."""
        while self._running and self._client_sock:
            time.sleep(10)
            try:
                if self._client_sock:
                    sock.sendall(LLRPMessage.keepalive(self._next_id()))
            except:
                break

    def _handle_client(self, sock):
        """Processa mensagens do cliente (middleware)."""
        buffer = b''
        sock.settimeout(2.0)

        while self._running:
            try:
                data = sock.recv(4096)
                if not data:
                    break
                buffer += data

                # Processar todas as mensagens no buffer
                while len(buffer) >= 10:
                    msg_type, length, msg_id = LLRPMessage.parse_header(buffer)
                    if length == 0 or len(buffer) < length:
                        break

                    msg_data = buffer[:length]
                    buffer   = buffer[length:]
                    self._process_message(sock, msg_type, msg_id, msg_data)

            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    self._log(f"Erro na conexão: {e}", "ERROR")
                break

    def _process_message(self, sock, msg_type: int, msg_id: int, data: bytes):
        """Processa cada mensagem LLRP recebida."""
        NOMES = {
            LLRPMessage.GET_READER_CONFIG: "GET_READER_CONFIG",
            LLRPMessage.ADD_ROSPEC:        "ADD_ROSPEC",
            LLRPMessage.DELETE_ROSPEC:     "DELETE_ROSPEC",
            LLRPMessage.ENABLE_ROSPEC:     "ENABLE_ROSPEC",
            LLRPMessage.START_ROSPEC:      "START_ROSPEC",
            LLRPMessage.STOP_ROSPEC:       "STOP_ROSPEC",
            LLRPMessage.KEEPALIVE_ACK:     "KEEPALIVE_ACK",
            LLRPMessage.CLOSE_CONNECTION:  "CLOSE_CONNECTION",
        }
        nome = NOMES.get(msg_type, f"TIPO_{msg_type}")
        self._log(f"← {nome} (id={msg_id})", "INFO")

        try:
            if msg_type == LLRPMessage.GET_READER_CONFIG:
                sock.sendall(LLRPMessage.simple_response(
                    LLRPMessage.GET_READER_CONFIG_RESPONSE, msg_id))

            elif msg_type == LLRPMessage.ADD_ROSPEC:
                sock.sendall(LLRPMessage.simple_response(
                    LLRPMessage.ADD_ROSPEC_RESPONSE, msg_id))

            elif msg_type == LLRPMessage.DELETE_ROSPEC:
                sock.sendall(LLRPMessage.simple_response(
                    LLRPMessage.DELETE_ROSPEC_RESPONSE, msg_id))

            elif msg_type == LLRPMessage.ENABLE_ROSPEC:
                sock.sendall(LLRPMessage.simple_response(
                    LLRPMessage.ENABLE_ROSPEC_RESPONSE, msg_id))

            elif msg_type == LLRPMessage.START_ROSPEC:
                sock.sendall(LLRPMessage.simple_response(
                    LLRPMessage.START_ROSPEC_RESPONSE, msg_id))
                # Leitura iniciada — enviar tags automaticamente
                if self._tags_sessao:
                    threading.Thread(target=self._enviar_tags, daemon=True).start()
                else:
                    self._log("START_ROSPEC recebido mas sem tags configuradas", "WARNING")

            elif msg_type == LLRPMessage.STOP_ROSPEC:
                sock.sendall(LLRPMessage.simple_response(
                    LLRPMessage.STOP_ROSPEC_RESPONSE, msg_id))

            elif msg_type == LLRPMessage.KEEPALIVE_ACK:
                pass  # Nada a fazer

            elif msg_type == LLRPMessage.CLOSE_CONNECTION:
                sock.sendall(LLRPMessage.simple_response(
                    LLRPMessage.CLOSE_CONNECTION_RESPONSE, msg_id))
                sock.close()

        except Exception as e:
            self._log(f"Erro ao responder {nome}: {e}", "ERROR")


# ============================================================================
# INTERFACE GRÁFICA
# ============================================================================

class FX7500SimulatorGUI:

    def __init__(self, root):
        self.root = root
        self.root.title("FX7500 Simulator — MOOUI")
        self.root.configure(bg=BG)
        self.root.resizable(False, True)

        self._log_queue      = queue.Queue()
        self._server         = None
        self._server_running = False
        self._cliente_ip     = None

        # Tags disponíveis (carregadas do template)
        self._todas_tags  = self._carregar_template()

        # Tags da sessão atual (as que serão enviadas)
        self._tags_sessao = []

        self.var_server   = tk.StringVar(value="Offline")
        self.var_cliente  = tk.StringVar(value="Nenhum")
        self.var_sessao   = tk.StringVar(value="0 tags")

        self._build()
        self._processar_log_queue()

        # Centralizar
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

    def _btn(self, parent, texto, fg, comando, side="left"):
        b = tk.Label(parent, text=texto, font=(F, 9, "bold"), bg=BG2, fg=fg, cursor="hand2")
        b.pack(side=side, padx=(0, 8))
        b.bind("<Button-1>", lambda e: comando())
        b.bind("<Enter>",    lambda e: b.config(fg=WHITE))
        b.bind("<Leave>",    lambda e: b.config(fg=fg))
        return b

    # ── Build ────────────────────────────────────────────────────────────────

    def _build(self):
        outer = tk.Frame(self.root, bg=BRD, padx=1, pady=1)
        outer.pack(padx=10, pady=10, fill="both", expand=True)
        m = tk.Frame(outer, bg=BG2, padx=18, pady=14)
        m.pack(fill="both", expand=True)

        # Header
        tk.Label(m, text="FX7500 Simulator",
                 font=(F, 11, "bold"), bg=BG2, fg=WHITE).pack(pady=(0, 2))
        tk.Label(m, text="Zebra FX7500 — LLRP Server @ localhost:5084",
                 font=(F, 8), bg=BG2, fg=LGRAY).pack(pady=(0, 8))
        self._div(m)

        # Status servidor
        r1 = tk.Frame(m, bg=BG2); r1.pack(fill="x", pady=2)
        tk.Label(r1, text="Servidor LLRP:", font=(F, 9), bg=BG2, fg=LGRAY,
                 width=16, anchor="w").pack(side="left")
        self.dot_server = tk.Label(r1, text="● ", font=(F, 9), bg=BG2, fg=RED)
        self.dot_server.pack(side="left")
        self.lbl_server = tk.Label(r1, textvariable=self.var_server,
                                   font=(F, 9), bg=BG2, fg=RED, anchor="w")
        self.lbl_server.pack(side="left")

        # Status cliente
        r2 = tk.Frame(m, bg=BG2); r2.pack(fill="x", pady=2)
        tk.Label(r2, text="Middleware:", font=(F, 9), bg=BG2, fg=LGRAY,
                 width=16, anchor="w").pack(side="left")
        self.dot_cliente = tk.Label(r2, text="● ", font=(F, 9), bg=BG2, fg=GRAY)
        self.dot_cliente.pack(side="left")
        self.lbl_cliente = tk.Label(r2, textvariable=self.var_cliente,
                                    font=(F, 9), bg=BG2, fg=GRAY, anchor="w")
        self.lbl_cliente.pack(side="left")

        # Tags na sessão
        r3 = tk.Frame(m, bg=BG2); r3.pack(fill="x", pady=2)
        tk.Label(r3, text="Sessão atual:", font=(F, 9), bg=BG2, fg=LGRAY,
                 width=16, anchor="w").pack(side="left")
        tk.Label(r3, textvariable=self.var_sessao,
                 font=(F, 9, "bold"), bg=BG2, fg=PURP, anchor="w").pack(side="left")

        tk.Frame(m, bg=BG2, height=6).pack()
        self._div(m)

        # Botões do servidor
        br1 = tk.Frame(m, bg=BG2); br1.pack(fill="x", pady=6)
        self.btn_start = self._btn(br1, "[INICIAR SERVIDOR]", GREEN, self.start_server)
        self.btn_stop  = self._btn(br1, "[PARAR]", GRAY, self.stop_server)

        self._div(m)

        # Painel de tags da sessão
        self._lbl(m, "Tags da sessão (serão enviadas ao middleware):", fg=PURP)
        tk.Frame(m, bg=BG2, height=4).pack()

        # Frame lista + botões lado a lado
        frame_tags = tk.Frame(m, bg=BG2)
        frame_tags.pack(fill="x")

        # Lista de tags da sessão
        frame_lista = tk.Frame(frame_tags, bg=BG2)
        frame_lista.pack(side="left", fill="both", expand=True)

        self.lista_sessao = tk.Listbox(
            frame_lista, height=8, font=(F, 8),
            bg="#0a0a0a", fg=PURP, selectbackground=GRAY,
            selectforeground=WHITE, relief="flat", bd=0,
            activestyle="none"
        )
        self.lista_sessao.pack(side="left", fill="both", expand=True)
        scroll_s = tk.Scrollbar(frame_lista, orient="vertical",
                                command=self.lista_sessao.yview)
        scroll_s.pack(side="right", fill="y")
        self.lista_sessao.config(yscrollcommand=scroll_s.set)

        # Botões de gestão de tags
        frame_btns = tk.Frame(frame_tags, bg=BG2, padx=8)
        frame_btns.pack(side="left", fill="y")

        for texto, fg, cmd in [
            ("[+ Template]",  GREEN, self.add_todas_template),
            ("[+ Selecionar]",CYAN,  self.add_selecionar),
            ("[+ Manual]",    YEL,   self.add_manual),
            ("[─ Remover]",   RED,   self.remover_tag),
            ("[✕ Limpar]",    GRAY,  self.limpar_sessao),
            ("[↕ Embaralhar]",LGRAY, self.embaralhar_sessao),
        ]:
            b = tk.Label(frame_btns, text=texto, font=(F, 8), bg=BG2,
                         fg=fg, cursor="hand2", anchor="w")
            b.pack(fill="x", pady=2)
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>", lambda e, b=b: b.config(fg=WHITE))
            b.bind("<Leave>", lambda e, b=b, f=fg: b.config(fg=f))

        self._div(m)

        # Botão disparar + info
        br2 = tk.Frame(m, bg=BG2); br2.pack(fill="x", pady=6)
        self._btn(br2, "[▶ DISPARAR LEITURA]", YEL, self.disparar_leitura)
        tk.Label(br2, text="← envia tags ao middleware conectado",
                 font=(F, 8), bg=BG2, fg=LGRAY).pack(side="left")

        self._div(m)

        # Log
        self._lbl(m, "Log LLRP:")
        self.log_text = scrolledtext.ScrolledText(
            m, height=12, wrap=tk.WORD, font=(F, 8),
            bg="#0a0a0a", fg=LGRAY, insertbackground=CYAN,
            relief="flat", bd=0, padx=8, pady=6
        )
        self.log_text.pack(fill="both", expand=True, pady=(4, 0))
        for level, color in [("timestamp", GRAY), ("info", CYAN),
                              ("success", GREEN), ("warning", YEL),
                              ("error", RED), ("purp", PURP)]:
            self.log_text.tag_config(level, foreground=color)

        # Footer
        tk.Frame(m, bg=BG2, height=4).pack()
        self._div(m)
        tk.Label(m, text="Configure LEITOR_IP = '127.0.0.1' no middleware",
                 font=(F, 7), bg=BG2, fg=GRAY).pack(anchor="w")

    # ── Log thread-safe ───────────────────────────────────────────────────────

    def log(self, message, level="INFO"):
        self._log_queue.put((message, level))

    def _processar_log_queue(self):
        try:
            while True:
                message, level = self._log_queue.get_nowait()
                self._escrever_log(message, level)
        except queue.Empty:
            pass
        self.root.after(50, self._processar_log_queue)

    def _escrever_log(self, message, level="INFO"):
        colors = {"INFO":CYAN,"SUCCESS":GREEN,"WARNING":YEL,"ERROR":RED,"PURP":PURP}
        color  = colors.get(level, LGRAY)
        ts     = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{ts}] ", "timestamp")
        self.log_text.insert(tk.END, f"{message}\n", level.lower())
        self.log_text.tag_config(level.lower(), foreground=color)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    # ── Template de tags ──────────────────────────────────────────────────────

    def _carregar_template(self) -> list:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(script_dir, TAGS_TEMPLATE)
        tags = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for linha in f:
                    t = linha.strip()
                    if t and len(t) == 24:
                        tags.append(t)
        except FileNotFoundError:
            pass
        return list(dict.fromkeys(tags))  # Remove duplicatas mantendo ordem

    def _atualizar_lista_sessao(self):
        self.lista_sessao.delete(0, tk.END)
        for i, tag in enumerate(self._tags_sessao):
            self.lista_sessao.insert(tk.END, f"{i+1:03d} │ {tag}")
        self.var_sessao.set(f"{len(self._tags_sessao)} tags")
        if self._server:
            self._server.set_tags_sessao(self._tags_sessao)

    # ── Gestão de tags da sessão ──────────────────────────────────────────────

    def add_todas_template(self):
        """Adiciona todas as tags do template à sessão."""
        antes = len(self._tags_sessao)
        for tag in self._todas_tags:
            if tag not in self._tags_sessao:
                self._tags_sessao.append(tag)
        adicionadas = len(self._tags_sessao) - antes
        self._atualizar_lista_sessao()
        self.log(f"+ {adicionadas} tags do template adicionadas ({len(self._tags_sessao)} total)", "PURP")

    def add_selecionar(self):
        """Abre janela para selecionar tags do template."""
        if not self._todas_tags:
            messagebox.showwarning("Sem tags", "Nenhuma tag no template.")
            return

        win = tk.Toplevel(self.root)
        win.title("Selecionar Tags")
        win.configure(bg=BG)
        win.geometry("520x420")

        tk.Label(win, text="Selecione as tags (Ctrl+clique para múltiplas):",
                 font=(F, 9), bg=BG, fg=LGRAY).pack(padx=10, pady=(10, 4), anchor="w")

        frame = tk.Frame(win, bg=BG)
        frame.pack(fill="both", expand=True, padx=10, pady=4)

        lb = tk.Listbox(frame, selectmode=tk.EXTENDED, font=(F, 8),
                        bg="#0a0a0a", fg=CYAN, selectbackground=GRAY,
                        selectforeground=WHITE, relief="flat", bd=0)
        lb.pack(side="left", fill="both", expand=True)

        sb = tk.Scrollbar(frame, orient="vertical", command=lb.yview)
        sb.pack(side="right", fill="y")
        lb.config(yscrollcommand=sb.set)

        for tag in self._todas_tags:
            lb.insert(tk.END, tag)

        def confirmar():
            selecionadas = [self._todas_tags[i] for i in lb.curselection()]
            adicionadas  = 0
            for tag in selecionadas:
                if tag not in self._tags_sessao:
                    self._tags_sessao.append(tag)
                    adicionadas += 1
            self._atualizar_lista_sessao()
            self.log(f"+ {adicionadas} tags selecionadas adicionadas", "PURP")
            win.destroy()

        btn_frame = tk.Frame(win, bg=BG)
        btn_frame.pack(pady=8)
        tk.Button(btn_frame, text="Adicionar", font=(F, 9), bg=BG2, fg=GREEN,
                  relief="flat", command=confirmar).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Cancelar", font=(F, 9), bg=BG2, fg=RED,
                  relief="flat", command=win.destroy).pack(side="left", padx=4)

    def add_manual(self):
        """Permite digitar um EPC manualmente."""
        epc = simpledialog.askstring(
            "Adicionar EPC",
            "Digite o EPC (24 chars hex):\nEx: 303B0286800520C000000001",
            parent=self.root
        )
        if not epc:
            return
        epc = epc.strip().upper()
        if len(epc) != 24:
            messagebox.showerror("EPC inválido", f"EPC deve ter 24 caracteres hex.\nRecebido: {len(epc)} chars")
            return
        try:
            bytes.fromhex(epc)
        except ValueError:
            messagebox.showerror("EPC inválido", "EPC deve conter apenas caracteres hexadecimais (0-9, A-F)")
            return
        if epc in self._tags_sessao:
            messagebox.showinfo("Duplicado", "Esta tag já está na sessão.")
            return
        self._tags_sessao.append(epc)
        self._atualizar_lista_sessao()
        self.log(f"+ EPC manual adicionado: {epc}", "PURP")

    def remover_tag(self):
        """Remove a tag selecionada da sessão."""
        sel = self.lista_sessao.curselection()
        if not sel:
            return
        idx = sel[0]
        tag = self._tags_sessao.pop(idx)
        self._atualizar_lista_sessao()
        self.log(f"─ Tag removida: {tag}", "WARNING")

    def limpar_sessao(self):
        """Limpa todas as tags da sessão."""
        if not self._tags_sessao:
            return
        if messagebox.askyesno("Limpar sessão", f"Remover todas as {len(self._tags_sessao)} tags da sessão?"):
            self._tags_sessao.clear()
            self._atualizar_lista_sessao()
            self.log("Sessão limpa", "WARNING")

    def embaralhar_sessao(self):
        """Embaralha a ordem das tags (simula leitura não-sequencial)."""
        if len(self._tags_sessao) < 2:
            return
        random.shuffle(self._tags_sessao)
        self._atualizar_lista_sessao()
        self.log("Ordem das tags embaralhada", "INFO")

    # ── Servidor ──────────────────────────────────────────────────────────────

    def start_server(self):
        if self._server_running:
            return

        self._server = LLRPServer(
            host=HOST,
            port=LLRP_PORT,
            log_fn=self.log,
            on_client_connect=self._on_cliente_conectado,
            on_client_disconnect=self._on_cliente_desconectado,
        )
        self._server.set_tags_sessao(self._tags_sessao)
        self._server.start()
        self._server_running = True

        self.var_server.set("Online")
        self.dot_server.config(fg=GREEN)
        self.lbl_server.config(fg=GREEN)
        self.btn_start.config(fg=GRAY)
        self.btn_stop.config(fg=RED)

        self.log("=" * 50, "INFO")
        self.log("Servidor LLRP iniciado", "SUCCESS")
        self.log(f"├─ Porta: {LLRP_PORT}", "INFO")
        self.log(f"├─ Configure no middleware: LEITOR_IP = '127.0.0.1'", "SUCCESS")
        self.log("=" * 50, "INFO")

    def stop_server(self):
        if not self._server_running:
            return
        if self._server:
            self._server.stop()
        self._server_running = False
        self._cliente_ip     = None

        self.var_server.set("Offline")
        self.dot_server.config(fg=RED)
        self.lbl_server.config(fg=RED)
        self.var_cliente.set("Nenhum")
        self.dot_cliente.config(fg=GRAY)
        self.lbl_cliente.config(fg=GRAY)
        self.btn_start.config(fg=GREEN)
        self.btn_stop.config(fg=GRAY)
        self.log("Servidor parado", "WARNING")

    def _on_cliente_conectado(self, addr):
        self._cliente_ip = f"{addr[0]}:{addr[1]}"
        self.var_cliente.set(self._cliente_ip)
        self.dot_cliente.config(fg=GREEN)
        self.lbl_cliente.config(fg=GREEN)
        self.log(f"Middleware conectado: {self._cliente_ip}", "SUCCESS")

    def _on_cliente_desconectado(self):
        self._cliente_ip = None
        self.var_cliente.set("Desconectado")
        self.dot_cliente.config(fg=RED)
        self.lbl_cliente.config(fg=RED)

    def disparar_leitura(self):
        """Envia tags manualmente (sem precisar do middleware)."""
        if not self._server_running:
            self.log("ERRO: Inicie o servidor primeiro", "ERROR")
            return
        if not self._server._client_sock:
            self.log("ERRO: Nenhum middleware conectado", "ERROR")
            return
        if not self._tags_sessao:
            self.log("ERRO: Nenhuma tag na sessão — adicione tags primeiro", "ERROR")
            return
        self.log(f"Disparando leitura manual: {len(self._tags_sessao)} tags", "SUCCESS")
        self._server.disparar_leitura()


# ============================================================================
# MAIN
# ============================================================================

def main():
    # Garantir que a pasta data/ existe
    Path("data").mkdir(exist_ok=True)

    root = tk.Tk()
    app  = FX7500SimulatorGUI(root)

    # Log inicial
    root.after(500, lambda: app.log("Simulador pronto — clique [INICIAR SERVIDOR]", "SUCCESS"))
    root.after(600, lambda: app.log(
        f"Template carregado: {len(app._todas_tags)} tags disponíveis", "INFO"
    ))

    root.mainloop()


if __name__ == "__main__":
    main()
