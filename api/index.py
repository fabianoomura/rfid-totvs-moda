"""
Entrypoint para o Vercel (serverless Python).
O Vercel precisa de um módulo em api/ que exponha o objeto `app` do Flask.
"""

import sys
import os

# Adiciona o diretório raiz ao path para importar rfid_interceptor
root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

import rfid_interceptor

# No Vercel o filesystem é somente leitura; /tmp é gravável
rfid_interceptor.LOG_FILE = "/tmp/rfid_requests.log"

# Expõe o app Flask para o Vercel
app = rfid_interceptor.app