"""
rfid_interceptor.py — MOOUI
Servidor de interceptação para descobrir o protocolo que o TOTVS usa
para se comunicar com middlewares RFID.
"""

from flask import Flask, request, jsonify
import json
import datetime
import os

app = Flask(__name__)
LOG_FILE = os.environ.get("LOG_FILE", "/tmp/rfid_requests.log")

# Códigos de barras RFID: 00392800010000#00001 até #00010
BARCODES = [f"00392800010000#{i:05d}" for i in range(1, 11)]


def ean13_to_sgtin96(ean13_no_check: str, serial: int) -> str:
    """
    Converte EAN-13 (sem dígito verificador) + serial para EPC SGTIN-96 (hex).
    Usa partition 6: Company Prefix 7 dígitos, Item Reference 6 dígitos.
    """
    # Header SGTIN-96
    header = 0x30  # 8 bits

    # Filter = 1 (POS item), Partition = 6
    filter_value = 1
    partition = 6
    filter_partition = (filter_value << 3) | partition  # 6 bits

    # Partition 6: Company Prefix 7 dígitos (30 bits), Item Reference 6 dígitos (24 bits)
    # EAN-13 sem check digit: 12 dígitos
    # Pega primeiros 7 como company prefix, próximos 5 como item reference
    company_prefix = int(ean13_no_check[:7])  # 7 dígitos
    item_ref = int(ean13_no_check[7:])        # 5 dígitos restantes

    # Serial: 38 bits
    serial_number = serial & 0x3FFFFFFFFF  # 38 bits max

    # Monta o SGTIN-96 (96 bits = 12 bytes = 24 hex chars)
    # Header (8) + Filter (3) + Partition (3) + CompanyPrefix (30) + ItemRef (24) + Serial (38)
    sgtin = (header << 88) | (filter_partition << 82) | (company_prefix << 52) | (item_ref << 38) | serial_number

    # Retorna como string hex uppercase, 24 caracteres
    return f"{sgtin:024X}"


def generate_rfid_tags() -> list:
    """Gera lista de 10 EPCs SGTIN-96 a partir dos códigos de barras."""
    tags = []
    for barcode in BARCODES:
        ean_part, serial_part = barcode.split("#")
        serial = int(serial_part)
        epc = ean13_to_sgtin96(ean_part, serial)
        tags.append(epc)
    return tags


def log(data: dict):
    entry = {"timestamp": datetime.datetime.now().isoformat(), **data}
    line = json.dumps(entry, ensure_ascii=False)
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def build_response(acao: str):
    now = datetime.datetime.now().isoformat()
    if acao == "ini":
        return jsonify({"status": "ok", "message": "Sessão iniciada",
                        "portal_id": 1, "session_id": "MOOUI-001", "timestamp": now})
    elif acao == "fin":
        return jsonify({"status": "ok", "message": "Sessão finalizada", "timestamp": now})
    elif acao == "cls":
        return jsonify({"status": "ok", "message": "Sessão limpa", "timestamp": now})
    elif acao == "lst":
        # 10 tags EPC SGTIN-96 geradas a partir dos códigos de barras 00392800010000#00001 a #00010
        tags = generate_rfid_tags()
        return jsonify({"status": "ok", "message": "Leitura realizada",
                        "tags": tags, "count": len(tags), "timestamp": now})
    elif acao == "lstcls":
        # Lista e fecha sessões anteriores — retorna lista vazia (sem sessões a fechar)
        return jsonify({"status": "ok", "sessions": [], "count": 0, "timestamp": now})
    elif acao == "read":
        # 10 tags EPC SGTIN-96 geradas a partir dos códigos de barras
        tags = generate_rfid_tags()
        return jsonify({"status": "ok", "message": "Leitura realizada",
                        "tags": tags, "count": len(tags), "timestamp": now})
    elif acao == "status":
        return jsonify({"status": "ok", "message": "Online", "timestamp": now})
    else:
        return jsonify({"status": "ok", "message": f"Acao '{acao}' recebida", "timestamp": now})


@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
@app.route("/<path:path>",             methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def catch_all(path):
    # Lê body como texto puro — sem tentar parsear JSON automaticamente
    body_raw = request.get_data(as_text=True) or None

    # Tenta parsear JSON manualmente, sem lançar exceção
    body_json = None
    try:
        if body_raw:
            body_json = json.loads(body_raw)
    except Exception:
        pass

    acao = (
        request.args.get("acao") or
        request.args.get("action") or
        request.args.get("cmd") or
        (body_json or {}).get("acao") or
        (body_json or {}).get("action") or
        "unknown"
    )

    log({
        "method":    request.method,
        "path":      f"/{path}",
        "acao":      acao,
        "args":      dict(request.args),
        "headers":   dict(request.headers),
        "body_raw":  body_raw,
        "body_json": body_json,
        "ip":        request.remote_addr,
    })

    return build_response(acao)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 9100))
    print(f"🔍 RFID Interceptor rodando na porta {port}")
    app.run(host="0.0.0.0", port=port, debug=False)