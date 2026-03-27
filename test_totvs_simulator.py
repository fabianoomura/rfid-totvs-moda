"""
test_totvs_simulator.py
Simula o comportamento do TOTVS criando os arquivos RFIDIniciar e RFIDParar
"""

import os
import time

RFID_DIR = r"C:\RFID"

def simular_totvs():
    print("=" * 60)
    print("SIMULADOR DE TOTVS - Criação de arquivos RFID")
    print("=" * 60)
    print()

    # Verifica diretório
    if not os.path.exists(RFID_DIR):
        print(f"ERRO: Diretório {RFID_DIR} não existe!")
        return

    print(f"Diretório: {RFID_DIR}")
    print()

    # Aguarda usuário iniciar o middleware
    input("1. Inicie o middleware GUI e clique em [INICIAR]\n   Pressione ENTER quando estiver pronto...")
    print()

    # Simula abertura do portal
    print(">>> Criando RFIDIniciar.txt (simulando abertura do portal)...")
    arquivo_iniciar = os.path.join(RFID_DIR, "RFIDIniciar.txt")

    with open(arquivo_iniciar, "w") as f:
        f.write("")  # Arquivo vazio

    print(f"✓ Arquivo criado: {arquivo_iniciar}")
    print(f"  Tamanho: {os.path.getsize(arquivo_iniciar)} bytes")
    print()

    # Aguarda 3 segundos
    print("Aguardando 3 segundos...")
    time.sleep(3)

    # Verifica se ListaTagtxt.txt foi criado
    arquivo_tags = os.path.join(RFID_DIR, "ListaTagtxt.txt")
    if os.path.exists(arquivo_tags):
        print(f"✓ ListaTagtxt.txt FOI CRIADO pelo middleware!")
        print(f"  Tamanho: {os.path.getsize(arquivo_tags)} bytes")

        # Mostra as primeiras 3 linhas
        with open(arquivo_tags, "r") as f:
            linhas = f.readlines()
            print(f"  Total de tags: {len(linhas)}")
            print("  Primeiras 3 tags:")
            for i, linha in enumerate(linhas[:3], 1):
                print(f"    {i}. {linha.strip()}")
    else:
        print("✗ ListaTagtxt.txt NÃO foi criado!")
        print("  O middleware pode não estar rodando ou há um problema.")

    print()
    input("Pressione ENTER para simular fechamento do portal...")
    print()

    # Simula fechamento do portal
    print(">>> Criando RFIDParar.txt (simulando fechamento do portal)...")
    arquivo_parar = os.path.join(RFID_DIR, "RFIDParar.txt")

    with open(arquivo_parar, "w") as f:
        f.write("")

    print(f"✓ Arquivo criado: {arquivo_parar}")
    print(f"  Tamanho: {os.path.getsize(arquivo_parar)} bytes")
    print()

    # Lista todos os arquivos
    print("Arquivos atuais em C:\\RFID:")
    for item in os.listdir(RFID_DIR):
        caminho = os.path.join(RFID_DIR, item)
        if os.path.isfile(caminho):
            print(f"  - {item} ({os.path.getsize(caminho)} bytes)")

    print()
    print("=" * 60)
    print("Teste concluído!")
    print("=" * 60)


if __name__ == "__main__":
    simular_totvs()
