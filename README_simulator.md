# RFID Middleware Simulator

Simulador de middleware RFID para integração com TOTVS via protocolo baseado em arquivos.

## Como funciona

O TOTVS usa um protocolo de comunicação baseado em **arquivos** no diretório `C:\RFID`:

1. **Portal TOTVS inicia** → cria `RFIDIniciar.txt`
2. **Middleware detecta** o arquivo e cria `ListaTagtxt.txt` com as tags RFID
3. **Portal TOTVS lê** as tags do arquivo `ListaTagtxt.txt`
4. **Portal TOTVS finaliza** → cria `RFIDParar.txt`
5. **Middleware detecta** e para de atualizar

## Configuração no TOTVS

No cadastro **ADMFM013** (Configuração de Portal RFID):

- **DS_CAMINHO_RFID**: `C:\RFID`
- **TP_VALIDA_SEQUENCIAL_RFID**: `1`

## Instalação

```bash
# Instalar dependências
pip install -r requirements_simulator.txt
```

## Uso

### Opção 1: Interface Gráfica (Recomendado)

```bash
python rfid_middleware_gui.py
```

A interface gráfica oferece:
- ✅ Visualização em tempo real das 10 tags geradas
- ✅ Status visual do middleware e portal TOTVS
- ✅ Log de eventos colorido e scrollable
- ✅ Botões para iniciar/parar o middleware
- ✅ Limpeza de logs com um clique

![Screenshot da GUI](https://via.placeholder.com/600x400?text=RFID+Middleware+GUI)

### Opção 2: Linha de Comando

1. **Inicie o simulador**:
   ```bash
   python rfid_middleware_simulator.py
   ```

2. O simulador vai:
   - Limpar todos os arquivos `.txt` em `C:\RFID`
   - Monitorar continuamente o diretório
   - Esperar pela criação de `RFIDIniciar.txt`

3. **Abra o Portal RFID no TOTVS** (ele vai criar `RFIDIniciar.txt`)

4. O simulador detecta e cria `ListaTagtxt.txt` com 10 tags:
   ```
   303800099709C40000000001
   303800099709C40000000002
   ...
   303800099709C4000000000A
   ```

5. **Feche o Portal no TOTVS** (ele vai criar `RFIDParar.txt`)

6. O simulador detecta e para de atualizar

## Tags geradas

O simulador gera 10 tags EPC SGTIN-96 baseadas nos códigos de barras:

```
00392800010000#00001 → 303800099709C40000000001
00392800010000#00002 → 303800099709C40000000002
...
00392800010000#00010 → 303800099709C4000000000A
```

### Formato SGTIN-96

- **Header**: `0x30` (SGTIN-96)
- **Filter**: `1` (POS item)
- **Partition**: `6` (Company Prefix 7 dígitos, Item Reference 5 dígitos)
- **Company Prefix**: `0039280`
- **Item Reference**: `00100`
- **Serial**: `1` a `10`

## Estrutura de arquivos

```
C:\RFID\
├── RFIDIniciar.txt      (criado pelo TOTVS - flag de início)
├── RFIDParar.txt        (criado pelo TOTVS - flag de parada)
└── ListaTagtxt.txt      (criado pelo middleware - lista de tags)
```

## Logs

O simulador exibe logs em tempo real:

```
🟢 Portal TOTVS INICIOU (detectado RFIDIniciar.txt)
📝 Arquivo ListaTagtxt.txt criado com 10 tags

🔴 Portal TOTVS PAROU (detectado RFIDParar.txt)
✓ Middleware desativado
```

## Troubleshooting

### O TOTVS não encontra as tags

1. Verifique se `C:\RFID\ListaTagtxt.txt` existe
2. Verifique o formato das tags (24 caracteres hex por linha)
3. Verifique as permissões do diretório `C:\RFID`

### O simulador não detecta os arquivos

1. Confirme que o TOTVS está configurado para usar `C:\RFID`
2. Verifique se o simulador tem permissão de leitura no diretório
3. Reinicie o simulador e tente novamente

## Desenvolvimento

Para modificar as tags geradas, edite a função `generate_rfid_tags()` em `rfid_middleware_simulator.py`.
