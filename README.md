# RIF Analyst 3.6

Aplicação **Streamlit** para análise de Relatórios de Inteligência Financeira (RIF), com foco em detecção de padrões suspeitos, análise de redes de relacionamento, extração automática de narrativas e integração com fontes de dados abertas.

## ✨ Principais Funcionalidades

-   **Processamento de Dados COAF:** Carregamento e consolidação de arquivos de comunicações, envolvidos e ocorrências.
-   **Detecção de Padrões Suspeitos:** Identificação automática de mais de 15 padrões de risco, como fracionamento de operações, movimentação atípica e transações em zonas de risco.
-   **Análise de Redes de Relacionamento:** Visualização interativa de redes de relacionamento entre envolvidos, permitindo a identificação de conexões e comunidades.
-   **Extração e Análise de Narrativas:** Processamento do campo "Informações Adicionais" para extrair de forma estruturada dados de KYC, movimentação financeira, contrapartes e riscos.
-   **Análise com IA Local (Ollama):** Integração com o Ollama para permitir a análise de narrativas usando modelos de linguagem locais, garantindo a privacidade dos dados.
-   **Diagramas de Fluxo (Sankey):** Visualização estruturada do fluxo financeiro (origem e destino dos recursos) com base nos papéis da comunicação e na extração automática textual.
-   **Integração com o Portal da Transparência:** Cruzamento de dados de envolvidos com pagamentos registrados no Portal da Transparência do Governo Federal.
-   **Análise de Trilhas da DIE:** Módulo para análise de planilhas de Detalhamento de Indícios de Irregularidades (DIE), com visualização de redes e cruzamento de informações.
-   **Interface Web Interativa:** Construído com Streamlit para oferecer uma experiência de análise rica, com dashboards, filtros dinâmicos e métricas detalhadas.

## 🧭 Abas da Aplicação

A aplicação é organizada nas seguintes abas, cada uma com um propósito específico:

### 📊 Análise Geral

Esta aba fornece uma visão macro dos dados carregados e filtrados. Ideal para entender o escopo geral do RIF.
-   **Métricas Principais:** Quantidade de comunicações, envolvidos únicos, tipos de ocorrências e valor total movimentado.
-   **Distribuições:** Gráficos e tabelas que mostram a distribuição de comunicações por tipo de ocorrência, segmento de mercado e cidade/UF da agência.
-   **Evolução Temporal:** Gráfico de linhas que exibe o volume de comunicações ao longo do tempo.
-   **Rankings Rápidos:** Listas com os principais envolvidos, remetentes e beneficiários, tanto por quantidade de comunicações quanto por valor.
-   **Análise de Fraude:** Inclui uma análise pela Lei de Benford para detectar anomalias nos valores das transações.
-   **Detalhamento de Espécie:** Foco em transações que envolvem dinheiro em espécie, com rankings de depositantes e sacadores.

### 🏆 Ranking de Envolvidos

O coração da análise de risco individual. Esta aba calcula um **Score de Risco** para cada envolvido, ajudando a priorizar a investigação.
-   **Tabela de Risco:** Classifica todos os envolvidos pelo Score de Risco, exibindo métricas como quantidade de comunicações, valor total e número de alertas.
-   **Detalhamento do Envolvido:** Ao selecionar um envolvido na tabela, a aba exibe um dossiê completo, incluindo:
    -   Suas comunicações vinculadas.
    -   Padrões suspeitos específicos detectados para ele.
    -   Análise de compatibilidade financeira (movimentação vs. renda/faturamento declarado).
    -   Visualização da sua rede de relacionamentos direta e expandida.
    -   Diagrama de fluxo (Sankey) mostrando suas principais contrapartes.

### 💬 Ranking de Comunicações

Esta aba foca na análise das comunicações em si, permitindo identificar as mais relevantes.
-   **Tabela de Ranking:** Classifica as comunicações por critérios como valor total, quantidade de envolvidos, e presença de indicadores de risco (PEP, movimentação em espécie, etc.).
-   **Detalhamento da Comunicação:** Ao selecionar uma comunicação, a aplicação exibe todos os seus detalhes:
    -   Informações do comunicante, valores e ocorrências.
    -   Lista de todos os envolvidos na comunicação.
    -   **Análise da Narrativa:** Extrai e exibe de forma estruturada as informações do campo "Informações Adicionais", incluindo análise de termos, resumo do fluxo financeiro e um dossiê do perfil (KYC).
    -   **Análise por IA Local:** Permite acionar o Ollama para gerar uma análise estruturada da narrativa, extraindo suspeitas, vínculos de risco e um resumo técnico.

### 🔍 Portal da Transparência

Módulo de enriquecimento de dados que cruza as informações dos envolvidos no RIF com dados públicos de pagamentos do Governo Federal.
-   **Busca por Envolvido:** Selecione um envolvido para buscar pagamentos que ele tenha recebido.
-   **Resumo de Pagamentos:** Exibe o valor total recebido e um resumo por ano.
-   **Linha do Tempo:** Apresenta um gráfico que compara a data dos pagamentos recebidos com as datas das comunicações do RIF, facilitando a identificação de nexos temporais.

### 🗺️ Trilhas da DIE

Ferramenta dedicada à análise de planilhas da dados complementares da Diretoria de Informações Estratégicas (DIE), geralmente em formato Excel.
-   **Filtros de Alvos e Comunicações:** Permite focar a análise em pessoas ou comunicações específicas.
-   **Rede de Vínculos:** Gera uma rede interativa que conecta pessoas, empresas e comunicações, ajudando a visualizar relacionamentos complexos.
-   **Exploração de Dados:** Apresenta os dados brutos de cada trilha (aba da planilha), com resumos e gráficos específicos para temas como Recursos Federais e Emendas Parlamentares.

## 🏗 Estrutura do Projeto

```
rif_analyst/
├── __init__.py
├── config.py
├── main.py
├── rifanalyst.bat
├── excel_loader.py
├── narrativa.py
├── trilhas_die_tab.py
│
├── core/
│   ├── data_loader.py
│   └── data_processor.py
│
├── parsers/
│   ├── narrative_parser.py
│   └── narrative_analyzer.py
│
├── analytics/
│   ├── patterns.py
│   ├── indicators.py
│   └── network.py
│
├── visualizations/
│   ├── charts.py
│   ├── networks.py
│   └── sankey.py
│
├── integrations/
│   ├── local_ai.py
│   └── portal_transparencia.py
│
└── project_utils/
    ├── helpers.py
    └── security.py
```

## 📦 Requisitos

Dependências principais (ver `requirements.txt` para lista completa).

- Python 3.10+
- streamlit
- pandas, numpy
- plotly, pyvis
- networkx, python-louvain
- requests, wordcloud
- openpyxl, xlrd

Instalação:

```bash
pip install -r requirements.txt
```

## 🔧 Configuração

### Portal da Transparência
Para usar a integração com o Portal da Transparência, é necessário um token de API.

```bash
# Linux/macOS
export PORTAL_TRANSPARENCIA_TOKEN="seu_token_aqui"

# Windows (PowerShell)
$env:PORTAL_TRANSPARENCIA_TOKEN="seu_token_aqui"
```

Ou, preferencialmente, via `.streamlit/secrets.toml` no diretório do projeto:

```toml
portal_transparencia_token = "seu_token_aqui"
```

### Análise com IA Local (Ollama)
Para usar a análise de narrativas com IA, é necessário ter o [Ollama](https://ollama.com/) instalado e em execução na máquina local. O modelo utilizado (`phi3:3.8b`) será baixado automaticamente no primeiro uso.

## ▶️ Execução Local

**Para usuários do Windows:**
Basta executar (duplo clique) o script `rifanalyst.bat`. Ele verificará e instalará as dependências automaticamente e iniciará a aplicação.

**Para usuários de Linux/macOS ou inicialização manual:**
Dentro da pasta do projeto, execute:

```bash
streamlit run main.py
```

A aplicação abrirá no navegador padrão (ex.: `http://localhost:8501`).

## 🔒 Segurança e Privacidade

- **Processamento Local:** A aplicação foi desenhada para rodar localmente, sem envio de dados sensíveis para APIs externas (com exceção do Portal da Transparência, que apenas envia o CPF/CNPJ para consulta pública). Isso garante a conformidade com sigilo bancário e LGPD.
- **Análise de IA Privada:** A integração com Ollama garante que as narrativas são processadas na máquina local, sem exposição a serviços de nuvem.
- **Gerenciamento de Sessão:** O módulo `project_utils/security.py` implementa controle de sessão com timeout automático e limpeza de dados para minimizar riscos em ambientes compartilhados.
- **Credenciais:** Tokens e outras credenciais devem ser sempre configurados via variáveis de ambiente ou pelo `secrets.toml` do Streamlit, nunca diretamente no código.

## 👥 Autoria e Contato

- **Autor/pacote:** NAE/CGU/SC – RIF Analyst.
- **Público-alvo:** Times de inteligência financeira, auditoria, controle interno e investigação de PLD/FT.
- **Sugestões e Issues:** Use a aba “Issues” do repositório ou o canal interno definido pela equipe.
