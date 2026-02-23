### Ajuda e Guia de Uso (Versão 3.2)

#### Como Usar

1. **Carga de dados:** Faça upload dos 3 arquivos CSV (`Ocorrencias`, `Envolvidos`, `Comunicacoes`) na barra lateral.
   
   **Formato Esperado:**
   
   - Arquivos CSV com separador `;`.
   - Datas em formato `DD/MM/AAAA`.
   - Valores numéricos em formato brasileiro (`1.234,56`) ou internacional (`1234.56`).

2. **Processamento Inteligente:** Clique em **"Processar Arquivos Carregados"**. O sistema interromperá a leitura automaticamente ao encontrar linhas em branco e realizará o "achatamento" dos dados financeiros para evitar inflação de valores por multiplicidade de ocorrências.

3. **Refinamento por Filtros:** Utilize a barra lateral para filtrar a análise por **Período**, **Ano/Mês** ou **Tipo de Ocorrência**. Todas as tabelas e gráficos serão recalculados instantaneamente com base na seleção.

4. **Detalhamento Integrado:** Ao clicar em uma linha na tabela do **Ranking de Envolvidos** ou **Ranking de Comunicações**, o detalhamento técnico completo será carregado logo abaixo na mesma aba.

5. **Exportação:** Gere relatórios em **Excel** contendo todos os dados filtrados e os rankings calculados.

**IMPORTANTE: Nenhuma informação pode ser usada em documentos externos.**



#### Descrição das Abas:

**📊Análise Geral:** Visão macro dos dados. Apresenta a **Evolução Temporal Real** (contagem por indexadores únicos), o **Ranking por Cidades** e o **Detalhamento de Movimentações em Espécie** mapeado por segmento.

- *Estatística:* Inclui a **Lei de Benford** para detecção de anomalias numéricas (indicado para amostras registros).

**🏆 Ranking de Envolvidos:** Placar de risco consolidado que une indicadores matemáticos (como concentração HHI e fracionamento temporal) com 17 padrões comportamentais suspeitos extraídos das narrativas.

**👤 Análise Individual Detalhada:** Dossiê exaustivo de um CPF/CNPJ, mostrando a força dos vínculos com contrapartes e o significado exato dos campos de valor para cada segmento.

**💬 Ranking de Comunicações:** Classificação dos RIFs por criticidade, complexidade e volume.

**🔎 Análise por Comunicação:** Detalhamento de um RIF específico, incluindo o **Grafo de Vínculos** interativo, a lista de envolvidos vinculados e o fluxo financeiro extraído via texto das informações adicionais.

**🌐 Análise de Rede Individual:** Mapa de conexões diretas para identificar comunidades financeiras e contas de passagem.



#### Destaques da Versão 3.2 (Melhorias e Bugs corrigidos)

**Integridade Financeira:** Os cálculos de volume financeiro utilizam o valor máximo por RIF (`max`), impedindo que o "Efeito Multiplicador" gere totais bilionários irreais.

**Detecção de Risco Booleana :** A identificação de PEPs e Servidores Públicos segue uma validação booleana estrita (`== True`), eliminando marcações incorretas em titulares que não possuem esses perfis.

**Fluxo Estruturado:** Diagramas de Sankey agora podem ser gerados com base nos papéis oficiais registrados (Remetente Titular Beneficiário), com filtros de legibilidade e agrupamento em nós "Outros" para facilitar a visualização de grandes redes.

**Segurança:** 

* Todos os dados carregados na memória são removidos ao encerrar a sessão. 

* Após 30 minutos de inatividade o sistema encerra automaticamente a sessão e elimina todos os dados carregados.



- ##### Segurança: Nunca processe dados sigilosos em LLMs abertas ou públicas.
  
   