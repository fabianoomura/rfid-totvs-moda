# RFID Simulator — TOTVS Integration

Ambiente de simulação completo para integração de leitura RFID com o TOTVS Moda.  
Emula o leitor **Zebra FX7500** via protocolo **LLRP** e o middleware de troca de arquivos.

---

## Visão Geral

```
┌─────────────────────┐        arquivos        ┌──────────────────────┐
│                     │  ←── RFIDIniciar.txt ──  │                      │
│   TOTVS Moda        │  ──→ ListaTagtxt.txt ──→ │  rfid_middleware.py  │
│                     │  ←── RFIDParar.txt ───   │                      │
└─────────────────────┘                          └──────────────────────┘
                                                          │ LLRP
                                                          ↓
                                                 ┌──────────────────────┐
                                                 │  fx7500_simulator.py │
                                                 │  (Zebra FX7500 fake) │
                                                 └──────────────────────┘
```

### Como funciona

| Etapa | Quem faz | O quê |
|-------|----------|-------|
| 1 | TOTVS | Cria `C:\RFID\RFIDIniciar.txt` sinalizando início de leitura |
| 2 | Middleware | Detecta o arquivo e lê as tags RFID (real ou simulado) |
| 3 | TOTVS | Cria `C:\RFID\RFIDParar.txt` sinalizando fim da sessão |
| 4 | Middleware | Grava `C:\RFID\ListaTagtxt.txt` com os EPCs lidos |
| 5 | TOTVS | Consome `ListaTagtxt.txt` e processa o inventário |

---

## Arquivos

```
rfid_simulador/
├── rfid_middleware.py          # Middleware principal (GUI + watchdog)
├── fx7500_simulator.py         # Simulador do leitor Zebra FX7500 (servidor LLRP)
├── rfid_middleware_gui_simples.py  # Versão simplificada do middleware
└── data/
    └── tags_template.txt       # Tags RFID de exemplo (SGTIN-96 / EPC)
```

---

## Instalação

```bash
pip install watchdog
```

Para integração real com o leitor FX7500:
```bash
pip install sllurp
```

---

## Como usar

### Modo Simulação (sem leitor físico)

1. Execute o middleware:
```bash
python rfid_middleware.py
```
2. Clique **[INICIAR]** — o middleware monitora `C:\RFID\` e lê as tags do template automaticamente
3. Use **[TESTAR]** para simular o ciclo completo do TOTVS

### Modo Real (com Zebra FX7500)

1. Em dois terminais separados:

```bash
# Terminal 1 — Simulador do leitor
python fx7500_simulator.py

# Terminal 2 — Middleware
python rfid_middleware.py
```

2. No **FX7500 Simulator**:
   - Clique `[INICIAR SERVIDOR]`
   - Adicione as tags desejadas à sessão (`[+ Template]`)
   - Aguarde o middleware conectar

3. No **Middleware**:
   - Clique `[INICIAR]`
   - O ciclo de leitura ocorre automaticamente via LLRP

---

## Fluxo Automático (Modo Simulação)

```
RFIDIniciar.txt detectado
    └── Lê data/tags_template.txt instantaneamente
    └── Armazena EPCs em memória

RFIDParar.txt detectado
    └── Grava C:\RFID\ListaTagtxt.txt
    └── TOTVS consome o arquivo
```

---

## Simulador FX7500

O `fx7500_simulator.py` implementa um servidor LLRP mínimo que replica o comportamento do leitor Zebra FX7500:

- **Protocolo**: LLRP 1.0.1 sobre TCP porta `5084`
- **Mensagens implementadas**: `READER_EVENT_NOTIFICATION`, `GET_READER_CONFIG`, `ADD/ENABLE/START/STOP/DELETE_ROSPEC`, `RO_ACCESS_REPORT`, `KEEPALIVE`
- **Simulação realista**: envia tags gradualmente em lotes de 5 (simula leitura por antena)
- **RSSI simulado**: valores aleatórios entre -65 e -45 dBm
- **Gestão de sessão**: adicione tags por template, seleção manual ou digitação de EPC

---

## Formato das Tags

As tags seguem o padrão **EPC SGTIN-96** em hexadecimal (24 caracteres):

```
303B0286800520C000000001
│   │   │   │   └── Serial
│   │   │   └────── Item Reference
│   │   └────────── Company Prefix
│   └────────────── Filter + Partition
└────────────────── Header (SGTIN-96 = 0x30)
```

---

## Configuração

### `rfid_middleware.py`

| Constante | Padrão | Descrição |
|-----------|--------|-----------|
| `RFID_DIR` | `C:\RFID` | Pasta monitorada |
| `TAGS_TEMPLATE` | `data/tags_template.txt` | Template de tags |
| `ARQUIVO_INICIAR` | `RFIDIniciar.txt` | Sinal de início |
| `ARQUIVO_PARAR` | `RFIDParar.txt` | Sinal de parada |
| `ARQUIVO_TAGS` | `ListaTagtxt.txt` | Saída para o TOTVS |

### `fx7500_simulator.py`

| Constante | Padrão | Descrição |
|-----------|--------|-----------|
| `LLRP_PORT` | `5084` | Porta do servidor LLRP |
| `INTERVALO_TAG` | `0.05s` | Delay entre tags (realismo) |
| `RSSI_MIN/MAX` | `-65 / -45` | Faixa de RSSI simulado |

---

## Requisitos

- Python 3.10+
- Windows (para integração com TOTVS via `C:\RFID\`)
- `watchdog` — monitoramento de pasta
- `sllurp` — comunicação LLRP real (opcional)

---

*Desenvolvido por MOOUI para ambiente TOTVS Moda.*
