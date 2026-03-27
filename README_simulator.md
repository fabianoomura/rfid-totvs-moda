# RFID Middleware Simulator

Simulador de middleware RFID para integração com TOTVS via protocolo baseado em arquivos.

## Como funciona

O TOTVS usa um protocolo de comunicação baseado em **arquivos** no diretório `C:\RFID`:

1. **Portal TOTVS inicia** → cria `RFIDIniciar.txt`
2. **Middleware detecta** o arquivo e atualiza status para "Portal Aberto"
3. **Portal TOTVS finaliza** → cria `RFIDParar.txt`
4. **Middleware detecta** e cria `ListaTagtxt.txt` com as tags RFID
5. **Portal TOTVS lê** as tags do arquivo `ListaTagtxt.txt`

**IMPORTANTE**: O arquivo `ListaTagtxt.txt` é criado APÓS o fechamento do portal (depois de `RFIDParar.txt`), não na abertura.

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

### Interface Gráfica

Execute o middleware usando o launcher:

```bash
start_gui.bat
```

Ou diretamente via Python:

```bash
python rfid_middleware_gui.py
```

A interface gráfica oferece:
- Visualização em tempo real das 32 tags SGTIN-96
- Status visual do middleware e portal TOTVS
- Log de eventos colorido
- Botões para iniciar/parar o middleware
- Botão de teste para simular o fluxo completo

### Fluxo de trabalho

1. **Clique em [INICIAR]** no middleware
2. **Abra o Portal RFID no TOTVS** (cria `RFIDIniciar.txt`)
3. **Feche o Portal no TOTVS** (cria `RFIDParar.txt`)
4. **Middleware cria automaticamente** `ListaTagtxt.txt` com as tags
5. **TOTVS lê** as tags do arquivo

## Tags RFID

O middleware utiliza 32 tags EPC SGTIN-96 pré-validadas armazenadas em `data/tags_template.txt`:

```
303B0286800520C000000001
303B028680051D4000000001
303B0286800520C000000001
303B0286800520C000000002
...
(32 tags no total)
```

Estas tags foram testadas e validadas com o sistema TOTVS.

## Estrutura de arquivos

```
rfid_web/
├── data/
│   └── tags_template.txt         # Template com 32 tags validadas
├── rfid_middleware_gui.py        # Aplicação principal
├── test_totvs_simulator.py       # Utilitário de teste
├── start_gui.bat                 # Launcher Windows
└── requirements_simulator.txt    # Dependências Python

C:\RFID/                          # Diretório monitorado
├── RFIDIniciar.txt               # Criado pelo TOTVS - abertura do portal
├── RFIDParar.txt                 # Criado pelo TOTVS - fechamento do portal
└── ListaTagtxt.txt               # Criado pelo middleware - lista de tags
```

## Teste sem TOTVS

Para testar o fluxo sem o TOTVS instalado:

1. Inicie o middleware GUI e clique em **[INICIAR]**
2. Execute `python test_totvs_simulator.py` em outro terminal
3. Siga as instruções interativas do simulador

Ou use o botão **[TESTAR]** na interface gráfica.

## Troubleshooting

### O TOTVS não encontra as tags

1. Verifique se `C:\RFID\ListaTagtxt.txt` existe
2. Verifique o formato das tags (24 caracteres hex por linha)
3. Verifique as permissões do diretório `C:\RFID`
4. Certifique-se de que o portal foi **fechado** antes de procurar pelas tags

### O middleware não cria o arquivo de tags

1. Confirme que o middleware está com status "Online"
2. Verifique se o arquivo `data/tags_template.txt` existe
3. Certifique-se de que `RFIDParar.txt` foi criado (portal fechado)
4. Verifique os logs na interface gráfica

### O middleware não detecta os arquivos

1. Confirme que o TOTVS está configurado para usar `C:\RFID`
2. Verifique se o middleware tem permissão de leitura/escrita no diretório
3. Reinicie o middleware e tente novamente

## Desenvolvimento

Para modificar as tags utilizadas, edite o arquivo `data/tags_template.txt` mantendo o formato de 24 caracteres hexadecimais por linha (SGTIN-96).
