"""
rfid_middleware_simulator.py — MOOUI
Simulador de middleware RFID que monitora C:\RFID e responde aos comandos do TOTVS.

Fluxo:
1. TOTVS cria RFIDIniciar.txt → Middleware cria ListaTagtxt.txt com tags
2. TOTVS cria RFIDParar.txt → Middleware para de atualizar
"""

import os
import time
import glob
from pathlib import Path
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
    """
    Converte EAN-13 (sem dígito verificador) + serial para EPC SGTIN-96 (hex).
    Usa partition 6: Company Prefix 7 dígitos, Item Reference 5 dígitos.
    """
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
    """Gera lista de 10 EPCs SGTIN-96 a partir dos códigos de barras."""
    tags = []
    for barcode in BARCODES:
        ean_part, serial_part = barcode.split("#")
        serial = int(serial_part)
        epc = ean13_to_sgtin96(ean_part, serial)
        tags.append(epc)
    return tags


def limpar_arquivos_txt():
    """Remove todos os arquivos .txt do diretório RFID ao iniciar o middleware."""
    print(f"🧹 Limpando arquivos .txt em {RFID_DIR}...")
    arquivos = glob.glob(os.path.join(RFID_DIR, "*.txt"))
    for arquivo in arquivos:
        try:
            os.remove(arquivo)
            print(f"   ✓ Removido: {os.path.basename(arquivo)}")
        except Exception as e:
            print(f"   ✗ Erro ao remover {arquivo}: {e}")


def criar_lista_tags():
    """Cria o arquivo ListaTagtxt.txt com as tags RFID."""
    tags = generate_rfid_tags()
    caminho_tags = os.path.join(RFID_DIR, ARQUIVO_TAGS)

    try:
        with open(caminho_tags, "w", encoding="utf-8") as f:
            for tag in tags:
                f.write(tag + "\n")
        print(f"📝 Arquivo {ARQUIVO_TAGS} criado com {len(tags)} tags")
        return True
    except Exception as e:
        print(f"❌ Erro ao criar {ARQUIVO_TAGS}: {e}")
        return False


class RFIDEventHandler(FileSystemEventHandler):
    """Monitora a criação de RFIDIniciar.txt e RFIDParar.txt"""

    def __init__(self):
        self.ativo = False

    def on_created(self, event):
        if event.is_directory:
            return

        nome_arquivo = os.path.basename(event.src_path)

        if nome_arquivo == ARQUIVO_INICIAR:
            print(f"\n🟢 Portal TOTVS INICIOU (detectado {ARQUIVO_INICIAR})")
            if not self.ativo:
                self.ativo = True
                criar_lista_tags()
            else:
                print(f"   ⚠️  Middleware já estava ativo")

        elif nome_arquivo == ARQUIVO_PARAR:
            print(f"\n🔴 Portal TOTVS PAROU (detectado {ARQUIVO_PARAR})")
            if self.ativo:
                self.ativo = False
                print(f"   ✓ Middleware desativado (arquivo {ARQUIVO_TAGS} mantido)")
            else:
                print(f"   ⚠️  Middleware já estava inativo")


def main():
    print("=" * 60)
    print("🔍 RFID Middleware Simulator — MOOUI")
    print("=" * 60)
    print(f"Monitorando diretório: {RFID_DIR}")
    print(f"Aguardando criação de: {ARQUIVO_INICIAR}")
    print(f"Parada detectada por: {ARQUIVO_PARAR}")
    print("=" * 60)

    # Garante que o diretório existe
    Path(RFID_DIR).mkdir(parents=True, exist_ok=True)

    # Limpa arquivos .txt ao iniciar
    limpar_arquivos_txt()

    # Configura o observador de arquivos
    event_handler = RFIDEventHandler()
    observer = Observer()
    observer.schedule(event_handler, RFID_DIR, recursive=False)
    observer.start()

    print(f"\n✓ Middleware simulador ATIVO")
    print(f"  Pressione Ctrl+C para parar\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Parando middleware...")
        observer.stop()

    observer.join()
    print("✓ Middleware parado")


if __name__ == "__main__":
    main()
