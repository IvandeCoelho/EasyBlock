# EasyBlock

**Bloqueie distrações. Tenha mais controle sobre o uso do computador.**

O **EasyBlock** é um aplicativo para Windows 10 e Windows 11 que permite bloquear sites, aplicativos, jogos e termos definidos pelo usuário. Ele pode utilizar listas online e, na versão completa, também permite criar regras locais, configurar horários e limites de uso e consultar o histórico de bloqueios.

> **Baixe o EasyBlock:** acesse a página oficial de [Releases](https://github.com/IvandeCoelho/EasyBlock/releases).

## Versões disponíveis

| Recurso                                          | EasyBlock (completa) |     EasyBlock Lite      |
| ------------------------------------------------ | :------------------: | :---------------------: |
| Bloqueio por lista online                        |          ✅          |           ✅            |
| Listas locais personalizadas                     |          ✅          |           ❌            |
| Bloqueio de sites                                |          ✅          |           ✅            |
| Bloqueio de aplicativos e jogos                  |          ✅          | Conforme a lista online |
| Bloqueio por termos                              |          ✅          | Conforme a lista online |
| Abas específicas para sites, apps/jogos e termos |          ✅          |           ❌            |
| Limites de uso                                   |          ✅          |           ❌            |
| Agenda por horário                               |          ✅          |           ❌            |
| Histórico de bloqueios                           |          ✅          |           ❌            |
| Gerenciamento de várias listas online            |          ✅          |           ✅            |
| Senha e código de recuperação                    |          ✅          |           ✅            |
| Inicialização com o Windows                      |          ✅          |           ✅            |
| Instalador                                       |          ✅          |           ❌            |

**Qual versão escolher?**

- **EasyBlock:** para quem precisa personalizar regras, gerenciar listas locais, definir limites e horários e consultar o histórico.
- **EasyBlock Lite:** para quem deseja aplicar listas online com uma configuração mais simples.

## Capturas de tela

### Tela principal e Configurações

| EasyBlock Lite — bloqueio online                                   | Configurações                              |
| ------------------------------------------------------------------ | ------------------------------------------ |
| ![Bloqueio online da versão Lite](docs/img/LiteBloqueioOnline.png) | ![Configuração](docs/img/Configuração.png) |

### Sites, aplicativos, jogos e termos

| Bloqueio de Sites                             | Bloqueio de App e Jogos                                        | Bloqueio de Termos                              |
| --------------------------------------------- | -------------------------------------------------------------- | ----------------------------------------------- |
| ![Gerenciamento de sites](docs/img/Sites.png) | ![Gerenciamento de aplicativos e jogos](docs/img/JogosApp.png) | ![Gerenciamento de termos](docs/img/Termos.png) |

### Agenda, limites de uso e Histórico de bloqueios

| Agenda                         | Limites                                 | Histórico de bloqueios                                    |
| ------------------------------ | --------------------------------------- | --------------------------------------------------------- |
| ![Agenda](docs/img/Agenda.png) | ![Limites de uso](docs/img/Limites.png) | ![Histórico de bloqueios](docs/img/HistoricoBloqueio.png) |

### Sobre e apoio ao projeto

| Sobre EasyBlock                          | Sobre EasyBlock Lite                            | Apoie o EasyBlock                      |
| ---------------------------------------- | ----------------------------------------------- | -------------------------------------- |
| ![Sobre o EasyBlock](docs/img/Sobre.png) | ![Sobre EasyBlock Lite](docs/img/SobreLite.png) | ![Apoie o projeto](docs/img/Apoie.png) |

### Editor de listas

| Tema claro                                                                    | Tema escuro                                                                   |
| ----------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| ![Editor de listas no tema claro](docs/img/LightEditorDeListaDoEasyBlock.png) | ![Editor de listas no tema escuro](docs/img/DarkEditorDeListaDoEasyBlock.png) |

## Releases e downloads

Os executáveis e instaladores publicados estão disponíveis na página de versões do projeto:

**[Acessar Releases do EasyBlock](https://github.com/IvandeCoelho/EasyBlock/releases)**

Na página de Releases, escolha a versão desejada e baixe o arquivo correspondente aos recursos que você precisa. Os nomes dos arquivos podem variar conforme a versão publicada.

- **Versão completa:** procure o instalador `EasyBlock-Setup-x.y.z.exe`, quando disponibilizado.
- **Versão Lite:** procure o executável `EasyBlock_Lite.exe`, quando disponibilizado.
- **Executável da versão completa:** `EasyBlock.exe`, quando disponibilizado.

Consulte as notas de cada release para verificar novidades, correções e alterações da versão.

## Como instalar e executar

1. Acesse a página de [Releases](https://github.com/IvandeCoelho/EasyBlock/releases).
2. Baixe o instalador ou executável da versão desejada.
3. Execute o aplicativo **como administrador**. Essa permissão é necessária para que o EasyBlock possa aplicar o bloqueio de sites por meio do arquivo `hosts` do Windows.
4. Na primeira execução, o aplicativo baixa a lista padrão online.

**Atenção:** o Windows ou o antivírus pode exibir um aviso para executáveis novos ou sem assinatura digital. Para reduzir riscos, baixe os arquivos somente pela página oficial de Releases deste repositório.

## Como funciona

- **Sites:** o EasyBlock registra os domínios no arquivo `C:\Windows\System32\drivers\etc\hosts`, direcionando-os para `127.0.0.1`, e limpa o cache DNS.
- **Aplicativos e jogos:** enquanto o aplicativo está em execução, encerra processos correspondentes aos nomes configurados, como `steam.exe`.
- **Termos:** identifica processos ou títulos de janelas que contenham os termos configurados e encerra o processo ou fecha a janela conforme o mecanismo implementado.
- **Listas online:** baixa listas de texto hospedadas no GitHub ou em outra URL HTTPS cadastrada. O intervalo de sincronização pode ser configurado de 5 minutos a 24 horas.
- **Itens ignorados:** permite ignorar um item localmente sem removê-lo da lista online. Quando a proteção por senha está ativada, ignorar ou restaurar itens exige autenticação.

### Pausar ou fechar o aplicativo

- Ao **pausar** o bloqueio, os sites são removidos imediatamente do arquivo `hosts`.
- Ao **fechar** o aplicativo com o bloqueio ativo, os sites permanecem registrados no `hosts`.
- Os bloqueios de aplicativos e termos dependem do aplicativo estar em execução; eles deixam de ser aplicados quando o programa é encerrado.

## Formato das listas online

As listas podem ser arquivos de texto UTF-8 organizados por seções:

```text
# Comentários começam com #

[sites]
bet365.com
www.exemplo.com.br

[apps]
steam.exe
RiotClientServices.exe

[termos]
jogo
```

Também é aceito o formato JSON:

```json
{
    "sites": ["exemplo.com"],
    "apps": ["steam.exe"],
    "terms": ["jogo"]
}
```

Um exemplo de lista está disponível em [`lists/lista_online_exemplo.txt`](lists/lista_online_exemplo.txt). Para editar uma lista sem escrever o arquivo manualmente, use [`tools/editor_lista.html`](tools/editor_lista.html).

## Segurança e proteção por senha

- **Senha:** protege ações como pausar o bloqueio, sair, ignorar itens e alterar configurações. A senha é armazenada como hash PBKDF2-SHA256 com 200 mil iterações, não em texto puro.
- **Código de recuperação:** é exibido uma única vez ao configurar a senha. Guarde-o em local seguro; ele é necessário para recuperar o acesso caso você esqueça a senha.
- **Assinatura de listas:** a versão completa oferece suporte a assinatura HMAC-SHA256 para ajudar a detectar alterações não autorizadas nas listas.

## Estrutura do repositório

```text
EasyBlock/
├── README.md
├── docs/img/                  capturas de tela
├── app/                       versão completa
│   ├── EasyBlock.py
│   ├── core.py
│   ├── ui_common.py
│   └── ui_tabs.py
├── lite/
│   └── EasyBlock_Lite.py
├── lists/
│   ├── default-list.txt       lista padrão (URL usada pelos apps)
│   └── lista_online_exemplo.txt
├── tools/
│   └── editor_lista.html
├── build/
│   ├── build.bat              gera os dois .exe
│   └── installer.iss          gera o instalador (Inno Setup 6)
├── version.json               manifesto de atualização da versão completa
└── version_lite.json          manifesto de atualização da versão lite
```

## Apoie o projeto

Se o EasyBlock ajudou você a reduzir distrações, economizar tempo ou evitar algumas dores de cabeça, considere apoiar a continuidade do projeto.

Toda contribuição é voluntária e ajuda a manter e aprimorar a ferramenta.

**Pix:** `ivandealveslp@gmail.com`

## Requisitos

- Windows 10 ou Windows 11.
- Permissão de administrador para aplicar os bloqueios que exigem alterações no sistema.
- Conexão com a internet para baixar e sincronizar listas online. Os bloqueios já aplicados no arquivo `hosts` podem continuar ativos sem conexão, mas a atualização da lista depende de acesso à internet.

## Compilar a partir do código-fonte

Para executar o projeto a partir do código-fonte, é necessário ter Windows 10/11 e Python 3.10 ou superior.

```bat
python -m pip install psutil
python app\EasyBlock.py
python lite\EasyBlock_Lite.py
```

Para gerar os executáveis, execute:

```bat
build\build.bat
```

O processo gera os executáveis em `dist\`, conforme a configuração do projeto. Para gerar o instalador da versão completa, compile `build\installer.iss` usando o [Inno Setup 6](https://jrsoftware.org/isinfo.php) após executar o script de build.

## Onde os dados são armazenados

- Configurações e histórico da versão completa: `%APPDATA%\Bloqueador`.
- Configurações da versão Lite: `%APPDATA%\BloqueadorLite`.
- Logs: `bloqueador.log` e `bloqueador_lite.log`, nas respectivas pastas de dados.

## Atualizações

Ao iniciar, o aplicativo consulta o manifesto de versão correspondente (`version.json` ou `version_lite.json`). Quando uma versão mais recente é identificada, a aba **Sobre** exibe um aviso e um link para download.

## Contribuições e sugestões

Sugestões, relatos de problemas e ideias para melhorias são bem-vindos. Abra uma [Issue](https://github.com/IvandeCoelho/EasyBlock/issues) no GitHub com uma descrição clara do problema ou da proposta.

## Autor

**Ivande Coelho** — [GitHub](https://github.com/IvandeCoelho)

## Licença

Este projeto é distribuído sob a licença [MIT](LICENSE).

Consulte o arquivo [`LICENSE`](LICENSE) para ler os termos completos da licença.
