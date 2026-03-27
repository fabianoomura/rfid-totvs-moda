# RFID Middleware Simulator

Simulador de middleware RFID para integração com portal TOTVS (indústria de moda/confecção).

## Como funciona

O TOTVS usa um protocolo de comunicação baseado em **arquivos** no diretório `C:\RFID`:

1. **Portal TOTVS inicia** → cria `RFIDIniciar.txt`
2. **Middleware detecta** e atualiza status para "Portal Aberto"
3. **Portal TOTVS finaliza** → cria `RFIDParar.txt`
4. **Middleware detecta** e copia `data/tags_template.txt` → `C:\RFID\ListaTagtxt.txt`
5. **TOTVS lê** as tags RFID do arquivo

**IMPORTANTE**:
- O arquivo `ListaTagtxt.txt` é criado APÓS o fechamento do portal (depois de `RFIDParar.txt`)
- Cada tag RFID é um código único (SGTIN-96) que identifica uma peça específica
- O middleware NÃO gera tags - ele copia as tags pré-cadastradas do template

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

### Recursos da interface:

- ✓ Visualização das 32 tags RFID em tempo real
- ✓ Status do middleware (Online/Offline) e portal (Aberto/Fechado)
- ✓ Log de eventos com código de cores
- ✓ Controles: [INICIAR], [PARAR], [LIMPAR], [TESTAR]
- ✓ Tema dark industrial com fonte monospace

### Fluxo de trabalho

1. **Execute** `start_gui.bat` e clique em **[INICIAR]**
2. **Abra o Portal RFID no TOTVS** → cria `RFIDIniciar.txt`
3. **Middleware detecta** e atualiza status para "Portal Aberto"
4. **Feche o Portal no TOTVS** → cria `RFIDParar.txt`
5. **Middleware detecta** e copia tags para `ListaTagtxt.txt`
6. **TOTVS lê** as 32 tags do arquivo e processa as peças

## Tags RFID

Cada tag RFID é um **código único** no formato EPC SGTIN-96 que identifica uma peça/produto específico.

O arquivo `data/tags_template.txt` contém 32 tags reais validadas:

```
303B0286800520C000000001
303B028680051D4000000001
303B0286800520C000000001
303B0286800520C000000002
...
(32 tags reais testadas)
```

**Importante sobre tags RFID:**
- Cada tag é um identificador único mundial (como um CPF para produtos)
- Tags RFID não podem ser duplicadas - cada código existe apenas uma vez
- O middleware copia estas tags do template para simular leitura de etiquetas reais
- Em produção, estas tags seriam lidas por antenas RFID físicas

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

### Modificando as tags do simulador

Para utilizar diferentes tags RFID no simulador:

1. Edite o arquivo `data/tags_template.txt`
2. Mantenha o formato: **24 caracteres hexadecimais por linha** (SGTIN-96)
3. Cada linha representa uma tag RFID única
4. Recomendado: usar tags reais já validadas com o TOTVS

**Formato SGTIN-96:**
- Header (2 hex) + Filtro/Partição (2 hex) + Company Prefix (10 hex) + Item Ref (10 hex)
- Exemplo: `303B0286800520C000000001`

### Sobre a arquitetura

- **rfid_middleware_gui.py**: Interface gráfica principal com watchdog para monitoramento
- **data/tags_template.txt**: Template com tags RFID pré-validadas (fonte de verdade)
- **test_totvs_simulator.py**: Utilitário para simular comportamento do portal TOTVS
- **start_gui.bat**: Launcher conveniente para Windows
