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
    elif acao == "read":
        return jsonify({"status": "ok", "message": "Leitura realizada",
                        "tags": [], "count": 0, "timestamp": now})
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