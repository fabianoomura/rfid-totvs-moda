# RFID Interceptor — MOOUI

Servidor que captura e loga TUDO que o TOTVS manda,
para descobrir o protocolo dos middlewares RFID.

## Deploy rápido (Railway)

1. Suba os arquivos para um repo GitHub
2. railway.app → New Project → Deploy from GitHub
3. Copie a URL gerada (ex: https://rfid-mooui.up.railway.app)

## Ou rodar local com ngrok

```bash
pip install flask
python rfid_interceptor.py
# em outro terminal:
ngrok http 9100
# copie a URL https://xxxx.ngrok.io
```

## Configurar no TOTVS (GERFM107)

- Tipo leitura RFID: qualquer um (Monitor, Virtual Age, etc.)
- Caminho: URL do deploy (ex: https://rfid-mooui.up.railway.app)

## O que vai aparecer no log (rfid_requests.log)

```json
{
  "timestamp": "2026-02-18T10:00:00",
  "method": "GET",
  "path": "/ProjetoSiteRFID/WEB-COMP/servlet/home.jsp",
  "acao": "ini",
  "args": {"acao": "ini", "ident": "1"},
  "headers": {...},
  "body_json": null,
  "ip": "189.x.x.x"
}
```

## O que analisar

- path → qual URL o TOTVS chama
- acao → quais ações (ini, fin, read, status...)
- args → parâmetros enviados
- body_json → se manda POST com body
- Testar cada Tipo de leitura RFID e comparar os logs
