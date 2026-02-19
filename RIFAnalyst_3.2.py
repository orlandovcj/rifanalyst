import pandas as pd
import numpy as np
import re
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go # <--- ADICIONE ESTA LINHA
import networkx as nx
from datetime import datetime
import community as community_louvain # Make sure 'pip install python-louvain' is installed
from pyvis.network import Network
import tempfile
from io import StringIO
from itertools import combinations, product
import unicodedata
import traceback # Para depuração de erros
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import string 
import io
import indicadores as rif_ind

# Mapeamento de CodigoSegmento para significado dos campos
#
SEGMENTO_MAP = {
    '17': "SPA - Loterias: A=Prêmio, B=Aposta(s)/Arrecadação, C=Qtd Premiações, D=Espécie",
    '19': "COAF - Jóias/Pedras/Metais: A=Valor Operação/Proposta, B=Pagamento(s) Espécie",
    '20': "COAF - Bingos: A=Prêmio, B=Aposta(s)/Arrecadação, C=Qtd Premiações",
    '22': "COAF - Bolsas Mercadorias: A=Valor Operação, B=Valor Pagamento(s)",
    '23': "IPHAN - Arte/Antiguidades: A=Valor Operação, B=Pagamento(s) Espécie",
    '24': "COFECI - Imóveis: A=Valor Imóvel, B=Valor Transação/Operação",
    '36': "COAF - Remessas Alternativas: A=Total, B=Transação(ões) Nacional(is), C=Transação(ões) Internacional(is)",
    '21': "COAF - Cartões Crédito: A=Valor Ocorrência(s)",
    '15': "COAF - Factoring: A=Valor Operação/Ativos Vendidos, B=Pago Espécie",
    '37': "SUSEP - Seguros: A=Valor Operação, B=Prêmio/Contribuição/Devolução, C=Quantidade",
    '42': "SFN - Espécie: A=Total, B=Crédito, C=Débito, D=Provisionamento, E=Proposta",
    '41': "SFN - Atípicas: A=Total, B=Crédito, C=Débito, D=Provisionamento, E=Proposta",
    '43': "PREVIC - Previdência Comp.: A=Valor Operação/Contribuição",
    '44': "CVM - Valores Mobiliários: A=Valor",
    '45': "PF - Transporte Valores: A=Valor Transportado, B=Valor Guardado/Custodiado, C=Proposta",
    '46': "Outros Lei 9.613/98: A=Valor total, B=Pago Espécie",
    '47': "Registros Públicos: A=Valor",
    '48': "COAF - Assessoria/Consultoria: A=Valor total, B=Pago Espécie",
    '49': "COAF - Atletas/Artistas: A=Valor total, B=Pago Espécie",
    '50': "Feiras/Exposições: A=Valor",
    '51': "Bens Rurais/Animal Alto Valor: A=Valor total, B=Pago Espécie",
    '52': "COAF - Bens Luxo/Alto Valor: A=Valor total, B=Pago Espécie",
    '53': "DREI - Juntas Comerciais: A=Valor",
    '54': "CFC - Contador: A=Valor",
    '55': "COFECON - Economista: A=Valor",
    '56': "ANS - Planos Saúde: A=Valor",
    '57': "OUTRAS PESSOAS OBRIGADAS: A=Transação(ões) Nacional(is), B=Transação(ões) Internacional(is)",
    '58': "CNJ - Notários/Registradores: A=Valor Operação(ões)",
    '59': "ANM - Mineração: A=Valor Operação(ões)",
    '60': "Lottopar - Aposta Quota Fixa: A=Prêmio(s), B=Aposta(s), C=Outro Tipo",
    '61': "SPA - Aposta Quota Fixa: A=Prêmio(s), B=Aposta(s), C=Outro Tipo",
    '62': "Lottopar - Prognóstico/Passiva: A=Prêmio(s), B=Aposta(s), C=Outro Tipo",
    '63': "Lottopar - Instantânea: A=Prêmio(s), B=Aposta(s), C=Outro Tipo",
    '64': "Lotep - Aposta Quota Fixa: A=Prêmio(s), B=Aposta(s), C=Outro Tipo",
    '65': "Lotep - Loterias: A=Prêmio(s), B=Aposta(s), C=Outro Tipo",
}
df_segmento_desc = pd.DataFrame(list(SEGMENTO_MAP.items()), columns=['CodigoSegmento', 'DescricaoCampos'])
df_segmento_desc['CodigoSegmento'] = df_segmento_desc['CodigoSegmento'].astype(str)

MAX_CONEXOES_REDE = 600
VERSAO = '3.2'
DATA_VERSAO = '19/02/2026'

# Configurações da página
st.set_page_config(
    page_title="Análise de RIF - NAE/CGU/SC",
    layout="wide",
    page_icon="🔍"
)

st.title(f"🔍 RIF Analyst {VERSAO} \nAnálise de RIF - NAE/CGU/SC  - Versão {VERSAO} - {DATA_VERSAO}")

# ==============================================
# FUNÇÕES AUXILIARES
# ==============================================

@st.cache_data
def load_data(uploaded_file):
    """Carrega arquivos CSV com tratamento robusto para datas e valores"""
    encodings = ['utf-8', 'latin1', 'iso-8859-1', 'cp1252']
    file_name = uploaded_file.name if uploaded_file else "Arquivo Desconhecido"
    for encoding in encodings:
        try:
            uploaded_file.seek(0)
            df = pd.read_csv(
                uploaded_file,
                sep=';',
                encoding=encoding,
                low_memory=False,
                na_values=['-', '', '#N/D', 'N/A']
             )

            # Tratar colunas de data
            date_cols = [col for col in df.columns if 'data' in col.lower()]
            for col in date_cols:
                original_type = df[col].dtype
                try:
                    # Tentar formato brasileiro primeiro
                    converted_date = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
                    # Tentar formato americano se brasileiro falhar
                    if converted_date.isna().all() and original_type == 'object':
                         converted_date = pd.to_datetime(df[col], errors='coerce', dayfirst=False)
                    # Tentar inferir se ambos falharem
                    if converted_date.isna().all() and original_type == 'object':
                         converted_date = pd.to_datetime(df[col], errors='coerce', infer_datetime_format=True)

                    df[col] = converted_date
                except Exception:
                    st.warning(f"Não foi possível converter a coluna de data '{col}' no arquivo {file_name}. Mantendo original.")
                    pass # Mantém a coluna como está se a conversão falhar

            return df
        except UnicodeDecodeError:
            continue
        except Exception as e:
            st.error(f"Erro crítico ao carregar ou processar datas no arquivo {file_name}: {str(e)}")
            return None
    st.error(f"Não foi possível ler o arquivo {file_name} com as codificações testadas. Verifique codificação e separador.")
    return None

def clean_numeric_br(series):
    """Limpa e converte uma Series para numérico, tratando formato brasileiro."""
    if series is None:
        return None
    # Verifica se a Series contém dados antes de tentar limpar
    if series.empty or series.isna().all():
        return pd.Series([0] * len(series), index=series.index) # Retorna zeros se vazia ou toda nula

    # Converte para string, remove pontos de milhar, troca vírgula decimal por ponto
    # Adiciona remoção de espaços e tratamento específico para casos como "R$ 1.234,56"
    cleaned_series = series.astype(str).str.strip()
    cleaned_series = cleaned_series.str.replace('R$', '', regex=False).str.strip() # Remove 'R$'
    cleaned_series = cleaned_series.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)

    # Tenta converter para numérico, erros viram NaN
    numeric_series = pd.to_numeric(cleaned_series, errors='coerce')
    return numeric_series.fillna(0) # Substitui NaN por 0

def check_columns(df, expected_cols, file_name):
    if df is None:
        st.error(f"DataFrame do arquivo {file_name} não foi carregado.")
        return False
    missing_cols = [col for col in expected_cols if col not in df.columns]
    if missing_cols:
        st.error(f"Colunas mínimas esperadas ausentes no arquivo {file_name}: {missing_cols}")
        return False
    return True

def safe_merge(left, right, left_on, right_on, **kwargs):
    if left is None or right is None:
        st.error("Erro no merge: um dos DataFrames está vazio.")
        return None
    try:
        if left_on not in left.columns:
            st.error(f"Coluna de merge '{left_on}' não encontrada no DataFrame da esquerda.")
            return None
        if right_on not in right.columns:
            st.error(f"Coluna de merge '{right_on}' não encontrada no DataFrame da direita.")
            return None

        left_copy = left.copy()
        right_copy = right.copy()
        # Garante que as colunas de merge sejam string para evitar erros de tipo
        left_copy[left_on] = left_copy[left_on].astype(str).str.strip()
        right_copy[right_on] = right_copy[right_on].astype(str).str.strip()

        merged_df = pd.merge(left_copy, right_copy, left_on=left_on, right_on=right_on, **kwargs)

        if merged_df.empty and not left_copy.empty and not right_copy.empty:
             # Verifica se há alguma correspondência nos identificadores
             left_ids = set(left_copy[left_on].unique())
             right_ids = set(right_copy[right_on].unique())
             if not left_ids.intersection(right_ids):
                  st.warning(f"Merge entre '{left_on}' e '{right_on}' vazio. **Nenhum valor correspondente encontrado** entre os arquivos.")
             else:
                  st.warning(f"Merge entre '{left_on}' e '{right_on}' vazio, mas há IDs correspondentes. Verifique outras condições do merge ou tipos de dados.")

        return merged_df

    except Exception as e:
        st.error(f"Erro crítico durante o merge em '{left_on}'/'{right_on}': {str(e)}")
        st.code(traceback.format_exc())
        return None

def normalize_string(text):
    if pd.isna(text):
        return "DESCONHECIDO"
    text = str(text)
    try:
        # Remover caracteres não-ASCII e normalizar
        text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
        normalized = text.encode('ASCII', 'ignore').decode('ASCII')
        return normalized.upper().strip() if normalized else "DESCONHECIDO"
    except Exception:
        # Fallback para uma limpeza mais simples se a normalização falhar
        try:
            cleaned = ''.join(filter(str.isalnum, text))
            return cleaned.upper() if cleaned else "DESCONHECIDO"
        except:
             return "ERRO_NORMALIZACAO"


@st.cache_data
def analyze_individual_network(df_full, selected_cpf):
    """Realiza análise de redes DIRECIONAL (DiGraph) para UM envolvido e suas conexões diretas,
       conectando 'outros' apenas ao(s) titular(es)."""
    if selected_cpf is None or selected_cpf == 'DESCONHECIDO':
        return nx.DiGraph(), {}, 0 # Retorna grafo, partição e contagem de arestas

    # Filtrar df_full ANTES de acessar colunas que podem não existir
    df_filtered_by_cpf = df_full[df_full['cpfCnpjEnvolvido'] == selected_cpf]
    if 'Indexador_x' not in df_filtered_by_cpf.columns:
         st.error("Coluna 'Indexador_x' não encontrada no DataFrame principal para análise de rede.")
         return nx.DiGraph(), {}, 0
    indexadores_selecionado = df_filtered_by_cpf['Indexador_x'].unique()


    if len(indexadores_selecionado) == 0:
        st.info(f"Envolvido {selected_cpf} não encontrado em nenhuma comunicação (nos dados filtrados).")
        return nx.DiGraph(), {}, 0

    # Filtrar o DataFrame principal para incluir APENAS essas comunicações
    relevant_df = df_full[df_full['Indexador_x'].isin(indexadores_selecionado)].copy()

    G = nx.DiGraph()

    # Garantir colunas necessárias e tratar NaNs
    relevant_df['cpfCnpjEnvolvido'] = relevant_df['cpfCnpjEnvolvido'].fillna('DESCONHECIDO').astype(str)
    relevant_df['nomeEnvolvido'] = relevant_df['nomeEnvolvido'].fillna('DESCONHECIDO').apply(normalize_string)
    relevant_df['tipoEnvolvido'] = relevant_df['tipoEnvolvido'].fillna('Desconhecido').str.lower()
    for flag in ['bitPepCitado', 'bitPessoaObrigadaCitado', 'intServidorCitado']:
        if flag not in relevant_df.columns: relevant_df[flag] = False
        else: relevant_df[flag] = relevant_df[flag].fillna(False).apply(lambda x: True if str(x).strip().lower() == 'sim' else False)


    # Adicionar nós
    node_attributes = relevant_df.drop_duplicates(subset=['cpfCnpjEnvolvido']).set_index('cpfCnpjEnvolvido')

    for node_id, row in node_attributes.iterrows():
        if node_id == 'DESCONHECIDO': continue
        G.add_node(
            node_id,
            label=row.get('nomeEnvolvido', 'DESCONHECIDO'),
            type=row.get('tipoEnvolvido', 'Desconhecido'),
            pep=row.get('bitPepCitado', False),
            obrigada=row.get('bitPessoaObrigadaCitado', False),
            servidor=row.get('intServidorCitado', False)
        )

    # Criação de arestas
    for indexador, group in relevant_df.groupby('Indexador_x'):

        num_envolvidos = group['cpfCnpjEnvolvido'].nunique()
        if num_envolvidos > 100:
            continue # Pular comunicações muito grandes
        if num_envolvidos < 2: continue

        # Identificar papéis
        depositantes = set(group.loc[group['tipoEnvolvido'] == 'depositante', 'cpfCnpjEnvolvido'].astype(str)) - {'DESCONHECIDO'}
        sacadores = set(group.loc[group['tipoEnvolvido'] == 'sacador', 'cpfCnpjEnvolvido'].astype(str)) - {'DESCONHECIDO'}
        titulares = set(group.loc[group['tipoEnvolvido'].isin(['titular da conta', 'titular']), 'cpfCnpjEnvolvido'].astype(str)) - {'DESCONHECIDO'} # Inclui 'titular'
        beneficiarios = set(group.loc[group['tipoEnvolvido'].isin(['beneficiário', 'beneficiario']), 'cpfCnpjEnvolvido'].astype(str)) - {'DESCONHECIDO'}
        remetentes = set(group.loc[group['tipoEnvolvido'] == 'remetente', 'cpfCnpjEnvolvido'].astype(str)) - {'DESCONHECIDO'}
        # 'Outros' são todos os restantes que não têm papel de fluxo principal
        outros_envolvidos = set(group['cpfCnpjEnvolvido'].astype(str)) - depositantes - sacadores - titulares - beneficiarios - remetentes - {'DESCONHECIDO'}


        # Lógica de conexão com Titular(es) como centro (se existirem)
        if titulares:
            # Fluxo: Remetente -> Titular
            for r, t in product(remetentes.union(depositantes), titulares): # Junta Remetente e Depositante
                if r != t and G.has_node(r) and G.has_node(t): G.add_edge(r, t, weight=1, operation='Entrada') # Simplificar nome
            # Fluxo: Titular -> Beneficiário
            for t, b in product(titulares, beneficiarios.union(sacadores)): # Junta Beneficiário e Sacador
                if t != b and G.has_node(t) and G.has_node(b): G.add_edge(t, b, weight=1, operation='Saída') # Simplificar nome

            # --- Conectar 'Outros' APENAS ao(s) Titular(es) (BIDIRECIONAL) ---
            for o, t in product(outros_envolvidos, titulares):
                if o != t and G.has_node(o) and G.has_node(t):
                    G.add_edge(o, t, weight=0.5, operation='Associado')
                    G.add_edge(t, o, weight=0.5, operation='Associado')
            # --- NÃO conectar outros entre si ---

        else: # Caso SEM titular explícito
             # Conectar Remetentes/Depositantes -> Beneficiários/Sacadores diretamente
             for r, b in product(remetentes.union(depositantes), beneficiarios.union(sacadores)):
                  if r != b and G.has_node(r) and G.has_node(b): G.add_edge(r, b, weight=0.8, operation='Fluxo Direto')
             # Conectar 'Outros' entre si (pode criar densidade, mas mostra que estavam juntos) - Manter opcionalmente
             # for a, b in combinations(outros_envolvidos, 2):
             #     if G.has_node(a) and G.has_node(b): G.add_edge(a, b, weight=0.2, operation='Vínculo (sem Titular)')


    # Detectar comunidades
    partition = {}
    if G.number_of_nodes() > 0:
        try:
            undirected_G = G.to_undirected()
            # Apenas calcular partição se houver arestas no grafo não direcionado
            if undirected_G.number_of_edges() > 0:
                 partition = community_louvain.best_partition(undirected_G, resolution=1.5)
            else:
                 # Se não há arestas, cada nó é sua própria comunidade
                 partition = {node: i for i, node in enumerate(undirected_G.nodes())}
        except AttributeError as e:
            st.error(f"Erro ao calcular comunidades: {e}. Verifique a instalação da biblioteca 'python-louvain'.")
            st.info("Instrução: No terminal com venv ativado, rode: pip uninstall community -y && pip uninstall python-louvain -y && pip install python-louvain")
            partition = {node: 0 for node in G.nodes()} # Fallback
        except Exception as e:
            st.warning(f"Não foi possível calcular as comunidades: {e}")
            partition = {node: 0 for node in G.nodes()} # Fallback

    # Retornar contagem de arestas
    return G, partition, G.number_of_edges()

def plot_relacionamentos_envolvido(df_full: pd.DataFrame, cpf_base: str):
    """
    Gera um gráfico de barras mostrando a força dos vínculos entre o envolvido cpf_base
    e seus contrapartes, com base em nº de comunicações e soma de ValorTotal (Campo A).
    df_full deve ser o dffinal (ou dfdisplay) já filtrado.
    """
    if df_full is None or df_full.empty:
        return None

    # Garante colunas essenciais
    for col in ["cpfCnpjEnvolvido", "Indexador_x", "ValorTotal"]:
        if col not in df_full.columns:
            return None

    df_local = df_full.copy()
    df_local["cpfCnpjEnvolvido"] = df_local["cpfCnpjEnvolvido"].astype(str)
    df_local["Indexador_x"] = df_local["Indexador_x"].astype(str)
    df_local["ValorTotal"] = pd.to_numeric(df_local["ValorTotal"], errors="coerce").fillna(0.0)

    # Comunicações onde o envolvido base participa
    idx_envolvido = df_local[df_local["cpfCnpjEnvolvido"] == str(cpf_base)]["Indexador_x"].unique()
    if len(idx_envolvido) == 0:
        return None

    df_sub = df_local[df_local["Indexador_x"].isin(idx_envolvido)].copy()

    # Self-merge para obter pares (base, contraparte) nas mesmas comunicações
    df_pairs = df_sub.merge(
        df_sub,
        on="Indexador_x",
        suffixes=("_orig", "_contra"),
    )

    # Mantém apenas pares onde o orig é o envolvido base e a contraparte é outro CPF/CNPJ
    df_pairs = df_pairs[
        (df_pairs["cpfCnpjEnvolvido_orig"] == str(cpf_base))
        & (df_pairs["cpfCnpjEnvolvido_contra"] != str(cpf_base))
    ].copy()

    if df_pairs.empty:
        return None

    # Usa ValorTotal da contraparte como medida de fluxo; se preferir, pode usar da base
    df_pairs["valor_vinculo"] = df_pairs["ValorTotal_contra"]

    # Agrega por contraparte
    agg = (
        df_pairs.groupby("cpfCnpjEnvolvido_contra", as_index=False)
        .agg(
            n_comunicacoes=("Indexador_x", "nunique"),
            valor_total=("valor_vinculo", "sum"),
        )
    )

    # Junta nome da contraparte (se disponível)
    if "nomeEnvolvido_contra" in df_pairs.columns:
        nomes = (
            df_pairs.groupby("cpfCnpjEnvolvido_contra", as_index=False)["nomeEnvolvido_contra"]
            .agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else x.iloc[0])
            .rename(columns={"nomeEnvolvido_contra": "NomeContraparte"})
        )
        agg = agg.merge(nomes, on="cpfCnpjEnvolvido_contra", how="left")
    else:
        agg["NomeContraparte"] = agg["cpfCnpjEnvolvido_contra"]

    # Ordena por valor_total
    agg = agg.sort_values("valor_total", ascending=False).head(30)  # top 30 contrapartes

    # Cria rótulo amigável para eixo Y
    agg["Label"] = agg["NomeContraparte"] + " (" + agg["cpfCnpjEnvolvido_contra"] + ")"

    fig = px.bar(
        agg,
        y="Label",
        x="valor_total",
        orientation="h",
        color="n_comunicacoes",
        labels={
            "valor_total": "Valor Total (Campo A)",
            "n_comunicacoes": "Qtd. Comunicações",
            "Label": "Contraparte",
        },
        title="Força dos vínculos (Valor Total e nº de comunicações)",
        hover_data=["n_comunicacoes"],
        height=600,
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})

    return fig


# --- NOVO: Função para simplificar o grafo individual ---
def simplify_graph(G_original, central_node):
    """Cria um grafo simplificado contendo apenas o nó central e seus vizinhos diretos."""
    if central_node not in G_original:
        return nx.DiGraph() # Retorna grafo vazio se o nó central não estiver no grafo

    G_simplified = nx.DiGraph()

    # Pega vizinhos diretos (antecessores e sucessores)
    predecessors = list(G_original.predecessors(central_node))
    successors = list(G_original.successors(central_node))
    neighbors = set(predecessors + successors)

    # Adicionar o nó central e seus atributos
    if G_original.has_node(central_node):
         G_simplified.add_node(central_node, **G_original.nodes[central_node])

    # Adicionar vizinhos e arestas conectadas AO nó central
    for neighbor in neighbors:
        if G_original.has_node(neighbor): # Garante que o vizinho existe
            # Adicionar o nó vizinho
            G_simplified.add_node(neighbor, **G_original.nodes[neighbor])

            # Adicionar aresta(s) entre vizinho e nó central, preservando direção e dados
            if G_original.has_edge(neighbor, central_node):
                G_simplified.add_edge(neighbor, central_node, **G_original.edges[neighbor, central_node])
            if G_original.has_edge(central_node, neighbor):
                G_simplified.add_edge(central_node, neighbor, **G_original.edges[central_node, neighbor])

    return G_simplified

# --- MANTIDO E CORRIGIDO NOVAMENTE: Função para visualizar grafo ---
def visualize_network(G, partition, selected_cpf=None):
    """Gera visualização Pyvis para o grafo, destacando o nó selecionado."""
    if G is None or G.number_of_nodes() == 0:
        st.warning("Nenhuma conexão para visualizar.")
        return None

    net = Network(height="750px", width="100%", bgcolor="#f0f2f6", font_color="black", directed=True)

    for node in G.nodes():
        node_data = G.nodes[node]
        is_selected = node == selected_cpf # Checa se é o nó central selecionado
        is_titular = node_data.get('role', '').lower() in ['titular', 'titular da conta'] # Checa se é titular (caso não seja o selecionado)

        # Definir tamanho: Maior para o selecionado, Médio para Titular, Padrão para outros
        if is_selected:
            node_size = 25
        elif is_titular:
             node_size = 20
        else:
             node_size = 15

        # Definir cor: Prioridade para selecionado, depois PEP, Servidor, Titular, P. Obrigada, padrão
        if is_selected:
            node_color = "#E74C3C" # Vermelho forte para selecionado
        elif node_data.get('pep', False):
             node_color = "#FF6B6B" # Vermelho PEP
        elif node_data.get('servidor', False):
             node_color = "#FFD700" # Amarelo Servidor
        elif is_titular:
             node_color = "#3498DB" # Azul para Titular (se não for selecionado/PEP/Servidor)
        elif node_data.get('obrigada', False):
              node_color = "#4ECDC4" # Verde-água Pessoa Obrigada
        else:
             node_color = "#556270" # Cinza padrão

        # Montar título do nó (tooltip)
        title_lines = []
        if is_selected: title_lines.append("**Selecionado:**")
        title_lines.append(f"Nome: {node_data.get('label', 'N/A')}")
        title_lines.append(f"CPF/CNPJ: {node}")
        if 'role' in node_data: title_lines.append(f"Papel: {node_data.get('role', 'N/A')}")
        if 'type' in node_data and 'role' not in node_data: title_lines.append(f"Tipo: {node_data.get('type', 'N/A')}") # Fallback se 'role' não existir
        if 'pep' in node_data: title_lines.append(f"PEP: {'Sim' if node_data.get('pep', False) else 'Não'}")
        if 'obrigada' in node_data: title_lines.append(f"P. Obrigada: {'Sim' if node_data.get('obrigada', False) else 'Não'}")
        if 'servidor' in node_data: title_lines.append(f"Servidor P.: {'Sim' if node_data.get('servidor', False) else 'Não'}")

        net.add_node(
            node,
            label=node_data.get('label', 'DESCONHECIDO'),
            group=partition.get(node, 0),
            size=node_size,
            color=node_color,
            title="\n".join(title_lines)
        )

    for edge in G.edges(data=True):
        source, target, data = edge
        if source in G and target in G:
            op = data.get('operation', 'conexão')
            weight = data.get('weight', 1)
            display_value = min(weight * 2, 10)
            net.add_edge(source, target, value=display_value, title=f"{op} (Peso: {weight})")

    net.repulsion(node_distance=250, central_gravity=0.1, spring_length=200, spring_strength=0.05, damping=0.1)
    net.show_buttons(filter_=['physics'])

    try:
        # --- CORRIGIDO NOVAMENTE: Sanitização mais explícita ---
        file_id_base = "network" # Default
        if selected_cpf:
            # Substituir caracteres inválidos por underscore
            sanitized_cpf = str(selected_cpf).replace('/', '_').replace('.', '_').replace('-', '_')
            file_id_base = f"net_{sanitized_cpf}"

        # Garantir que o nome não seja excessivamente longo (limite do Windows pode ser 260 chars no total)
        file_id_base = file_id_base[:50] # Limita a parte variável a 50 caracteres

        suffix = f"_{file_id_base}.html"
        # --- FIM CORREÇÃO ---

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, mode='w', encoding='utf-8') as tmpfile:
            net.save_graph(tmpfile.name)
            return tmpfile.name
    except Exception as e:
        st.error(f"Erro ao gerar visualização da rede: {str(e)}")
        st.code(traceback.format_exc())
        return None

# --- NOVO: Função para gerar legenda do gráfico de rede ---
def generate_network_legend():
    """Gera o HTML para a legenda de cores do gráfico de rede."""
    colors = {
        "Selecionado / Titular (Com.)": "#E74C3C",
        "PEP": "#FF6B6B",
        "Servidor Público": "#FFD700",
        "Titular (Rede Ind.)": "#3498DB",
        "Pessoa Obrigada": "#4ECDC4",
        "Outro": "#556270"
    }

    legend_html = "<div style='display: flex; flex-wrap: wrap; justify-content: center; margin-bottom: 15px;'>"
    for label, color in colors.items():
        legend_html += f"""
        <div style='margin: 5px; display: flex; align-items: center;'>
            <span style='background-color:{color}; width: 15px; height: 15px; border-radius: 50%; display: inline-block; margin-right: 5px;'></span>
            <span>{label}</span>
        </div>
        """
    legend_html += "</div>"
    return legend_html

@st.cache_data
def analyze_suspicious_patterns(_df_display, _df_ocorrencias, _df_comunicacoes, _df_envolvidos):
    """Detecta padrões suspeitos (VETORIZADO) - Recebe df filtrado e retorna com Indexador/idComunicacao como STRING"""
    suspicious_patterns = []
    return_cols = ['Indexador', 'idComunicacao', 'cpfCnpj', 'Nome', 'Motivo', 'Risco']

    # Usar cópias para segurança
    df = _df_display.copy() if _df_display is not None else pd.DataFrame()
    df_ocorrencias_local = _df_ocorrencias.copy() if _df_ocorrencias is not None else pd.DataFrame()
    df_comunicacoes_local = _df_comunicacoes.copy() if _df_comunicacoes is not None else pd.DataFrame()
    df_envolvidos_local = _df_envolvidos.copy() if _df_envolvidos is not None else pd.DataFrame()

    if df.empty or df_ocorrencias_local.empty or df_comunicacoes_local.empty or df_envolvidos_local.empty:
        return pd.DataFrame(columns=return_cols)

    # --- Pré-processamento Interno ---
    df_ocorrencias_local['idOcorrencia'] = df_ocorrencias_local['idOcorrencia'].astype(str)
    df_ocorrencias_local['Indexador'] = df_ocorrencias_local['Indexador'].astype(str).str.strip()
    df_comunicacoes_local['Indexador'] = df_comunicacoes_local['Indexador'].astype(str).str.strip()
    df_envolvidos_local['Indexador'] = df_envolvidos_local['Indexador'].astype(str).str.strip()
    df_envolvidos_local['cpfCnpjEnvolvido'] = df_envolvidos_local['cpfCnpjEnvolvido'].fillna('DESCONHECIDO').astype(str).str.strip()

    envolvidos_dict = df_envolvidos_local.drop_duplicates(subset=['cpfCnpjEnvolvido']).set_index('cpfCnpjEnvolvido')['nomeEnvolvido'].apply(normalize_string)

    # Garante colunas em df
    if 'Indexador_x' not in df.columns: df['Indexador_x'] = 'N/A'
    if 'idComunicacao' not in df.columns: df['idComunicacao'] = 'N/A'

    # --- Padrão 1: Contas recém-abertas ---
    # ... (código mantido, adiciona string explicitly) ...
    if 'DataAberturaConta' in df.columns and 'Data_da_operacao' in df.columns:
        df['DataAberturaConta'] = pd.to_datetime(df['DataAberturaConta'], errors='coerce')
        df['Data_da_operacao'] = pd.to_datetime(df['Data_da_operacao'], errors='coerce')
        if pd.api.types.is_datetime64_any_dtype(df['DataAberturaConta']) and pd.api.types.is_datetime64_any_dtype(df['Data_da_operacao']):
            df['IdadeConta'] = (df['Data_da_operacao'] - df['DataAberturaConta']).dt.days
            contas_novas = df[(df['IdadeConta'] < 30) & (df['IdadeConta'] >= 0)].copy()
            if not contas_novas.empty:
                for _, row in contas_novas.iterrows():
                     suspicious_patterns.append({
                         'Indexador': str(row.get('Indexador_x', 'N/A')), # Força string
                         'idComunicacao': str(row.get('idComunicacao', 'N/A')), # Força string
                         'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
                         'Nome': str(row.get('nomeEnvolvido', 'DESCONHECIDO')),
                         'Motivo': f"Operação em conta com {row.get('IdadeConta', 0):.0f} dias",
                         'Risco': 'Moderado'
                     })

    # --- Padrão 2: Alta frequência ---
    if 'Data_da_operacao' in df.columns and pd.api.types.is_datetime64_any_dtype(df['Data_da_operacao']):
        df_clean_date = df.dropna(subset=['Data_da_operacao'])
        if not df_clean_date.empty:
            agg_freq = df_clean_date.groupby('cpfCnpjEnvolvido').agg(
                DataMin=('Data_da_operacao', 'min'), DataMax=('Data_da_operacao', 'max'),
                Count=('idComunicacao', 'nunique'),
                # --- MODIFICADO: Coleta apenas o PRIMEIRO exemplo ---
                First_Indexador=('Indexador_x', 'first'),
                First_Comunicacao=('idComunicacao', 'first')
            ).reset_index()
            agg_freq['Dias'] = (agg_freq['DataMax'] - agg_freq['DataMin']).dt.days + 1
            high_frequency = agg_freq[(agg_freq['Count'] > 10) & (agg_freq['Dias'] <= 7)].copy()
            if not high_frequency.empty:
                for _, row in high_frequency.iterrows():
                     suspicious_patterns.append({
                         'Indexador': f"Ex: {str(row.get('First_Indexador', 'N/A'))}", # Formato String
                         'idComunicacao': f"Ex: {str(row.get('First_Comunicacao', 'N/A'))}", # Formato String
                         'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
                         'Nome': envolvidos_dict.get(str(row.get('cpfCnpjEnvolvido')), 'DESCONHECIDO'),
                         'Motivo': f"Alta frequência: {row.get('Count', 0)} comunicações em {row.get('Dias', 0)} dias",
                         'Risco': 'Alto'
                     })

    # --- Padrão 3: Múltiplas localidades ---
    if 'Data_da_operacao' in df.columns and 'CidadeAgencia' in df.columns:
        df_clean_date_loc = df.dropna(subset=['Data_da_operacao', 'CidadeAgencia'])
        if not df_clean_date_loc.empty:
            same_day_loc = df_clean_date_loc.groupby(['cpfCnpjEnvolvido', df_clean_date_loc['Data_da_operacao'].dt.date]).agg(
                Cidades=('CidadeAgencia', 'nunique'), Agencias=('NumeroAgencia', 'nunique'),
                 # --- MODIFICADO: Coleta apenas o PRIMEIRO exemplo ---
                First_Indexador=('Indexador_x', 'first'),
                First_Comunicacao=('idComunicacao', 'first')
            ).reset_index()
            suspicious_locations = same_day_loc[(same_day_loc['Cidades'] > 1) | (same_day_loc['Agencias'] > 2)].copy()
            if not suspicious_locations.empty:
                 for _, row in suspicious_locations.iterrows():
                     suspicious_patterns.append({
                         'Indexador': f"Ex: {str(row.get('First_Indexador', 'N/A'))}", # Formato String
                         'idComunicacao': f"Ex: {str(row.get('First_Comunicacao', 'N/A'))}", # Formato String
                         'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
                         'Nome': envolvidos_dict.get(str(row.get('cpfCnpjEnvolvido')), 'DESCONHECIDO'),
                         'Motivo': f"Transações em {row.get('Cidades', 0)} cidades/{row.get('Agencias', 0)} agências no dia {row.get('Data_da_operacao', 'N/A')}",
                         'Risco': 'Moderado'
                     })

    # --- Padrão 4: PEPs com múltiplas comunicações ---
    if 'bitPepCitado' in df.columns:
        pep_comms_df = df[df['bitPepCitado'] == True]
        if not pep_comms_df.empty:
            pep_agg = pep_comms_df.groupby('cpfCnpjEnvolvido').agg(
                idComunicacao_count=('idComunicacao', 'nunique'),
                # --- MODIFICADO: Coleta apenas o PRIMEIRO exemplo ---
                First_Indexador=('Indexador_x', 'first'),
                First_Comunicacao=('idComunicacao', 'first')
            ).reset_index()
            high_risk_peps = pep_agg[pep_agg['idComunicacao_count'] > 3].copy()
            if not high_risk_peps.empty:
                 for _, row in high_risk_peps.iterrows():
                    suspicious_patterns.append({
                        'Indexador': f"Ex: {str(row.get('First_Indexador', 'N/A'))}", # Formato String
                        'idComunicacao': f"Ex: {str(row.get('First_Comunicacao', 'N/A'))}", # Formato String
                        'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
                        'Nome': envolvidos_dict.get(str(row.get('cpfCnpjEnvolvido')), 'DESCONHECIDO'),
                        'Motivo': f"PEP com {row.get('idComunicacao_count', 0)} comunicações suspeitas",
                        'Risco': 'Crítico'
                    })


    # --- NOVO Padrão 17: Burla de Limites (Structuring) ---
    # Detecta valores entre 90% e 99% de limites comuns (10k, 50k, 100k, 1mi)
    if 'ValorTotal' in df.columns:
        limites_comuns = [10000, 50000, 100000, 1000000]
        for limite in limites_comuns:
            lower_bound = limite * 0.90
            upper_bound = limite * 0.99

            # Filtra transações nesse intervalo "quase lá"
            # Ignora segmento 24 (Imóveis) onde valores altos são normais
            df_structuring = df[
                (df['ValorTotal'] >= lower_bound) &
                (df['ValorTotal'] <= upper_bound) &
                (df['CodigoSegmento'] != '24')
            ].copy()

            if not df_structuring.empty:
                for _, row in df_structuring.iterrows():
                     suspicious_patterns.append({
                         'Indexador': str(row.get('Indexador_x', 'N/A')),
                         'idComunicacao': str(row.get('idComunicacao', 'N/A')),
                         'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
                         'Nome': str(row.get('nomeEnvolvido', 'DESCONHECIDO')),
                         'Motivo': f"Burla de Limites? Valor (R$ {row['ValorTotal']:,.2f}) está logo abaixo do limite de {limite/1000:.0f}k",
                         'Risco': 'Alto'
                     })
    # --- FIM NOVO ---

    # --- Padrão 5 e 5b: Alto valor ---
    if 'ValorTotal' in df.columns and 'CodigoSegmento' in df.columns:
        high_value = df[(df['ValorTotal'] > 1_000_000) & (df['CodigoSegmento'] != '24')].copy()
        if not high_value.empty:
            for _, row in high_value.iterrows():
                 suspicious_patterns.append({
                     'Indexador': str(row.get('Indexador_x', 'N/A')), # Força string
                     'idComunicacao': str(row.get('idComunicacao', 'N/A')), # Força string
                     'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
                     'Nome': str(row.get('nomeEnvolvido', 'DESCONHECIDO')),
                     'Motivo': f"Transação alto valor (CampoA): R$ {row.get('ValorTotal', 0):,.2f}",
                     'Risco': 'Alto'
                 })

    if 'ValorCampoB' in df.columns and 'CodigoSegmento' in df.columns:
        high_value_b = df[(df['ValorCampoB'] > 1_000_000) & (df['CodigoSegmento'] == '24')].copy()
        if not high_value_b.empty:
             for _, row in high_value_b.iterrows():
                 suspicious_patterns.append({
                     'Indexador': str(row.get('Indexador_x', 'N/A')), # Força string
                     'idComunicacao': str(row.get('idComunicacao', 'N/A')), # Força string
                     'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
                     'Nome': str(row.get('nomeEnvolvido', 'DESCONHECIDO')),
                     'Motivo': f"Transação Imob. (CampoB) alto valor: R$ {row.get('ValorCampoB', 0):,.2f}",
                     'Risco': 'Alto'
                 })


    # --- Padrões 6, 7, 8, 12 (Baseados em merge com tabelas originais) ---
    comm_cols_base = ['Indexador', 'idComunicacao', 'ValorCampoA', 'CodigoSegmento']
    comm_cols_vals = [f'Valor{c}' for c in ['B','C','D','E'] if f'Valor{c}' in df_comunicacoes_local.columns]
    comm_cols = list(set(comm_cols_base + comm_cols_vals).intersection(df_comunicacoes_local.columns))
    env_cols = ['Indexador', 'cpfCnpjEnvolvido', 'nomeEnvolvido']
    ocor_cols = ['Indexador', 'idOcorrencia', 'Ocorrencia']
    comm_cols = [col for col in comm_cols if col in df_comunicacoes_local.columns]
    env_cols = [col for col in env_cols if col in df_envolvidos_local.columns]
    ocor_cols = [col for col in ocor_cols if col in df_ocorrencias_local.columns]

    df_comm_for_merge = df_comunicacoes_local[comm_cols]

    comm_env_ocor = pd.merge(df_comm_for_merge, df_envolvidos_local[env_cols], on='Indexador', how='left')
    comm_env_ocor = pd.merge(comm_env_ocor, df_ocorrencias_local[ocor_cols], on='Indexador', how='left')
    comm_env_ocor.dropna(subset=['idOcorrencia', 'cpfCnpjEnvolvido'], inplace=True)
    valid_indexadores_pattern = df['Indexador_x'].unique()
    comm_env_ocor = comm_env_ocor[comm_env_ocor['Indexador'].isin(valid_indexadores_pattern)]

    # Padrão 6: Saques
    saque_ids = ['891', '894', '1163', '1159']
    p6_df = comm_env_ocor[(comm_env_ocor['idOcorrencia'].isin(saque_ids)) & (comm_env_ocor['ValorCampoA'] >= 50_000)].drop_duplicates(subset=['cpfCnpjEnvolvido', 'Indexador', 'idComunicacao']).copy()
    if not p6_df.empty:
        for _, row in p6_df.iterrows():
             suspicious_patterns.append({
                 'Indexador': str(row.get('Indexador', 'N/A')), # Força string
                 'idComunicacao': str(row.get('idComunicacao', 'N/A')), # Força string
                 'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
                 'Nome': envolvidos_dict.get(str(row.get('cpfCnpjEnvolvido')), 'DESCONHECIDO'),
                 'Motivo': f"Saque espécie >= R$ 50k (R$ {row.get('ValorCampoA', 0):,.2f}, Ocorr: {row.get('idOcorrencia')})",
                 'Risco': 'Alto'
             })

    # Padrão 7: Depósitos
    deposito_ids = ['1161']
    p7_df = comm_env_ocor[(comm_env_ocor['idOcorrencia'].isin(deposito_ids)) & (comm_env_ocor['ValorCampoA'] >= 50_000)].drop_duplicates(subset=['cpfCnpjEnvolvido', 'Indexador', 'idComunicacao']).copy()
    if not p7_df.empty:
        for _, row in p7_df.iterrows():
             suspicious_patterns.append({
                 'Indexador': str(row.get('Indexador', 'N/A')), # Força string
                 'idComunicacao': str(row.get('idComunicacao', 'N/A')), # Força string
                 'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
                 'Nome': envolvidos_dict.get(str(row.get('cpfCnpjEnvolvido')), 'DESCONHECIDO'),
                 'Motivo': f"Depósito espécie >= R$ 50k (R$ {row.get('ValorCampoA', 0):,.2f}, Ocorr: {row.get('idOcorrencia')})",
                 'Risco': 'Alto'
             })

    # Padrão 8: Resistência
    resistencia_ids = ['958']
    p8_df = comm_env_ocor[comm_env_ocor['idOcorrencia'].isin(resistencia_ids)].drop_duplicates(subset=['cpfCnpjEnvolvido', 'Indexador', 'idComunicacao']).copy()
    if not p8_df.empty:
        for _, row in p8_df.iterrows():
             suspicious_patterns.append({
                 'Indexador': str(row.get('Indexador', 'N/A')), # Força string
                 'idComunicacao': str(row.get('idComunicacao', 'N/A')), # Força string
                 'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
                 'Nome': envolvidos_dict.get(str(row.get('cpfCnpjEnvolvido')), 'DESCONHECIDO'),
                 'Motivo': "Resistência (Ocorr: 958)",
                 'Risco': 'Moderado'
             })

    # Padrão 12: Alto Valor em Espécie (CampoB)
    segmentos_especie_b = ['19', '23', '15', '46', '48', '49', '51', '52']
    if 'ValorCampoB' in comm_env_ocor.columns and 'CodigoSegmento' in comm_env_ocor.columns:
         high_cash_b = comm_env_ocor[
             (comm_env_ocor['CodigoSegmento'].isin(segmentos_especie_b)) &
             (comm_env_ocor['ValorCampoB'] >= 50_000)
         ].drop_duplicates(subset=['cpfCnpjEnvolvido', 'Indexador', 'idComunicacao']).copy()
         if not high_cash_b.empty:
              for _, row in high_cash_b.iterrows():
                 suspicious_patterns.append({
                     'Indexador': str(row.get('Indexador', 'N/A')), # Força string
                     'idComunicacao': str(row.get('idComunicacao', 'N/A')), # Força string
                     'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
                     'Nome': envolvidos_dict.get(str(row.get('cpfCnpjEnvolvido')), 'DESCONHECIDO'),
                     'Motivo': f"Alto Valor Espécie (CampoB): R$ {row.get('ValorCampoB', 0):,.2f} (Seg: {row.get('CodigoSegmento')})",
                     'Risco': 'Crítico'
                 })


    # --- Padrões 9, 10, 11 (Baseados em df_display, agregados) ---
    # Padrão 9: Fracionamento
    limite_reporte = 50000
    limite_fracionamento = 0.9 * limite_reporte
    if 'Data_da_operacao' in df.columns:
        df_clean_date_smurf = df.dropna(subset=['Data_da_operacao'])
        if not df_clean_date_smurf.empty:
            daily_sums = df_clean_date_smurf.groupby(['cpfCnpjEnvolvido', df_clean_date_smurf['Data_da_operacao'].dt.date]).agg(
                ValorDia=('ValorTotal', 'sum'), QtdDia=('idComunicacao', 'nunique'),
                First_Indexador=('Indexador_x', 'first'), First_Comunicacao=('idComunicacao', 'first')
            ).reset_index()
            smurfing = daily_sums[(daily_sums['QtdDia'] >= 3) & (daily_sums['ValorDia'] >= limite_fracionamento) & (daily_sums['ValorDia'] < limite_reporte)].copy()
            if not smurfing.empty:
                 for _, row in smurfing.iterrows():
                     suspicious_patterns.append({
                         'Indexador': f"Ex: {str(row.get('First_Indexador', 'N/A'))}", # Formato String
                         'idComunicacao': f"Ex: {str(row.get('First_Comunicacao', 'N/A'))}", # Formato String
                         'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
                         'Nome': envolvidos_dict.get(str(row.get('cpfCnpjEnvolvido')), 'DESCONHECIDO'),
                         'Motivo': f"Fracionamento (CampoA): {row.get('QtdDia', 0)} coms. total R$ {row.get('ValorDia', 0):,.2f} em {row.get('Data_da_operacao', 'N/A')}",
                         'Risco': 'Crítico'
                     })

    # Padrão 10: Risco Geográfico
    cidades_de_risco = ['PONTA PORA', 'CORUMBA', 'FOZ DO IGUACU', 'GUAIRA', 'PACARAIMA', 'TABATINGA', 'SANTOS', 'PARANAGUA', 'ITAJAI', 'CACEQUES', 'BARRACAO', 'PORTO XAVIER', 'CAPANEMA']
    if 'CidadeAgencia' in df.columns:
        df['CidadeAgenciaNorm'] = df['CidadeAgencia'].apply(normalize_string)
        risco_geo = df[df['CidadeAgenciaNorm'].isin(cidades_de_risco)].copy()
        if not risco_geo.empty:
            risco_geo_agg = risco_geo.groupby(['cpfCnpjEnvolvido', 'CidadeAgenciaNorm']).agg(
                ValorTotal=('ValorTotal', 'sum'), Qtd=('idComunicacao', 'nunique'),
                First_Indexador=('Indexador_x', 'first'), First_Comunicacao=('idComunicacao', 'first')
            ).reset_index()
            if not risco_geo_agg.empty:
                 for _, row in risco_geo_agg.iterrows():
                    suspicious_patterns.append({
                        'Indexador': f"Ex: {str(row.get('First_Indexador', 'N/A'))}", # Formato String
                        'idComunicacao': f"Ex: {str(row.get('First_Comunicacao', 'N/A'))}", # Formato String
                        'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
                        'Nome': envolvidos_dict.get(str(row.get('cpfCnpjEnvolvido')), 'DESCONHECIDO'),
                        'Motivo': f"Risco Geo: {row.get('Qtd', 0)} coms. em {row.get('CidadeAgenciaNorm', 'N/A')} (R$ {row.get('ValorTotal', 0):,.2f})",
                        'Risco': 'Moderado'
                    })

    # Padrão 11: Pass-Through
    if 'tipoEnvolvido' in df.columns:
        roles = df.groupby('cpfCnpjEnvolvido')['tipoEnvolvido'].unique().apply(set).reset_index()
        pass_through_candidates = roles[
            roles['tipoEnvolvido'].apply(lambda x: 'depositante' in x) &
            roles['tipoEnvolvido'].apply(lambda x: 'sacador' in x or 'titular da conta' in x)
        ]
        if not pass_through_candidates.empty:
            volume = df[df['cpfCnpjEnvolvido'].isin(pass_through_candidates['cpfCnpjEnvolvido'])] \
                         .groupby('cpfCnpjEnvolvido') \
                         .agg(
                             ValorTotal=('ValorTotal', 'sum'),
                             First_Indexador=('Indexador_x', 'first'),
                             First_Comunicacao=('idComunicacao', 'first')
                         ).reset_index()
            high_volume_pass = volume[volume['ValorTotal'] > 500_000].copy()
            if not high_volume_pass.empty:
                 for _, row in high_volume_pass.iterrows():
                    suspicious_patterns.append({
                        'Indexador': f"Ex: {str(row.get('First_Indexador', 'N/A'))}", # Formato String
                        'idComunicacao': f"Ex: {str(row.get('First_Comunicacao', 'N/A'))}", # Formato String
                        'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
                        'Nome': envolvidos_dict.get(str(row.get('cpfCnpjEnvolvido')), 'DESCONHECIDO'),
                        'Motivo': f"Atividade 'Pass-Through' (R$ {row.get('ValorTotal', 0):,.2f})",
                        'Risco': 'Alto'
                    })


    # --- Padrões 13-16 (Baseados em Indexador, usam df originais) ---
    # Padrão 13: Múltiplas Ocorrências
    ocor_counts = df_ocorrencias_local.groupby('Indexador')['idOcorrencia'].nunique()
    multi_ocor_idx = ocor_counts[ocor_counts > 2].index
    if not multi_ocor_idx.empty:
        ocor_details = df_ocorrencias_local[df_ocorrencias_local['Indexador'].isin(multi_ocor_idx)]
        ocor_grouped_text = ocor_details.groupby('Indexador')['Ocorrencia'].apply(lambda x: '; '.join(x.astype(str).unique()))
        for idx, ocor_text in ocor_grouped_text.items():
            comm_id_ex_df = df_comunicacoes_local[df_comunicacoes_local['Indexador']==idx]['idComunicacao']
            comm_id_ex = str(comm_id_ex_df.iloc[0]) if not comm_id_ex_df.empty else 'N/A'
            suspicious_patterns.append({
                'Indexador': str(idx), # Força string
                'idComunicacao': comm_id_ex, # Já é string
                'cpfCnpj': 'N/A (Indexador)',
                'Nome': "Múltiplas Ocorrências",
                'Motivo': f"{ocor_counts[idx]} ocorrências: {ocor_text[:200]}...",
                'Risco': 'Alto'
            })

    # Padrão 14: Alta Complexidade
    involved_counts = df_envolvidos_local.groupby('Indexador')['cpfCnpjEnvolvido'].nunique()
    complex_idx = involved_counts[involved_counts > 15].index
    if not complex_idx.empty:
        for idx in complex_idx:
            comm_id_ex_df = df_comunicacoes_local[df_comunicacoes_local['Indexador']==idx]['idComunicacao']
            comm_id_ex = str(comm_id_ex_df.iloc[0]) if not comm_id_ex_df.empty else 'N/A'
            suspicious_patterns.append({
                'Indexador': str(idx), # Força string
                'idComunicacao': comm_id_ex, # Já é string
                'cpfCnpj': 'N/A (Indexador)',
                'Nome': "Alta Complexidade",
                'Motivo': f"{involved_counts[idx]} envolvidos distintos.",
                'Risco': 'Moderado'
            })

    # Padrão 15: Concentração de Perfis de Risco
    for flag in ['bitPepCitado', 'bitPessoaObrigadaCitado', 'intServidorCitado']:
         if flag not in df_envolvidos_local.columns: df_envolvidos_local[flag] = 'Não'
         df_envolvidos_local[flag] = df_envolvidos_local[flag].apply(lambda x: True if str(x).strip().lower() == 'sim' else False).fillna(False).astype(bool)
    risk_profile_agg = df_envolvidos_local.groupby('Indexador').agg(
        total_envolvidos=('cpfCnpjEnvolvido', 'nunique'), pep_count=('bitPepCitado', 'sum'),
        obrigada_count=('bitPessoaObrigadaCitado', 'sum'), servidor_count=('intServidorCitado', 'sum')
    )
    risk_profile_agg = risk_profile_agg[risk_profile_agg['total_envolvidos'] > 0]
    risk_profile_agg['pep_perc'] = (risk_profile_agg['pep_count'] / risk_profile_agg['total_envolvidos']) * 100
    risk_profile_agg['servidor_perc'] = (risk_profile_agg['servidor_count'] / risk_profile_agg['total_envolvidos']) * 100
    high_conc_idx = risk_profile_agg[
        (risk_profile_agg['pep_count'] > 2) | (risk_profile_agg['servidor_count'] > 5) | (risk_profile_agg['pep_perc'] > 50)
    ].index
    if not high_conc_idx.empty:
        for idx in high_conc_idx:
            details = risk_profile_agg.loc[idx]
            comm_id_ex_df = df_comunicacoes_local[df_comunicacoes_local['Indexador']==idx]['idComunicacao']
            comm_id_ex = str(comm_id_ex_df.iloc[0]) if not comm_id_ex_df.empty else 'N/A'
            suspicious_patterns.append({
                'Indexador': str(idx), # Força string
                'idComunicacao': comm_id_ex, # Já é string
                'cpfCnpj': 'N/A (Indexador)',
                'Nome': "Concentração Perfis Risco",
                'Motivo': f"{details['pep_count']} PEPs ({details['pep_perc']:.0f}%), {details['servidor_count']} Servidores ({details['servidor_perc']:.0f}%)",
                'Risco': 'Alto'
            })

    # Padrão 16: Keywords Suspeitas
    # ... (código mantido, adiciona str()) ...
    keywords = ['LARANJA', 'FACHADA', 'INCOMPATIVEL', 'SEM LASTRO', 'SEM ORIGEM', 'RECUSA', 'NERVOSISMO', 'FRACIONAMENTO', 'CORRUPCAO', 'TRAFICO', 'ESPECIE VALOR ALTO', 'DOLEIRO', 'TESTA DE FERRO', 'SIMULADA', 'DROGAS']
    keyword_regex = '|'.join(keywords)
    if 'informacoesAdicionais' in df_comunicacoes_local.columns and df_comunicacoes_local['informacoesAdicionais'].notna().any():
        df_comunicacoes_local['info_norm'] = df_comunicacoes_local['informacoesAdicionais'].astype(str).apply(normalize_string)
        keyword_hits = df_comunicacoes_local[df_comunicacoes_local['info_norm'].str.contains(keyword_regex, na=False)].copy()
        if not keyword_hits.empty:
             def find_keywords(text, kw_list):
                 if pd.isna(text): return 'N/A'
                 # Busca case-insensitive
                 found = [kw for kw in kw_list if kw in text.upper()]
                 return ', '.join(found) if found else 'N/A'
             keyword_hits['keywords_found'] = keyword_hits['info_norm'].apply(lambda x: find_keywords(x, keywords))
             # Filtrar pelos indexadores válidos
             keyword_hits = keyword_hits[keyword_hits['Indexador'].isin(valid_indexadores_pattern)]
             for _, row in keyword_hits.iterrows():
                suspicious_patterns.append({
                    'Indexador': str(row.get('Indexador', 'N/A')), # Força string
                    'idComunicacao': str(row.get('idComunicacao', 'N/A')), # Força string
                    'cpfCnpj': 'N/A (Narrativa)',
                    'Nome': "Keyword Suspeita",
                    'Motivo': f"Narrativa contém: '{row.get('keywords_found', 'N/A')}'.",
                    'Risco': 'Moderado'
                })
        df_comunicacoes_local.drop(columns=['info_norm'], inplace=True, errors='ignore')


    # Padrão 17: Burla de Limites (Structuring) ---
    limiares = [10000, 50000, 100000]
    for limite in limiares:
        inferior = limite * 0.90
        superior = limite * 0.99

        # Filtra transações nesse intervalo perigoso
        df_structuring = df[(df['ValorTotal'] >= inferior) & (df['ValorTotal'] <= superior)].copy()

        if not df_structuring.empty:
            for _, row in df_structuring.iterrows():
                 suspicious_patterns.append({
                     'Indexador': str(row.get('Indexador_x', 'N/A')),
                     'idComunicacao': str(row.get('idComunicacao', 'N/A')),
                     'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
                     'Nome': str(row.get('nomeEnvolvido', 'DESCONHECIDO')),
                     'Motivo': f"Valor próximo ao limite de R$ {limite/1000:.0f}k (Indício de Burla): R$ {row['ValorTotal']:,.2f}",
                     'Risco': 'Alto'
                 })

    # --- Consolidação Final (Versão Corrigida) ---
    if not suspicious_patterns:
        return pd.DataFrame(columns=return_cols)

    final_df = pd.DataFrame(suspicious_patterns)
    
    # 1. REMOVER DUPLICADAS (O "Pulo do Gato")
    # Isso elimina as repetições causadas pelas múltiplas ocorrências do merge
    key_cols = ['Indexador', 'idComunicacao', 'cpfCnpj', 'Motivo', 'Risco']
    final_df = final_df.drop_duplicates(subset=key_cols)

    if not final_df.empty:
        # Definir pesos
        pesos = {'Crítico': 10, 'Alto': 5, 'Moderado': 2, 'Baixo': 1}

        # Criar coluna de pontos
        final_df['Pontos'] = final_df['Risco'].map(pesos).fillna(1)

        # Agrupar por Envolvido para somar pontos (opcional para o retorno da lista)
        score_df = final_df.groupby(['cpfCnpj', 'Nome'])['Pontos'].sum().reset_index()
        score_df = score_df.sort_values('Pontos', ascending=False)

        def classificar_risco(pontos):
            if pontos >= 20: return 'Altíssimo Risco'
            if pontos >= 10: return 'Alto Risco'
            return 'Médio Risco'

        score_df['Classificação Final'] = score_df['Pontos'].apply(classificar_risco)

    return final_df
    

# --- NOVO: Função para criar grafo de UMA comunicação ---
def create_communication_graph(df_envolvidos_comunicacao):
    """Cria um grafo NetworkX DIRECIONAL para os envolvidos de uma única comunicação,
       mostrando o fluxo: Remetente -> Titular -> Beneficiário."""
    G_comm = nx.DiGraph()

    # Dicionários para mapear nós para seus papéis
    node_roles = {}
    titulares = []
    remetentes = []
    beneficiarios = []
    outros_papeis = [] # Para sócios, responsáveis, outros, etc.

    # Adicionar nós com atributos
    for _, row in df_envolvidos_comunicacao.iterrows():
        node_id = str(row.get('cpfCnpjEnvolvido', 'DESCONHECIDO')).strip()
        if node_id == 'DESCONHECIDO': continue

        nome = normalize_string(row.get('nomeEnvolvido', 'DESCONHECIDO'))
        tipo = str(row.get('tipoEnvolvido', 'Desconhecido')).lower().strip()

        # Armazenar papel principal (se houver múltiplos para o mesmo CPF/CNPJ, priorizar Titular > Beneficiário > Remetente)
        if node_id not in node_roles or tipo == 'titular da conta' or tipo == 'titular':
             node_roles[node_id] = tipo
        elif tipo == 'beneficiário' and node_roles[node_id] != 'titular da conta' and node_roles[node_id] != 'titular':
             node_roles[node_id] = tipo
        elif tipo == 'remetente' and node_roles[node_id] not in ['titular da conta', 'titular', 'beneficiário']:
             node_roles[node_id] = tipo
        # Se já existe e o novo tipo não é prioritário, mantém o anterior (ou adiciona a outros se ainda não classificado)
        elif node_id not in node_roles:
            node_roles[node_id] = tipo

        # Adicionar nó ao grafo (se ainda não existir com os dados principais)
        if node_id not in G_comm:
            G_comm.add_node(
                node_id,
                label=nome,
                # Atributos booleanos (pegar da primeira ocorrência encontrada)
                pep=True if str(row.get('bitPepCitado', 'Não')).lower() == 'sim' else False,
                servidor=True if str(row.get('intServidorCitado', 'Não')).lower() == 'sim' else False
                # Role será adicionado depois com base no mapeamento final
            )

    # Classificar nós e adicionar atributo 'role' final
    for node_id, role in node_roles.items():
        if role == 'titular da conta' or role == 'titular':
            titulares.append(node_id)
            G_comm.nodes[node_id]['role'] = 'Titular' # Padronizar nome
        elif role == 'remetente':
            remetentes.append(node_id)
            G_comm.nodes[node_id]['role'] = 'Remetente'
        elif role == 'beneficiário' or role == 'beneficiario': # Acentuação
             beneficiarios.append(node_id)
             G_comm.nodes[node_id]['role'] = 'Beneficiário'
        else:
            outros_papeis.append(node_id)
            G_comm.nodes[node_id]['role'] = role.capitalize() # Capitalizar outros papéis

    # Adicionar Arestas Direcionais de Fluxo
    # Remetente(s) -> Titular(es)
    for r, t in product(remetentes, titulares):
        if G_comm.has_node(r) and G_comm.has_node(t):
            G_comm.add_edge(r, t, operation='Remessa')

    # Titular(es) -> Beneficiário(s)
    for t, b in product(titulares, beneficiarios):
         if G_comm.has_node(t) and G_comm.has_node(b):
            G_comm.add_edge(t, b, operation='Benefício')

    # Conectar Outros Papéis ao(s) Titular(es) (bidirecional para associação)
    if titulares: # Apenas se houver titular
        for o, t in product(outros_papeis, titulares):
            if G_comm.has_node(o) and G_comm.has_node(t):
                 # Evitar auto-loops se alguém for 'outro' e 'titular' por algum motivo
                 if o != t:
                    G_comm.add_edge(o, t, operation='Associado')
                    G_comm.add_edge(t, o, operation='Associado')
    elif len(G_comm.nodes()) > 1:
        # Se não há titular, criar uma ligação simples entre todos para mostrar que estão juntos
        # (Alternativa: não criar nenhuma aresta)
        st.caption("Sem titular definido, mostrando todos os envolvidos conectados.")
        for node1, node2 in combinations(G_comm.nodes(), 2):
            G_comm.add_edge(node1, node2, operation='Vínculo')
            # G_comm.add_edge(node2, node1, operation='Vínculo') # Opcional: bidirecional

    return G_comm, titulares # Retorna lista de titulares para destaque na visualização

# --- NOVO: Função para visualizar grafo de UMA comunicação ---
def visualize_communication_graph(G, titulares_cpf):
    """Gera visualização Pyvis para o grafo de uma comunicação, destacando titulares."""
    if G is None or G.number_of_nodes() == 0:
        st.warning("Grafo da comunicação está vazio.")
        return None

    net = Network(height="500px", width="100%", bgcolor="#f0f2f6", font_color="black", directed=True)

    for node in G.nodes():
        node_data = G.nodes[node]
        is_titular = node in titulares_cpf

        node_size = 25 if is_titular else 15
        node_color = "#E74C3C" if is_titular else \
                     "#FF6B6B" if node_data.get('pep', False) else \
                     "#FFD700" if node_data.get('servidor', False) else "#556270"

        net.add_node(
            node,
            label=node_data.get('label', 'DESCONHECIDO'),
            size=node_size,
            color=node_color,
            title=f"Nome: {node_data.get('label', 'N/A')}\n"
                  f"CPF/CNPJ: {node}\n"
                  f"Papel: {node_data.get('role', 'N/A')}\n"
                  f"PEP: {'Sim' if node_data.get('pep', False) else 'Não'}\n"
                  f"Servidor: {'Sim' if node_data.get('servidor', False) else 'Não'}" +
                  ("\n**Titular da Conta**" if is_titular else "")
        )

    for edge in G.edges(data=True):
        source, target, data = edge
        if source in G and target in G:
            net.add_edge(source, target, title=data.get('operation', 'conexão'))


    net.repulsion(node_distance=150, central_gravity=0.2, spring_length=100)
    net.show_buttons(filter_=['physics'])

    try:
        # --- CORRIGIDO: Sanitizar nome do arquivo ---
        file_id = "comm" # Default
        if titulares_cpf:
            # Remover caracteres inválidos do primeiro titular (ex: /, ., -)
            clean_cpf_cnpj = ''.join(filter(str.isalnum, titulares_cpf[0]))
            file_id = f"comm_{clean_cpf_cnpj}"

        suffix = f"_{file_id}.html"
        # --- FIM CORREÇÃO ---

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, mode='w', encoding='utf-8') as tmpfile:
            net.save_graph(tmpfile.name)
            return tmpfile.name
    except Exception as e:
        st.error(f"Erro ao gerar visualização do grafo da comunicação: {str(e)}")
        st.code(traceback.format_exc())
        return None

# --- NOVO: Função para gerar Diagrama de Sankey ---
def plot_sankey_fluxo(df_cred, df_deb, titular_nome):
    """
    Gera um Diagrama de Sankey conectando:
    Origens (Crédito) -> Titular -> Destinos (Débito)
    """
    if df_cred.empty and df_deb.empty:
        return None

    # Lista de nós (labels)
    # O índice 0 será sempre o Titular
    labels = [titular_nome]

    # Listas para construir os links
    sources = []
    targets = []
    values = []
    custom_data = [] # Para tooltip extra
    link_colors = [] # Cores dos fluxos

    # --- Processar Créditos (Origem -> Titular) ---
    # Titular é o alvo (target = 0)
    if not df_cred.empty:
        # Pegar Top 15 para não poluir o gráfico se houver muitos
        df_cred_top = df_cred.sort_values('Valor (R$)', ascending=False).head(15)

        for _, row in df_cred_top.iterrows():
            origem = row['Origem do Crédito']
            valor = row['Valor (R$)']

            if origem not in labels:
                labels.append(origem)

            idx_origem = labels.index(origem)

            sources.append(idx_origem)
            targets.append(0) # 0 é o Titular
            values.append(valor)
            custom_data.append(f"Crédito: {origem}")
            link_colors.append("rgba(46, 204, 113, 0.4)") # Verde translúcido

    # --- Processar Débitos (Titular -> Destino) ---
    # Titular é a fonte (source = 0)
    if not df_deb.empty:
        # Pegar Top 15
        df_deb_top = df_deb.sort_values('Valor (R$)', ascending=False).head(15)

        for _, row in df_deb_top.iterrows():
            destino = row['Destino do Débito']
            valor = row['Valor (R$)']

            if destino not in labels:
                labels.append(destino)

            idx_destino = labels.index(destino)

            sources.append(0) # 0 é o Titular
            targets.append(idx_destino)
            values.append(valor)
            custom_data.append(f"Débito: {destino}")
            link_colors.append("rgba(231, 76, 60, 0.4)") # Vermelho translúcido

    if not values:
        return None

    # Criar a figura
    fig = go.Figure(data=[go.Sankey(
        node = dict(
          pad = 15,
          thickness = 20,
          line = dict(color = "black", width = 0.5),
          label = labels,
          color = ["#3498DB"] + ["#556270"] * (len(labels)-1) # Azul para titular, cinza para outros
        ),
        link = dict(
          source = sources,
          target = targets,
          value = values,
          color = link_colors,
          hovertemplate='%{value:$.2f}<br />%{customdata}<extra></extra>',
          customdata = custom_data
    ))])

    fig.update_layout(
        title_text=f"Fluxo Financeiro: {titular_nome}",
        font_size=12,
        height=500
    )
    return fig
# --- NOVO: Funções para parsear 'informacoesAdicionais' ---

def parse_valor_br(valor_str):
    """Converte string de valor BRL (ex: '1.234,56') para float."""
    if isinstance(valor_str, (int, float)):
        return float(valor_str)
    if isinstance(valor_str, str):
        try:
            # Remove 'R$', espaços, pontos de milhar e troca vírgula decimal
            clean_val = valor_str.replace('R$', '').strip().replace('.', '').replace(',', '.')
            return float(clean_val)
        except ValueError:
            return 0.0 # Retorna 0 se a conversão falhar
    return 0.0

def extract_principais(text, section_keyword):
    """Extrai principais remetentes/destinatários de uma seção do texto."""
    items = []
    try:
        # Encontra a seção relevante (case-insensitive)
        match = re.search(rf"{section_keyword}.*?:\s*\n(.*?)(?=\n\s*\n|\Z)", text, re.IGNORECASE | re.DOTALL)
        if not match:
            # Tentar um padrão alternativo sem nova linha inicial explícita
             match = re.search(rf"{section_keyword}.*?:\s*(.*?)(?=\n\s*\n|\Z)", text, re.IGNORECASE | re.DOTALL)
        if match:
            section_text = match.group(1).strip()
            # Regex para encontrar itens: Nome - CPF/CNPJ (...) - X lançamento(s) no total de: R$ VALOR
            # Ou variações mais simples que podem aparecer
            pattern = re.compile(
                r"^\s*(.*?)\s*-\s*([0-9./-]+|\w+)\s*.*?-\s*[0-9]+\s*lançamento\(s\)\s*no total de:\s*R\$([0-9.,]+)",
                re.MULTILINE | re.IGNORECASE
            )
            # Tentar um padrão mais simples se o primeiro falhar (ex: Nome - R$ VALOR)
            pattern_simple = re.compile(
                r"^\s*-\s*([0-9.,]+%)\s*\(R\$\s*([0-9.,]+).*?\)\s*(?:via|para)\s*(?:CPF|CNPJ)?\s*[\d./-]+?\s*\((.*?)\)",
                 re.MULTILINE | re.IGNORECASE
            )


            matches = pattern.findall(section_text)
            if matches:
                for name, identifier, value_str in matches:
                    name = name.strip()
                    value = parse_valor_br(value_str)
                    if value > 0:
                        items.append({'Nome/Entidade': name, 'Valor (R$)': value})
            else:
                 # Tentar padrão alternativo (comum em outros bancos)
                 matches_simple = pattern_simple.findall(section_text)
                 for perc, value_str, name in matches_simple:
                     name = name.strip()
                     value = parse_valor_br(value_str)
                     if value > 0:
                         items.append({'Nome/Entidade': name, 'Valor (R$)': value})


            # Agregar valores para a mesma entidade (se nomes repetidos)
            if items:
                df_items = pd.DataFrame(items)
                df_agg = df_items.groupby('Nome/Entidade')['Valor (R$)'].sum().reset_index()
                # Pegar os Top N (ex: Top 10)
                df_agg = df_agg.sort_values('Valor (R$)', ascending=False).head(10)
                return df_agg
    except Exception as e:
        # Silenciosamente falha ou loga o erro se necessário
        # print(f"Erro ao extrair {section_keyword}: {e}")
        pass
    return pd.DataFrame(columns=['Nome/Entidade', 'Valor (R$)']) # Retorna DF vazio se falhar

# --- FUNÇÕES DE PARSING (v4.0 - Lógica do Usuário: Máquina de Estados) ---

def clean_value(value_str):
    """Converte string monetária (ex: '1.234,56' ou '1.234.56') para float."""
    if isinstance(value_str, (int, float)): return float(value_str)
    if not value_str or not isinstance(value_str, str): return 0.0
    try:
        # Remove tudo que não é dígito, ponto ou vírgula
        val = re.sub(r'[^\d.,]', '', value_str)
        # Caso brasileiro: 1.000,00 -> remove ponto, troca virgula por ponto
        if ',' in val and '.' in val:
            if val.find('.') < val.find(','): # 1.000,00
                val = val.replace('.', '').replace(',', '.')
            else: # 1,000.00 (formato US raro, mas possivel)
                val = val.replace(',', '')
        elif ',' in val: # 1000,00
            val = val.replace(',', '.')
        # Se só tem ponto (1000.00), o float() resolve
        return float(val)
    except ValueError:
        return 0.0

# --- FUNÇÃO DE PARSING REVISADA (v13.0 - Suporte Multi-Banco + CAIXA) ---

def extract_all_financial_data(text):
    """
    Extrai dados financeiros detectando automaticamente o padrão do relatório.
    Suporta:
    1. Padrão Lista/Tabular (Nubank/Genérico)
    2. Padrão Narrativo Denso (Itaú)
    3. Padrão Narrativo Lista (Sicoob)
    4. Padrão Lista Descritiva (Banco do Brasil)
    5. Padrão Tabular Rígido (Bradesco)
    6. Padrão Lista Detalhada (Santander)
    7. Padrão Tópicos Numerados (Caixa)
    """
    cred_cols = ['Origem do Crédito', 'Valor (R$)', 'Qtd Transações', 'Detalhe']
    deb_cols = ['Destino do Débito', 'Valor (R$)', 'Qtd Transações', 'Detalhe']
    card_cols = ['Estabelecimento', 'Valor (R$)', 'Qtd Transações']

    if not text:
        return pd.DataFrame(columns=cred_cols), pd.DataFrame(columns=deb_cols), pd.DataFrame(columns=card_cols)

    # Normalização básica
    text_norm = text.replace('−', '-').replace('–', '-').replace('—', '-')
    text_norm = text_norm.replace('•', '-').replace('•', '-')

    # --- PARSER 7: CAIXA ECONÔMICA FEDERAL ---
    # Padrão: R$ VALOR - NOME CNPJ DOC - ( DETALHES )
    def _parse_caixa_style(txt):
        credits = []
        debits = []

        # Regex Caixa: R$ VALOR - NOME DOC - ( DETALHES )
        # Ex: R$ 2.818.436,28 - ZOOP TECNOLOGIA... CNPJ 19... - ( 23 PIXs... )
        re_caixa = re.compile(
            r"R\$\s*(?P<val>[\d.,]+)\s*-\s*"        # Valor
            r"(?P<name>.*?)\s+"                     # Nome (até o doc)
            r"(?P<doc_type>CNPJ|CPF)\s*"            # Tipo Doc
            r"(?P<doc>[\d./-]+)\s*-\s*"             # Doc
            r"\(\s*(?P<details>.*?)\s*\)",          # Detalhes entre parênteses
            re.IGNORECASE | re.DOTALL
        )

        # Tentar extrair Qtd dos detalhes (ex: "23 PIXs")
        def extract_qtd(details_str):
            match_qtd = re.search(r"(\d+)\s+(?:PIX|TEV|DOC|TED|trans)", details_str, re.IGNORECASE)
            return int(match_qtd.group(1)) if match_qtd else 1

        # 1. Créditos
        match_cred = re.search(r"ORIGEM DOS RECURSOS:.*?\d+\.\s+Os principais créditos foram:(.*?)(?=DESTINO DOS RECURSOS:|4\.|TOTAL|$)", txt, re.IGNORECASE | re.DOTALL)
        if match_cred:
            block = match_cred.group(1)
            # Iterar sobre as linhas que parecem transações (R$ ...)
            for match in re_caixa.finditer(block):
                credits.append({
                    'Origem do Crédito': match.group('name').strip().upper(),
                    'Valor (R$)': clean_value(match.group('val')),
                    'Qtd Transações': extract_qtd(match.group('details')),
                    'Detalhe': f"{match.group('doc_type')}: {match.group('doc')}"
                })

        # 2. Débitos
        match_deb = re.search(r"DESTINO DOS RECURSOS:.*?\d+\.\s+Os principais débitos foram:(.*?)(?=CARACTERÍSTICAS|5\.|TOTAL|$)", txt, re.IGNORECASE | re.DOTALL)
        if match_deb:
            block = match_deb.group(1)
            for match in re_caixa.finditer(block):
                debits.append({
                    'Destino do Débito': match.group('name').strip().upper(),
                    'Valor (R$)': clean_value(match.group('val')),
                    'Qtd Transações': extract_qtd(match.group('details')),
                    'Detalhe': f"{match.group('doc_type')}: {match.group('doc')}"
                })

        return credits, debits, []

    # --- PARSER 1: SANTANDER ---
    def _parse_santander_style(txt):
        # ... (Código mantido v12.0) ...
        credits, debits = [], []
        re_santander = re.compile(r"-\s*(?P<name>.+?)\s+-\s+(?:CNPJ|CPF):\s*(?P<doc>[\d./-]+).*?Valor (?:Recebido|Enviado):\s*R\$(?P<val>[\d.,]+)", re.IGNORECASE)
        match_cred = re.search(r"Principais remetentes/depositantes identificados:(.*?)(?=Resumo de lancamentos a debito|Principais destinatarios|$)", txt, re.IGNORECASE | re.DOTALL)
        if match_cred:
            for match in re_santander.finditer(match_cred.group(1)):
                credits.append({'Origem do Crédito': match.group('name').strip().upper(), 'Valor (R$)': clean_value(match.group('val')), 'Qtd Transações': 1, 'Detalhe': f"Doc: {match.group('doc')}"})
        match_deb = re.search(r"Principais destinatarios de recursos identificados:(.*?)(?=Ao analisar|Conclusao|Informa|$)", txt, re.IGNORECASE | re.DOTALL)
        if match_deb:
            for match in re_santander.finditer(match_deb.group(1)):
                debits.append({'Destino do Débito': match.group('name').strip().upper(), 'Valor (R$)': clean_value(match.group('val')), 'Qtd Transações': 1, 'Detalhe': f"Doc: {match.group('doc')}"})
        return credits, debits, []

    # --- PARSER 2: BRADESCO ---
    def _parse_bradesco_style(txt):
        # ... (Código mantido v11.0) ...
        credits, debits = [], []
        txt_linear = ' '.join(txt.split())
        re_bradesco_item = re.compile(r"(?P<val>[\d]{1,3}(?:\.[\d]{3})*,\d{2})\s+(?P<qtd>\d+)\s*(?P<name>.+?)\s+(?P<doc>\d{11,14}|[\d.\-/]{14,18})", re.IGNORECASE)
        match_cred = re.search(r"Demonstramos os principais remetentes.*?:(.*?)((?:Os débitos|Total a débito|Demonstramos os principais favorecidos|$))", txt_linear, re.IGNORECASE)
        if match_cred:
            for match in re_bradesco_item.finditer(match_cred.group(1)):
                if "VALOR" in match.group('name').upper() or "REMETENTE" in match.group('name').upper(): continue
                credits.append({'Origem do Crédito': match.group('name').strip().upper(), 'Valor (R$)': clean_value(match.group('val')), 'Qtd Transações': int(match.group('qtd')), 'Detalhe': f"Doc: {match.group('doc')}"})
        match_deb = re.search(r"Demonstramos os principais favorecidos.*?:(.*?)((?:Notas:|Demonstramos por amostragem|Diante do exposto|$))", txt_linear, re.IGNORECASE)
        if match_deb:
            for match in re_bradesco_item.finditer(match_deb.group(1)):
                if "VALOR" in match.group('name').upper() or "FAVORECIDOS" in match.group('name').upper(): continue
                debits.append({'Destino do Débito': match.group('name').strip().upper(), 'Valor (R$)': clean_value(match.group('val')), 'Qtd Transações': int(match.group('qtd')), 'Detalhe': f"Doc: {match.group('doc')}"})
        return credits, debits, []

    # --- PARSER 3: BANCO DO BRASIL ---
    def _parse_bb_style(txt):
        # ... (Código mantido v10.0) ...
        credits, debits = [], []
        re_bb = re.compile(r"(?P<name>.*?)\s+-\s+(?P<doc>[\d./-]+)\s*(?:\(.*?\))?\s*-\s*(?P<qtd>\d+)\s+lançamento\(s\).*?:\s*R\$(?P<val>[\d.,]+)", re.IGNORECASE)
        match_cred = re.search(r"Principais remetentes/depositantes identificados:(.*?)(?=Resumo de lançamentos a débito|Principais destinatários|$)", txt, re.IGNORECASE | re.DOTALL)
        match_deb = re.search(r"Principais destinatários de recursos identificados:(.*?)(?=INFORMAÇÕES ADICIONAIS|$)", txt, re.IGNORECASE | re.DOTALL)
        if match_cred:
            for match in re_bb.finditer(match_cred.group(1)):
                credits.append({'Origem do Crédito': match.group('name').strip().upper(), 'Valor (R$)': clean_value(match.group('val')), 'Qtd Transações': int(match.group('qtd')), 'Detalhe': f"Doc: {match.group('doc')}"})
        if match_deb:
            for match in re_bb.finditer(match_deb.group(1)):
                debits.append({'Destino do Débito': match.group('name').strip().upper(), 'Valor (R$)': clean_value(match.group('val')), 'Qtd Transações': int(match.group('qtd')), 'Detalhe': f"Doc: {match.group('doc')}"})
        return credits, debits, []

    # --- PARSER 4: SICOOB ---
    def _parse_sicoob_style(txt):
        # ... (Código mantido v9.0) ...
        credits, debits = [], []
        re_sicoob = re.compile(r"(?P<date>\d{2}/\d{2}/\d{4})\s*-\s*R\$\s*(?P<val>[\d.,]+)\s*-\s*(?P<type>origem|destino):\s*(?P<name>.*?),\s*(?P<doc>[\d./-]+)(?:\.|\s+Bc\.|\s+Ag\.|$)", re.IGNORECASE)
        match_section = re.search(r"Análise de movimentações.*?((?:Para o movimento|No período).*?)(?=\*\*\*|Diante das informações|$)", txt, re.IGNORECASE | re.DOTALL)
        section_text = match_section.group(1) if match_section else txt
        for match in re_sicoob.finditer(section_text):
            val, tipo, nome, doc = clean_value(match.group('val')), match.group('type').lower(), match.group('name').strip().upper(), match.group('doc').strip()
            item = {'Valor (R$)': val, 'Qtd Transações': 1, 'Detalhe': f"Doc: {doc} ({match.group('date')})"}
            if 'origem' in tipo: credits.append({**item, 'Origem do Crédito': nome})
            elif 'destino' in tipo: debits.append({**item, 'Destino do Débito': nome})
        return credits, debits, []

    # --- PARSER 5: ITAÚ ---
    def _parse_itau_style(txt):
        # ... (Código mantido v9.0) ...
        credits, debits = [], []
        re_itau_item = re.compile(r"(?P<name>[^,:\n]+),\s+(?P<doc>\d{11,14})\s*(?:\[.*?\]|\s*-\s*Banco.*?)?\s*\(R\$\s*(?P<val>[\d.,]+)\)", re.IGNORECASE)
        match_cred = re.search(r"ORIGEM DOS RECURSOS.*?:(.*?)(?=DESTINO DOS RECURSOS|Total a débito|$)", txt, re.IGNORECASE | re.DOTALL)
        if match_cred:
            for match in re_itau_item.finditer(match_cred.group(1)):
                raw_name, clean_name = match.group('name').strip(), re.split(r"emitentes\(s\):|emitentes:", match.group('name').strip(), flags=re.IGNORECASE)[-1].strip()
                if len(clean_name) > 2: credits.append({'Origem do Crédito': clean_name.upper(), 'Valor (R$)': clean_value(match.group('val')), 'Qtd Transações': 1, 'Detalhe': f"Doc: {match.group('doc')}"})
        match_deb = re.search(r"DESTINO DOS RECURSOS.*?:(.*?)(?=ENQUADRAMENTO|SINAIS DE ALERTA|$)", txt, re.IGNORECASE | re.DOTALL)
        if match_deb:
            for match in re_itau_item.finditer(match_deb.group(1)):
                raw_name, clean_name = match.group('name').strip(), re.split(r"favorecidos\(s\):|favorecidos:", match.group('name').strip(), flags=re.IGNORECASE)[-1].strip()
                if len(clean_name) > 2: debits.append({'Destino do Débito': clean_name.upper(), 'Valor (R$)': clean_value(match.group('val')), 'Qtd Transações': 1, 'Detalhe': f"Doc: {match.group('doc')}"})
        return credits, debits, []

    # --- PARSER 6: NUBANK/PADRÃO ---
    def _parse_standard_style(txt):
        # ... (Código mantido v7.0) ...
        credits, debits, cards = [], [], []
        txt_proc = re.sub(r'(\s-\s\d{1,3}[.,]\d{1,2}%)', r'\n\1', txt)
        txt_proc = re.sub(r'(Origem dos creditos|Destino dos debitos|Total dos debitos|Uso do cartao de credito)', r'\n\1', txt_proc, flags=re.IGNORECASE)
        lines = txt_proc.split('\n')
        current_section = None
        re_cpf_cnpj = re.compile(r"-\s*([\d,.]+)%\s*\(R\$\s*([\d.,]+)\s*em\s*(\d+)\s*transa.*?\)\s*(?:via|para)\s*(?:CPF|CNPJ)\s*([\d.\-\/]+)\s*\((.*?)\)", re.IGNORECASE)
        re_general = re.compile(r"-\s*([\d,.]+)%\s*\(R\$\s*([\d.,]+)\s*em\s*(\d+)\s*transa.*?\)\s*(?:para|em)\s*(.*)", re.IGNORECASE)
        for line in lines:
            line = line.strip()
            if len(line) < 5: continue
            line_l = line.lower()
            if 'origem dos creditos' in line_l: current_section = 'CREDIT'; continue
            if 'destino dos debitos' in line_l or 'total dos debitos' in line_l: current_section = 'DEBIT'; continue
            if 'uso do cartao' in line_l or 'principais estabelecimentos' in line_l: current_section = 'CARD'; continue
            if current_section and line.startswith('-'):
                val, qtd, name, det = 0.0, 1, "N/A", ""
                match_doc = re_cpf_cnpj.search(line)
                match_gen = None
                if match_doc:
                    val, qtd, det, name = clean_value(match_doc.group(2)), int(match_doc.group(3)), f"Doc: {match_doc.group(4)}", match_doc.group(5).strip().upper()
                else:
                    match_gen = re_general.search(line)
                    if match_gen:
                        val, qtd, name_raw = clean_value(match_gen.group(2)), int(match_gen.group(3)), match_gen.group(4)
                        name = re.split(r'[.,;]\s|Segundo pesquisa|sendo a principal', name_raw, flags=re.IGNORECASE)[0].strip().upper()
                if val > 0:
                    item = {'Valor (R$)': val, 'Qtd Transações': qtd, 'Detalhe': det}
                    if current_section == 'CREDIT': credits.append({**item, 'Origem do Crédito': name})
                    elif current_section == 'DEBIT': debits.append({**item, 'Destino do Débito': name})
                    elif current_section == 'CARD': cards.append({**item, 'Estabelecimento': name})
        return credits, debits, cards

    # --- ROTEADOR DE PARSERS ---
    # Identificação via Keywords
    is_caixa = "INFORMAÇÕES CADASTRAIS:" in text_norm and "ORIGEM DOS RECURSOS:" in text_norm # Novo
    is_santander = "Valor Recebido:" in text_norm or "Valor Enviado:" in text_norm
    is_bradesco = "VALOR R$ QTDE REMETENTE" in text_norm or "VALOR R$ QTDE FAVORECIDOS" in text_norm
    is_bb = "Principais remetentes/depositantes identificados:" in text_norm and not is_santander
    is_sicoob = re.search(r"\d{2}/\d{2}/\d{4}\s*-\s*R\$.*?origem:|destino:", text_norm, re.IGNORECASE)
    is_itau = "principal(ais) emitentes(s)" in text_norm or "principal(ais) favorecidos(s)" in text_norm

    if is_caixa:
        c_data, d_data, card_data = _parse_caixa_style(text_norm)
    elif is_santander:
        c_data, d_data, card_data = _parse_santander_style(text_norm)
    elif is_bradesco:
        c_data, d_data, card_data = _parse_bradesco_style(text_norm)
    elif is_bb:
        c_data, d_data, card_data = _parse_bb_style(text_norm)
    elif is_sicoob:
        c_data, d_data, card_data = _parse_sicoob_style(text_norm)
    elif is_itau:
        c_data, d_data, card_data = _parse_itau_style(text_norm)
    else:
        c_data, d_data, card_data = _parse_standard_style(text_norm)

    # --- CONSTRUÇÃO DOS DATAFRAMES FINAIS (Mantido) ---
    def build_df(data_list, col_name, final_cols):
        if not data_list: return pd.DataFrame(columns=final_cols)
        df = pd.DataFrame(data_list)
        df_agg = df.groupby(col_name, as_index=False).agg({'Valor (R$)': 'sum', 'Qtd Transações': 'sum', 'Detalhe': 'first'})
        total = df_agg['Valor (R$)'].sum()
        df_agg['Percentual (%)'] = (df_agg['Valor (R$)'] / total * 100) if total > 0 else 0.0
        cols_order = [c for c in final_cols if c in df_agg.columns]
        return df_agg.sort_values('Valor (R$)', ascending=False)[cols_order]

    df_creditos = build_df(c_data, 'Origem do Crédito', cred_cols)
    df_debitos = build_df(d_data, 'Destino do Débito', deb_cols)
    df_cartao = build_df(card_data, 'Estabelecimento', card_cols)

    return df_creditos, df_debitos, df_cartao

def generate_word_cloud_and_keywords(text, max_words=50, top_n_keywords=10):
    """
    Gera uma nuvem de palavras, extrai os termos mais frequentes e
    identifica keywords financeiras relevantes, usando uma lista manual de stopwords.

    Retorna:
        tuple: (bytes_image, df_keywords, df_context) ou (None, None, None) se falhar.
    """
    if pd.isna(text) or not isinstance(text, str) or text.strip() == '':
        return None, None, None

    try:
        # 1. Pré-processamento básico
        text_lower = text.lower()
        # Remover pontuação e números (mantido)
        text_cleaned = re.sub(r'[\d' + string.punctuation + ']', ' ', text_lower)
        # Remover espaços extras (mantido)
        text_cleaned = ' '.join(text_cleaned.split())

        # --- NOVA LISTA MANUAL DE STOPWORDS ---
        stop_words_pt = [
            'de', 'a', 'o', 'que', 'e', 'do', 'da', 'em', 'um', 'para', 'é', 'com', 'não', 'uma',
            'os', 'no', 'se', 'na', 'por', 'mais', 'as', 'dos', 'como', 'mas', 'foi', 'ao', 'ele',
            'das', 'tem', 'à', 'seu', 'sua', 'ou', 'ser', 'quando', 'muito', 'há', 'nos', 'já',
            'está', 'eu', 'também', 'só', 'pelo', 'pela', 'até', 'isso', 'ela', 'entre', 'era',
            'depois', 'sem', 'mesmo', 'aos', 'ter', 'seus', 'quem', 'nas', 'me', 'esse', 'eles',
            'estão', 'você', 'tinha', 'foram', 'essa', 'num', 'nem', 'suas', 'meu', 'às', 'minha',
            'têm', 'numa', 'pelos', 'elas', 'havia', 'seja', 'qual', 'será', 'nós', 'tenho', 'lhe',
            'deles', 'essas', 'esses', 'pelas', 'este', 'fosse', 'dele', 'tu', 'te', 'vocês', 'vos',
            'lhes', 'meus', 'minhas', 'teu', 'tua', 'teus', 'tuas', 'nosso', 'nossa', 'nossos',
            'nossas', 'dela', 'delas', 'esta', 'estes', 'estas', 'aquele', 'aquela', 'aqueles',
            'aquelas', 'isto', 'aquilo', 'estou', 'está', 'estamos', 'estão', 'estive', 'esteve',
            'estivemos', 'estiveram', 'estava', 'estávamos', 'estavam', 'estivera', 'estivéramos',
            'esteja', 'estejamos', 'estejam', 'estivesse', 'estivéssemos', 'estivessem', 'estiver',
            'estivermos', 'estiverem', 'hei', 'há', 'havemos', 'hão', 'houve', 'houvemos', 'houveram',
            'houvera', 'houvéramos', 'haja', 'hajamos', 'hajam', 'houvesse', 'houvéssemos',
            'houvessem', 'houver', 'houvermos', 'houverem', 'houverei', 'houverá', 'houveremos',
            'houverão', 'houveria', 'houveríamos', 'houveriam', 'sou', 'somos', 'são', 'era', 'éramos',
            'eram', 'fui', 'foi', 'fomos', 'foram', 'fora', 'fôramos', 'seja', 'sejamos', 'sejam',
            'fosse', 'fôssemos', 'fossem', 'for', 'formos', 'forem', 'serei', 'será', 'seremos', 'serão',
            'seria', 'seríamos', 'seriam', 'tenho', 'tem', 'temos', 'têm', 'tinha', 'tínhamos',
            'tinham', 'tive', 'teve', 'tivemos', 'tiveram', 'tivera', 'tivéramos', 'tenha', 'tenhamos',
            'tenham', 'tivesse', 'tivéssemos', 'tivessem', 'tiver', 'tivermos', 'tiverem', 'terei',
            'terá', 'teremos', 'terão', 'teria', 'teríamos', 'teriam'
        ]
        # --- FIM NOVA LISTA ---

        # Adicionar stopwords customizadas (mantido)
        custom_stopwords = [
            'r', 'via', 'cnpj', 'cpf', 'banco', 'bco', 'agencia', 'conta', 'numero',
            'ltda', 'sa', 'eireli', 'me', 'epp', 'valor', 'reais', 'mes', 'periodo',
            'cliente', 'empresa', 'principal', 'utilizada', 'segundo', 'pesquisa',
            'base', 'dados', 'privada', 'referente', 'etc', 'nome', 'fantasia',
            'data', 'abertura', 'situacao', 'faturamento', 'presumido', 'socios',
            'atividade', 'porte', 'endereco', 'cep', 'nunca', 'antes', 'reportado',
            'pld', 'ft', 'identificado', 'sem', 'informacoes', 'sobre',
            'participacoes', 'societarias', 'midia', 'negativa', 'nao', 'sim',
            'total', 'principais', 'contrapartes', 'outras', 'restantes', 'sao',
            'oes', 'informacao', 'declarada', 'interna', 'atualizacao', 'cadastral',
            'registro', 'profissional', 'vinculo', 'empregaticio', 'desde', 'vez',
            'recibo', 'em', 'relevantes', 'titular', 'proprio', 'ja', 'razao', 'social',
            'idade', 'anos', 'estado', 'civil', 'nacionalidade', 'email', 'adicionais',
            'historico', 'relacionada', 'considerando', 'analisado',
            'ag', 'cnt', 'tipo', 'brl', 'uso', 'referem',
            'sendo', 'medio', 'mensal', 'estabelecimento',
            # Adicionar termos mais específicos do relatório
             'pesquisa', 'relacionamento', 'exercidos', 'pais', 'nascimento', 'brasil',
             'atividade', 'exercida', 'cadastro', 'renda', 'patrimonio', 'cadastrada',
             'atualizada', 'reputacional', 'supostamente', 'enquadrado', 'pessoa',
             'exposta', 'politicamente', 'no', 'entanto', 'possui', 'exposicao',
             'envolvimento', 'assertividade', 'alta', 'conjuge',
             'relacionamentos', 'responsavel', 'legal', 'socio', 'administrador',
             'participacao', 'sociedade', 'limitada', 'constituida', 'ambulatorial',
             'recursos', 'realizacao', 'exames', 'complementares', 'listas', 'csnu',
             'ofac', 'analise', 'vista', 'ativa',
             'desconsiderando', 'concessoes', 'internas', 'cred', 'str',
             'contas', 'externa', 'dif',
             'outros', 'meio',
             'cooperado', 'verificado', 'praticamente', 'diferentes',
             'somam', 'cerca', 'ultima', 'constava', 'solicitado',
             'declaracao', 'ir', 'confirmacao', 'diante', 'foram', 'identificados',
             'seguintes', 'pontos', 'indicam', 'apesar', 'ter', 'sido',
             'representa', 'vezes', 'ou', 'seja', 'superou', 'aproximadamente',
             'capacidade', 'perfil', 'observamos', 'forma', 'contumaz',
             'acima', 'havendo', 'grande', 'discrepancia', 'ultimos', 'aparentemente',
             'declara', 'rendimentos', 'integralidade', 'aparentando', 'possivel',
             'fisco', 'conforme', 'mil',
             # Mais termos comuns
             'este', 'esta', 'aquele', 'aquela', 'quanto', 'quantos', 'quantas',
             'tal', 'tais', 'nosso', 'nossa', 'vosso', 'vossa', 'seu', 'sua'
             ]
        all_stopwords = set(stop_words_pt).union(custom_stopwords) # Usa a lista manual

        words = [word for word in text_cleaned.split() if word not in all_stopwords and len(word) > 2]

        if not words:
             st.caption("Nenhuma palavra significativa encontrada após limpeza.")
             return None, None, None

        processed_text = ' '.join(words)

        # 3. Gerar Nuvem de Palavras (mantido)
        wordcloud = WordCloud(width=800, height=300, background_color='white',
                              colormap='viridis', max_words=max_words).generate(processed_text)
        img_buffer = io.BytesIO()
        plt.figure(figsize=(10, 4))
        plt.imshow(wordcloud, interpolation='bilinear')
        plt.axis('off')
        plt.tight_layout(pad=0)
        plt.savefig(img_buffer, format='png')
        plt.close()
        img_buffer.seek(0)
        bytes_image = img_buffer.getvalue()

        # 4. Extrair Keywords Financeiras Frequentes (mantido)
        word_freq = pd.Series(words).value_counts()
        df_freq = word_freq.reset_index()
        df_freq.columns = ['Palavra', 'Frequência']
        financial_keywords = [
            'pagamento', 'pago', 'pagamentos', 'fatura', 'compra', 'compras', 'gasto', 'gastos',
            'credito', 'creditos', 'creditado', 'recebido', 'recebimento', 'aporte', 'aportes',
            'debito', 'debitos', 'debitado', 'enviado', 'transferencia', 'transferencias', 'transf',
            'remessa', 'remessas', 'pix', 'ted', 'doc',
            'saque', 'saques', 'retirada', 'retiradas',
            'deposito', 'depositos', 'recursos', 'entradas'
            'aplicacao', 'investimento', 'resgate', 'resgates',
            'emprestimo', 'financiamento',
            'premio', 'aposta', 'arrecadacao',
            'especie'
            ]
        df_keywords = df_freq[df_freq['Palavra'].isin(financial_keywords)].head(top_n_keywords)

        # 5. Encontrar Contexto (mantido)
        context_snippets = {}
        if not df_keywords.empty:
            text_norm_context = text.replace('−', '-').replace('–', '-')
            sentences = re.split(r'[.!?]\s+', text_norm_context) # Aproximação por frases
            for keyword in df_keywords['Palavra']:
                found_snippets = []
                pattern_kw = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
                for sentence in sentences:
                    if pattern_kw.search(sentence):
                        snippet = sentence.strip()
                        if snippet: found_snippets.append(snippet)
                    if len(found_snippets) >= 3: break
                if found_snippets: context_snippets[keyword] = found_snippets

        return bytes_image, df_keywords, context_snippets

    except Exception as e:
        st.warning(f"Erro ao gerar nuvem de palavras ou extrair keywords: {e}")
        # st.code(traceback.format_exc()) # Opcional
        return None, None, None


def analise_benford(df):
    """Calcula e plota a Lei de Benford para os valores das transações."""
    if 'ValorTotal' not in df.columns or df.empty: return None

    # Pegar primeiro dígito de valores > 0
    valores = df[df['ValorTotal'] > 0]['ValorTotal'].astype(str).str[0].astype(int)
    # Filtrar apenas dígitos 1-9
    valores = valores[valores > 0]

    contagem = valores.value_counts(normalize=True).sort_index()
    df_benford = pd.DataFrame({'Dígito': contagem.index, 'Real (%)': contagem.values * 100})

    # Probabilidades esperadas por Benford
    import math
    df_benford['Esperado (%)'] = [math.log10(1 + 1/d) * 100 for d in df_benford['Dígito']]

    fig = px.bar(df_benford, x='Dígito', y=['Real (%)', 'Esperado (%)'], barmode='group',
                 title='Análise da Lei de Benford (Detecção de Anomalias Numéricas)')
    return fig

def render_analise_comunicacao(selected_indexador: str):
    """
    Renderiza todo o conteúdo da aba 'Análise por Comunicação'
    para o Indexador selecionado.
    Reutiliza st.session_state.dfcomunicacoes, dfenvolvidos, dfocorrencias, df_segmento_desc, etc.
    """
    import pandas as pd

    if (
        "df_comunicacoes" not in st.session_state
        or st.session_state.df_comunicacoes is None
        or st.session_state.df_comunicacoes.empty
    ):
        st.warning("DataFrame de comunicações não está disponível.")
        return

    df_comunicacoes = st.session_state.df_comunicacoes
    df_envolvidos = st.session_state.df_envolvidos
    df_ocorrencias = st.session_state.df_ocorrencias

    # Filtrar dados para o Indexador selecionado (mesma lógica da aba 5)
    comunicacao_detalhe = df_comunicacoes[df_comunicacoes["Indexador"].astype(str) == str(selected_indexador)]
    envolvidos_detalhe = df_envolvidos[
        df_envolvidos["Indexador"].astype(str).str.strip() == str(selected_indexador).strip()
    ]
    ocorrencias_detalhe = df_ocorrencias[df_ocorrencias["Indexador"].astype(str) == str(selected_indexador)]

    if comunicacao_detalhe.empty:
        st.warning(f"Nenhum detalhe de comunicação encontrado para o Indexador {selected_indexador}.")
        return

    comunicacao_info = comunicacao_detalhe.iloc[0]

    # A partir daqui, copie exatamente o conteúdo que hoje está dentro de `if selected_indexador != "Selecione"...`
    # na aba "Análise por Comunicação": métricas gerais, Campos A–E, titulares, infos adicionais, wordcloud,
    # fluxos, gráficos, grafo da comunicação etc., só substituindo `selectedindexador` pela variável local.
    # Exemplo simplificado:

    if selected_indexador != "Selecione...":
        st.subheader(f"Detalhes da Comunicação Indexador: {selected_indexador}")

        # Filtrar dados para o Indexador selecionado
        comunicacao_detalhe = st.session_state.df_comunicacoes[st.session_state.df_comunicacoes['Indexador'] == selected_indexador]
        envolvidos_detalhe = st.session_state.df_envolvidos[st.session_state.df_envolvidos['Indexador'].astype(str).str.strip() == str(selected_indexador).strip()]
        ocorrencias_detalhe = st.session_state.df_ocorrencias[st.session_state.df_ocorrencias['Indexador'] == selected_indexador]

        if not comunicacao_detalhe.empty:
            comunicacao_info = comunicacao_detalhe.iloc[0] # Pega a primeira (e única) linha
            # Exibir Informações Gerais da Comunicação
            col1_comm, col2_comm, col3_comm = st.columns(3)
            with col1_comm:
                st.metric("ID Comunicação", comunicacao_info.get('idComunicacao', 'N/A'))
                st.metric("Data Operação", comunicacao_info.get('Data_da_operacao', pd.NaT).strftime('%d/%m/%Y') if pd.notna(comunicacao_info.get('Data_da_operacao')) else 'N/A')
            with col2_comm:
                st.metric("Comunicante", comunicacao_info.get('nomeComunicante', 'N/A'))
                st.metric("Cidade/UF Agência", f"{comunicacao_info.get('CidadeAgencia', 'N/A')} / {comunicacao_info.get('UFAgencia', 'N/A')}")
            with col3_comm:
                st.metric("Segmento", comunicacao_info.get('CodigoSegmento', 'N/A'))
                # Buscar descrição do segmento
                desc_campos = df_segmento_desc[df_segmento_desc['CodigoSegmento'] == str(comunicacao_info.get('CodigoSegmento', ''))]
                if not desc_campos.empty:
                    #st.caption(f"Descrição Campos: {desc_campos['DescricaoCampos'].iloc[0]}")
                    st.info(f"Descrição Campos do Segmento: {desc_campos['DescricaoCampos'].iloc[0]}")
                else:
                    st.caption("Descrição Campos: Segmento não mapeado")

                st.divider()

                # --- NOVO: Exibir Titular(es) da Comunicação (com DESTAQUE) ---
                st.subheader("👤 Titular(es) da Comunicação")
                if not envolvidos_detalhe.empty:
                    # Filtrar pelos papéis de titular
                    titulares_df = envolvidos_detalhe[
                        envolvidos_detalhe['tipoEnvolvido'].str.lower().isin(['titular', 'titular da conta'])
                    ]

                    if not titulares_df.empty:
                        # Exibir cada titular encontrado
                        for _, titular_row in titulares_df.iterrows():
                            nome_titular = titular_row.get('nomeEnvolvido', 'N/A')
                            cpf_titular = titular_row.get('cpfCnpjEnvolvido', 'N/A')

                            # Formatar tags de PEP e Servidor com estilo
                            pep_info = ""
                            servidor_info = ""
                            if str(titular_row.get('bitPepCitado', 'Não')).lower() == 'sim':
                                # Estilo para a tag PEP (fundo vermelho, texto branco)
                                pep_info = ' <span style="background-color: #FF6B6B; color: #FFF; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; font-weight: bold;">PEP</span>'
                        if str(titular_row.get('intServidorCitado', 'Não')).lower() == 'sim':
                            # Estilo para a tag Servidor (fundo amarelo, texto escuro)
                            servidor_info = ' <span style="background-color: #FFD700; color: #333; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; font-weight: bold;">SERVIDOR</span>'

                            # --- MODIFICADO: Bloco HTML para destaque ---
                            # Usamos um <div> com estilo para criar a caixa.
                            # Ajuste as cores (background-color, border, color) para o seu tema.
                            # Estas cores são otimizadas para o tema escuro das suas screenshots.
                            st.markdown(f"""
                            <div style="background-color: #222226; border: 1px solid #4C4E54; border-radius: 7px; padding: 12px; margin-bottom: 10px;">
                                <div style="font-size: 1.25em; font-weight: bold; color: #FAFAFA; margin-bottom: 5px;">
                                    {nome_titular} {pep_info} {servidor_info}
                                </div>
                                <div style="font-size: 1.1em; color: #ADADAD; font-family: monospace;">
                                    {cpf_titular}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            # --- FIM MODIFICAÇÃO ---
                        else:
                            st.info("Nenhum envolvido com papel 'Titular' ou 'Titular da Conta' encontrado para este Indexador.")
                    else:
                        st.info("Nenhum envolvido encontrado para este Indexador.")
                    # --- FIM NOVO ---

                    st.divider()

                    # Exibir Valores (Campos A-E) em destaque
                    st.subheader("Valores Reportados")
                    val_cols = st.columns(5)
                    campos = ['A', 'B', 'C', 'D', 'E']
                    for i, campo in enumerate(campos):
                        valor_col_name = f'ValorCampo{campo}'
                        if valor_col_name in comunicacao_info and pd.notna(comunicacao_info[valor_col_name]):
                            with val_cols[i]:
                                st.metric(f"Valor Campo {campo}", f"R$ {comunicacao_info[valor_col_name]:,.2f}")
                        else:
                             with val_cols[i]:
                                st.metric(f"Valor Campo {campo}", "R$ 0,00") # Ou N/A

                    st.divider()

                    # Exibir Informações Adicionais
                    st.subheader("Informações Adicionais")
                    st.info("⚠️ IMPORTANTE. Nunca usar LLM abertas para analisar esses dados.")

                    info_adicional = comunicacao_info.get('informacoesAdicionais', 'Nenhuma informação adicional disponível.')
                    if pd.isna(info_adicional) or info_adicional.strip() == '':
                         info_adicional = 'Nenhuma informação adicional disponível.'
                    # Usar text_area para textos longos, definir altura
                    st.markdown(f"""
                    <div style="height: 300px; overflow-y: auto; border: 1px solid #e0e0e0; padding: 10px; border-radius: 5px; background-color: #f9f9f9; color: #333;">
                        {info_adicional.replace('<','&lt;').replace('>','&gt;')}
                    </div>
                    """, unsafe_allow_html=True)
                    # st.code(info_adicional, language=None) # language=None evita highlight # Mostra o conteúdo em uma única linha permitindo cópia.
                    # st.text_area("Detalhes:", value=info_adicional, height=300, disabled=True, key=f"info_{selected_indexador}") # Mostra o conteúdo bloqueado.

                    # --- NOVO: Nuvem de Palavras e Keywords ---
                    st.divider()
                    st.subheader("Nuvem de Palavras e Termos Financeiros Frequentes")
                    with st.spinner("Gerando nuvem de palavras e analisando termos..."):
                         wordcloud_img, df_fin_keywords, context_map = generate_word_cloud_and_keywords(info_adicional)

                    if wordcloud_img:
                        st.image(wordcloud_img, caption="Nuvem das palavras mais frequentes (após remoção de stopwords)")
                    else:
                        st.caption("Não foi possível gerar a nuvem de palavras.")

                    if df_fin_keywords is not None and not df_fin_keywords.empty:
                        st.markdown("##### Top Termos Financeiros:")
                        st.dataframe(df_fin_keywords, hide_index=True, width=400) # Tabela menor

                        st.markdown("##### Contexto dos Termos:")
                        if context_map:
                            for keyword, snippets in context_map.items():
                                with st.expander(f"Contexto para '{keyword}' ({len(snippets)} trechos)"):
                                    for i, snippet in enumerate(snippets):
                                        #st.markdown(f"_{i+1}_: ...{snippet}...") # Usar markdown para itálico
                                        st.text_area(
                                        label=f"Trecho {i+1}", # Rótulo para a caixa de texto
                                        value=snippet,
                                        height=100, # Ajuste a altura conforme necessário
                                        key=f"context_{selected_indexador}_{keyword}_{i}" # Chave única
                                        )
                                        if i < len(snippets) - 1: st.markdown("---") # Divisor
                        else:
                            st.caption("Não foi possível encontrar contexto para os termos financeiros.")
                    elif wordcloud_img: # Se a nuvem foi gerada mas keywords não
                         st.caption("Nenhum termo financeiro relevante encontrado entre as palavras mais frequentes.")
                    # --- FIM NOVO ---

                    st.divider()

                    # Exibir Ocorrências Vinculadas
                    st.subheader("Ocorrências Vinculadas")
                    if not ocorrencias_detalhe.empty:
                        st.dataframe(ocorrencias_detalhe[['idOcorrencia', 'Ocorrencia']], width='stretch', hide_index=True)
                    else:
                        st.info("Nenhuma ocorrência vinculada encontrada para este Indexador.")

                    st.divider()

                    # Exibir Envolvidos Vinculados
                    st.subheader("Envolvidos Vinculados")
                    if not envolvidos_detalhe.empty:
                        # Selecionar e formatar colunas para exibição
                        cols_envolvidos = ['cpfCnpjEnvolvido', 'nomeEnvolvido', 'tipoEnvolvido',
                                           'bitPepCitado', 'bitPessoaObrigadaCitado', 'intServidorCitado',
                                           'agenciaEnvolvido', 'contaEnvolvido']
                        cols_envolvidos_exist = [c for c in cols_envolvidos if c in envolvidos_detalhe.columns]

                        # Criar cópia para formatação
                        envolvidos_display = envolvidos_detalhe[cols_envolvidos_exist].copy()

                        # Formatar booleanos
                        for flag in ['bitPepCitado', 'bitPessoaObrigadaCitado', 'intServidorCitado']:
                             if flag in envolvidos_display.columns:
                                 envolvidos_display[flag] = envolvidos_display[flag].apply(lambda x: "Sim" if str(x).lower()=='sim' or x==True else "Não")

                        st.dataframe(envolvidos_display, width='stretch', hide_index=True,
                                     column_config={
                                         "cpfCnpjEnvolvido": "CPF/CNPJ",
                                         "nomeEnvolvido": "Nome",
                                         "tipoEnvolvido": "Papel",
                                         "bitPepCitado": "PEP",
                                         "bitPessoaObrigadaCitado": "P. Obrigada",
                                         "intServidorCitado": "Servidor P.",
                                         "agenciaEnvolvido": "Agência Env.",
                                         "contaEnvolvido": "Conta Env."
                                     })
                    else:
                        st.info("Nenhum envolvido vinculado encontrado para este Indexador.")


                    # --- NOVO: Visualização do Grafo da Comunicação ---
                    st.divider()
                    st.subheader("Visualização dos Vínculos na Comunicação")
                    if not envolvidos_detalhe.empty:
                        with st.spinner("Gerando grafo da comunicação..."):
                            G_comm, titulares_comm = create_communication_graph(envolvidos_detalhe)

                        if G_comm.number_of_nodes() > 0:

                            # Visualizar o grafo
                            with st.spinner("Renderizando visualização do grafo..."):
                                comm_graph_file = visualize_communication_graph(G_comm, titulares_comm)

                            if comm_graph_file:
                                st.components.v1.html(open(comm_graph_file, 'r', encoding='utf-8').read(), height=550)
                                st.html(generate_network_legend())
                            else:
                                st.warning("Não foi possível renderizar o grafo da comunicação.")
                        else:
                            st.info("Não há envolvidos suficientes ou válidos para gerar um grafo para esta comunicação.")
                    else:
                        st.info("Não há envolvidos vinculados para gerar o grafo.")


                    # --- MODIFICADO: Tabelas e Gráficos de Fluxo Baseados em Informações Adicionais ---
                    st.divider()
                    st.subheader("Resumo do Fluxo (Extraído de Informações Adicionais)")
                    st.info("⚠️ IMPORTANTE. É possível que esses dados estejam incompletos. Os valores aqui informados não substituem a análise mais detida do conteúdo do campo Informações Adicionais.")

                    if pd.notna(info_adicional) and info_adicional != 'Nenhuma informação adicional disponível.':
                        with st.spinner("Analisando texto de informações adicionais..."):
                            # Chamar a nova função que retorna 3 DataFrames
                            df_creditos_ext, df_debitos_ext, df_cartao_ext = extract_all_financial_data(info_adicional)

                            # --- NOVO: Diagrama de Sankey ---
                            st.markdown("##### 🌊 Diagrama de Fluxo (Sankey)")

                            # Determinar o nome do titular para o centro do gráfico
                            nome_titular_sankey = "Titular/Conta"
                            # Tentar pegar o nome do titular identificado anteriormente na aba
                            if not envolvidos_detalhe.empty:
                                 tits = envolvidos_detalhe[envolvidos_detalhe['tipoEnvolvido'].str.lower().isin(['titular', 'titular da conta'])]
                                 if not tits.empty:
                                     nome_titular_sankey = tits.iloc[0]['nomeEnvolvido']

                            if not df_creditos_ext.empty or not df_debitos_ext.empty:
                                fig_sankey = plot_sankey_fluxo(df_creditos_ext, df_debitos_ext, nome_titular_sankey)
                                if fig_sankey:
                                    st.plotly_chart(fig_sankey, use_container_width=True)
                                else:
                                    st.caption("Dados insuficientes para gerar o diagrama de fluxo.")
                            # --- FIM NOVO ---
                        # --- FIM MODIFICAÇÃO ---

                        st.markdown("##### Principais Origens de Crédito")
                        if not df_creditos_ext.empty:
                            # Ordenar por valor para exibição
                            df_creditos_ext = df_creditos_ext.sort_values('Valor (R$)', ascending=False)
                            st.dataframe(df_creditos_ext, width='stretch', hide_index=True,
                                         column_config={
                                            "Valor (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                                            "Percentual (%)": st.column_config.NumberColumn(format="%.2f%%")
                                            # Remover 'Detalhe' se não estiver mais presente
                                         })
                            fig_cred = px.bar(df_creditos_ext.head(10), y='Origem do Crédito', x='Valor (R$)',
                                              orientation='h', title='Top 10 Origens de Crédito',
                                              labels={'Origem do Crédito': 'Origem', 'Valor (R$)': 'Valor Recebido (R$)'},
                                              text='Valor (R$)', height=400)
                            fig_cred.update_traces(texttemplate='R$ %{x:,.2f}', textposition='outside')
                            fig_cred.update_layout(yaxis={'categoryorder':'total ascending'})
                            st.plotly_chart(fig_cred, use_container_width=True)
                        # else: st.caption("Não foi possível extrair origens de crédito.") # Já tratado na função

                        st.markdown("##### Principais Destinos de Débito")
                        if not df_debitos_ext.empty:
                            # Ordenar por valor para exibição
                            df_debitos_ext = df_debitos_ext.sort_values('Valor (R$)', ascending=False)
                            st.dataframe(df_debitos_ext, width='stretch', hide_index=True,
                                         column_config={
                                            "Valor (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                                            "Percentual (%)": st.column_config.NumberColumn(format="%.2f%%")
                                            # Remover 'Detalhe' se não estiver mais presente
                                         })
                            fig_deb = px.bar(df_debitos_ext.head(10), y='Destino do Débito', x='Valor (R$)',
                                             orientation='h', title='Top 10 Destinos de Débito',
                                             labels={'Destino do Débito': 'Destino', 'Valor (R$)': 'Valor Enviado (R$)'},
                                             text='Valor (R$)', height=400)
                            fig_deb.update_traces(texttemplate='R$ %{x:,.2f}', textposition='outside')
                            fig_deb.update_layout(yaxis={'categoryorder':'total ascending'})
                            st.plotly_chart(fig_deb, use_container_width=True)
                        # else: st.caption("Não foi possível extrair destinos de débito.") # Já tratado na função

                        st.markdown("##### Principais Gastos no Cartão")
                        if not df_cartao_ext.empty:
                             # Ordenar por valor para exibição
                             df_cartao_ext = df_cartao_ext.sort_values('Valor (R$)', ascending=False)
                             st.dataframe(df_cartao_ext, width='stretch', hide_index=True,
                                         column_config={
                                            "Valor (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                                            "Percentual (%)": st.column_config.NumberColumn(format="%.2f%%")
                                         })
                             fig_card = px.bar(df_cartao_ext.head(10), y='Estabelecimento', x='Valor (R$)',
                                               orientation='h', title='Top 10 Gastos no Cartão de Crédito',
                                               labels={'Estabelecimento': 'Estabelecimento', 'Valor (R$)': 'Valor Gasto (R$)'},
                                               text='Valor (R$)', height=400)
                             fig_card.update_traces(texttemplate='R$ %{x:,.2f}', textposition='outside')
                             fig_card.update_layout(yaxis={'categoryorder':'total ascending'})
                             st.plotly_chart(fig_card, use_container_width=True)
                        # else: st.caption("Não foi possível extrair gastos no cartão.") # Já tratado na função

                    else:
                        st.info("Campo 'Informações Adicionais' vazio ou indisponível para gerar gráficos de fluxo.")
                    # --- FIM MODIFICAÇÃO Bloco Gráficos ---

                else:
                    st.warning(f"Nenhum detalhe de comunicação encontrado para o Indexador {selected_indexador}.")
            #else:
            #    st.info("Selecione um Indexador na lista acima para ver os detalhes.")
    

# ==============================================
# INTERFACE PRINCIPAL
# ==============================================

# Upload de arquivos
st.sidebar.header("📤 Carregamento de Dados")
file_ocorrencias = st.sidebar.file_uploader("Ocorrencias.csv", type=['csv'], key="up_ocor")
file_envolvidos = st.sidebar.file_uploader("Envolvidos.csv", type=['csv'], key="up_env")
file_comunicacoes = st.sidebar.file_uploader("Comunicacoes.csv", type=['csv'], key="up_comm")

# Inicializar variáveis de estado
if 'df_final' not in st.session_state: st.session_state.df_final = None
if 'df_ocorrencias' not in st.session_state: st.session_state.df_ocorrencias = None
if 'df_envolvidos' not in st.session_state: st.session_state.df_envolvidos = None
if 'df_comunicacoes' not in st.session_state: st.session_state.df_comunicacoes = None
if 'data_loaded' not in st.session_state: st.session_state.data_loaded = False


# Processar dados
process_button = st.sidebar.button("Processar Arquivos Carregados")

# --- DEBUGGING ---
# st.sidebar.write(f"Botão Processar Pressionado: {process_button}")
# st.sidebar.write(f"Arquivo Ocorrencias: {'Carregado' if file_ocorrencias else 'Não Carregado'}")
# st.sidebar.write(f"Arquivo Envolvidos: {'Carregado' if file_envolvidos else 'Não Carregado'}")
# st.sidebar.write(f"Arquivo Comunicacoes: {'Carregado' if file_comunicacoes else 'Não Carregado'}")
# --- FIM DEBUGGING ---


if process_button and file_ocorrencias and file_envolvidos and file_comunicacoes:
    st.info("Iniciando processamento...") # Mensagem visível
    st.session_state.data_loaded = False
    with st.spinner('🔍 Processando dados iniciais... Pode levar alguns minutos.'):
        try:
            st.write("Passo 1: Carregando dados...")
            df_ocorrencias_raw = load_data(file_ocorrencias)
            df_envolvidos_raw = load_data(file_envolvidos)
            df_comunicacoes_raw = load_data(file_comunicacoes)

            if df_ocorrencias_raw is None or df_envolvidos_raw is None or df_comunicacoes_raw is None:
                st.error("Erro no carregamento. Verifique os arquivos e logs.")
                st.stop()
            st.write("Passo 1: Carregamento concluído.")

            st.write("Passo 2: Verificando colunas...")
            expected_cols_ocorrencias = ['Indexador', 'idOcorrencia', 'Ocorrencia']
            expected_cols_envolvidos = ['Indexador', 'cpfCnpjEnvolvido', 'nomeEnvolvido', 'tipoEnvolvido', 'bitPepCitado','bitPessoaObrigadaCitado', 'intServidorCitado']
            expected_cols_comunicacoes = ['Indexador', 'idComunicacao', 'Data_da_operacao', 'CodigoSegmento', 'CampoA']

            checks_ok = True
            if not check_columns(df_ocorrencias_raw, expected_cols_ocorrencias, "Ocorrencias.csv"): checks_ok = False
            if not check_columns(df_envolvidos_raw, expected_cols_envolvidos, "Envolvidos.csv"): checks_ok = False
            if not check_columns(df_comunicacoes_raw, expected_cols_comunicacoes, "Comunicacoes.csv"): checks_ok = False
            if not checks_ok: st.stop()
            st.write("Passo 2: Verificação de colunas concluída.")

            st.write("Passo 3: Pré-processamento e Conversões...")
            df_ocorrencias = df_ocorrencias_raw.copy()
            df_envolvidos = df_envolvidos_raw.copy()
            df_comunicacoes = df_comunicacoes_raw.copy()

            df_envolvidos['Indexador'] = df_envolvidos['Indexador'].astype(str).str.strip()
            df_comunicacoes['Indexador'] = df_comunicacoes['Indexador'].astype(str).str.strip()
            df_comunicacoes['CodigoSegmento'] = df_comunicacoes['CodigoSegmento'].astype(str).str.split('.').str[0].str.strip()
            df_ocorrencias['Indexador'] = df_ocorrencias['Indexador'].astype(str).str.strip()
            df_envolvidos['cpfCnpjEnvolvido'] = df_envolvidos['cpfCnpjEnvolvido'].astype(str).str.strip()

            # Limpeza e conversão de valores
            st.write("Convertendo valores numéricos (Campos A-E)...")
            for campo in ['CampoA', 'CampoB', 'CampoC', 'CampoD', 'CampoE']:
                 if campo in df_comunicacoes.columns:
                     df_comunicacoes[f'Valor{campo}'] = clean_numeric_br(df_comunicacoes[campo])
                 else:
                      df_comunicacoes[f'Valor{campo}'] = 0.0 # Usar float

            if 'ValorCampoA' not in df_comunicacoes.columns: df_comunicacoes['ValorCampoA'] = 0.0
            df_comunicacoes['ValorTotal'] = df_comunicacoes['ValorCampoA']
            st.write("Passo 3: Pré-processamento concluído.")

            st.write("Passo 4: Realizando merges...")
            comm_cols_merge_base = ['Indexador', 'idComunicacao', 'Data_da_operacao', 'CodigoSegmento', 'ValorTotal']
            #comm_cols_merge_vals = [f'Valor{c}' for c in ['A','B','C','D','E'] if f'Valor{c}' in df_comunicacoes.columns]
            comm_cols_merge_vals = [f'ValorCampo{c}' for c in ['A','B','C','D','E'] if f'ValorCampo{c}' in df_comunicacoes.columns]
            comm_cols_merge_info = ['informacoesAdicionais', 'CidadeAgencia', 'NumeroAgencia', 'UFAgencia']
            comm_cols_merge = list(set(comm_cols_merge_base + comm_cols_merge_vals + comm_cols_merge_info).intersection(df_comunicacoes.columns))

            env_cols_merge_base = ['Indexador', 'cpfCnpjEnvolvido', 'nomeEnvolvido', 'tipoEnvolvido', 'bitPepCitado', 'bitPessoaObrigadaCitado', 'intServidorCitado']
            env_cols_merge_data = ['DataAberturaConta']
            env_cols_merge = list(set(env_cols_merge_base + env_cols_merge_data).intersection(df_envolvidos.columns))

            ocor_cols_merge = ['Indexador', 'idOcorrencia', 'Ocorrencia']
            ocor_cols_merge = [col for col in ocor_cols_merge if col in df_ocorrencias.columns]

            if 'Indexador' not in comm_cols_merge: comm_cols_merge.append('Indexador')
            if 'Indexador' not in env_cols_merge: env_cols_merge.append('Indexador')
            if 'Indexador' not in ocor_cols_merge: ocor_cols_merge.append('Indexador')

            df_merged_comm_env = safe_merge(df_comunicacoes[comm_cols_merge], df_envolvidos[env_cols_merge], 'Indexador', 'Indexador', how='left', suffixes=('_comm', '_env'))
            if df_merged_comm_env is None: st.stop()
            st.write(f"Merge 1 OK: {len(df_merged_comm_env)} linhas.")

            df_final_merged = safe_merge(df_merged_comm_env, df_ocorrencias[ocor_cols_merge], 'Indexador', 'Indexador', how='left', suffixes=('', '_ocor'))
            if df_final_merged is None: st.stop()
            st.write(f"Merge 2 OK: {len(df_final_merged)} linhas.")
            st.write("Passo 4: Merges concluídos.")

            st.write("Passo 5: Processamento final...")
            # Renomear Indexador
            if 'Indexador_comm' in df_final_merged.columns:
                 df_final_merged.rename(columns={'Indexador_comm': 'Indexador_x'}, inplace=True)
            elif 'Indexador_x' not in df_final_merged.columns and 'Indexador' in df_final_merged.columns:
                 df_final_merged.rename(columns={'Indexador': 'Indexador_x'}, inplace=True)
            # Garantir que Indexador_x exista
            if 'Indexador_x' not in df_final_merged.columns:
                st.error("Coluna 'Indexador_x' não pôde ser criada após merges.")
                st.stop()


            # Converter flags booleanas
            bool_flags = ['bitPepCitado','bitPessoaObrigadaCitado', 'intServidorCitado']
            for flag in bool_flags:
                if flag in df_final_merged.columns:
                    df_final_merged[flag] = df_final_merged[flag].apply(lambda x: True if str(x).strip().lower() == 'sim' else False).fillna(False).astype(bool)
                else:
                    df_final_merged[flag] = False

            # Normalizar nomes e preencher NaNs
            df_final_merged['nomeEnvolvido'] = df_final_merged['nomeEnvolvido'].fillna('DESCONHECIDO').apply(normalize_string)
            df_final_merged['cpfCnpjEnvolvido'] = df_final_merged['cpfCnpjEnvolvido'].fillna('DESCONHECIDO').astype(str).str.strip()

            # --- NOVO: Extrair Ano e Mês da Data da Operação ---
            st.write("Extraindo Ano/Mês...")
            if 'Data_da_operacao' in df_final_merged.columns and pd.api.types.is_datetime64_any_dtype(df_final_merged['Data_da_operacao']):
                # Usar .dt accessor apenas em dados não nulos para evitar erros
                mask_notna = df_final_merged['Data_da_operacao'].notna()
                df_final_merged.loc[mask_notna, 'Ano'] = df_final_merged.loc[mask_notna, 'Data_da_operacao'].dt.year
                df_final_merged.loc[mask_notna, 'Mes'] = df_final_merged.loc[mask_notna, 'Data_da_operacao'].dt.month
                # Preencher NaNs com um valor padrão ou deixar como NaN (vamos preencher com 0 ou string 'N/A')
                df_final_merged['Ano'].fillna(0, inplace=True) # Ou 'N/A'
                df_final_merged['Mes'].fillna(0, inplace=True) # Ou 'N/A'
                # Converter para inteiros (se não usou 'N/A')
                df_final_merged['Ano'] = df_final_merged['Ano'].astype(int)
                df_final_merged['Mes'] = df_final_merged['Mes'].astype(int)
                st.write("Colunas Ano/Mês adicionadas.")
            else:
                st.warning("Coluna 'Data_da_operacao' não encontrada ou não é do tipo data. Filtro Ano/Mês indisponível.")
                df_final_merged['Ano'] = 0 # Adicionar colunas vazias para evitar erros posteriores
                df_final_merged['Mes'] = 0


            # Adicionar Descrição dos Campos do Segmento
            if 'CodigoSegmento' in df_final_merged.columns:
                df_final_merged['CodigoSegmento'] = df_final_merged['CodigoSegmento'].astype(str).str.strip()
                df_final_merged = pd.merge(df_final_merged, df_segmento_desc, on='CodigoSegmento', how='left')
                df_final_merged['DescricaoCampos'] = df_final_merged['DescricaoCampos'].fillna('Segmento não mapeado')
            else:
                df_final_merged['DescricaoCampos'] = 'Segmento não disponível'

            # Reconverter colunas de data
            if 'Data_da_operacao' in df_final_merged.columns:
                df_final_merged['Data_da_operacao'] = pd.to_datetime(df_final_merged['Data_da_operacao'], errors='coerce')
            if 'DataAberturaConta' in df_final_merged.columns:
                 df_final_merged['DataAberturaConta'] = pd.to_datetime(df_final_merged['DataAberturaConta'], errors='coerce')

            st.write("Passo 5: Processamento final concluído.")

            # Armazenar no estado da sessão
            st.session_state.df_final = df_final_merged
            st.session_state.df_ocorrencias = df_ocorrencias_raw
            st.session_state.df_envolvidos = df_envolvidos_raw
            st.session_state.df_comunicacoes = df_comunicacoes # Pré-processado com Valores
            st.session_state.data_loaded = True
            st.success("Dados processados com sucesso!")
            # st.balloons() # Opcional: Efeito visual de sucesso
            st.rerun()

        except Exception as e:
            st.error(f"Erro fatal durante o processamento inicial: {str(e)}")
            st.code(traceback.format_exc())
            st.session_state.data_loaded = False
            st.stop()

# --- Else if para o caso de botão pressionado mas arquivos faltando ---
elif process_button and (not file_ocorrencias or not file_envolvidos or not file_comunicacoes):
     st.sidebar.error("Faltam arquivos! Carregue os 3 arquivos CSV e clique em 'Processar'.")


# --- Interface Principal (Executa se os dados foram carregados) ---
if st.session_state.data_loaded:

    # Acessar dados do estado da sessão
    # Usar cópias para filtros não afetarem o estado original
    df_final_loaded = st.session_state.df_final.copy()
    df_ocorrencias = st.session_state.df_ocorrencias # Usar original para consulta
    df_envolvidos = st.session_state.df_envolvidos # Usar original para consulta
    df_comunicacoes = st.session_state.df_comunicacoes # Usar pré-processado com valores
    
    df_env = rif_ind.calc_indicadores_envolvido(df_final_loaded)
    df_com = rif_ind.calc_indicadores_comunicacao(df_final_loaded)
    df_par = rif_ind.calc_indicadores_pares(df_final_loaded)

    df_display = df_final_loaded # Começa com todos os dados carregados
    st.caption(f"Trabalhando com {len(df_display)} registros após carregamento.")

    if st.session_state.get('trigger_jump', False):
        st.info(f"Navegue para a aba '🔎 Análise por Comunicação' para ver os detalhes do Indexador '{st.session_state.get('jump_target_indexador', '')}'.")

    # --- Filtros na Sidebar ---
    st.sidebar.header("🔎 Filtros")

    # Filtro de Data
    date_range_selected = None
    if 'Data_da_operacao' in df_display.columns and pd.api.types.is_datetime64_any_dtype(df_display['Data_da_operacao']):
        min_date_val = df_display['Data_da_operacao'].min()
        max_date_val = df_display['Data_da_operacao'].max()
        # Definir padrões seguros se min/max forem NaT
        default_min_date = datetime.now().date().replace(day=1) # Primeiro dia do mês atual
        default_max_date = datetime.now().date()
        min_date = min_date_val.date() if pd.notna(min_date_val) else default_min_date
        max_date = max_date_val.date() if pd.notna(max_date_val) else default_max_date

        try:
            date_range_selected = st.sidebar.date_input(
                "Período da Operação",
                value=[min_date, max_date],
                min_value=min_date if pd.notna(min_date_val) else None, # Permite selecionar antes se min era NaT
                max_value=max_date if pd.notna(max_date_val) else None, # Permite selecionar depois se max era NaT
                key='date_filter'
            )
            if len(date_range_selected) == 2:
                start_date, end_date = date_range_selected
                # Aplicar filtro, tratando NaT na coluna de data
                df_display_filtered = df_display[
                    df_display['Data_da_operacao'].notna() &
                    (df_display['Data_da_operacao'].dt.date >= start_date) &
                    (df_display['Data_da_operacao'].dt.date <= end_date)
                ]
                # Atualizar df_display somente se o filtro mudou algo ou se não estava vazio
                if not df_display_filtered.equals(df_display):
                     if df_display_filtered.empty and not df_display.empty:
                          st.sidebar.warning("Nenhum dado encontrado para o período selecionado.")
                     df_display = df_display_filtered

            else:
                 st.sidebar.warning("Selecione data inicial e final.")
                 date_range_selected = None
        except Exception as e:
             st.sidebar.error(f"Erro no filtro de data: {e}")
             date_range_selected = None


    # Filtros de Ano e Mês
    selected_year = "Todos"
    selected_month = "Todos"
    if 'Ano' in df_display.columns and 'Mes' in df_display.columns:
        # Obter anos únicos dos dados JÁ FILTRADOS por data (df_display)
        available_years = ["Todos"] + sorted(df_display['Ano'].unique().tolist(), reverse=True)
        # Remover 0 se foi usado como NaN filler
        if 0 in available_years: available_years.remove(0)

        selected_year = st.sidebar.selectbox(
            "Filtrar por Ano:",
            options=available_years,
            key='year_filter'
        )

        # Aplicar filtro de ano
        if selected_year != "Todos":
            df_display = df_display[df_display['Ano'] == selected_year]

        # Obter meses únicos DO ANO SELECIONADO (ou todos se ano="Todos")
        available_months = ["Todos"] + sorted(df_display['Mes'].unique().tolist())
         # Remover 0 se foi usado como NaN filler
        if 0 in available_months: available_months.remove(0)

        # Mapear números dos meses para nomes (opcional, mas melhora a UX)
        month_map = {1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
                     7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"}
        month_options_display = ["Todos"] + [month_map.get(m, m) for m in available_months if m != "Todos"]
        # Guardar mapeamento inverso
        month_display_map = {v: k for k, v in month_map.items()}

        selected_month_display = st.sidebar.selectbox(
            "Filtrar por Mês:",
            options=month_options_display,
            key='month_filter'
        )

        # Aplicar filtro de mês
        if selected_month_display != "Todos":
            selected_month_num = month_display_map.get(selected_month_display)
            if selected_month_num: # Verifica se a conversão funcionou
                 df_display = df_display[df_display['Mes'] == selected_month_num]

    # Filtro de Granularidade Temporal
    granularity = 'Mensal'
    if 'Data_da_operacao' in df_display.columns and pd.api.types.is_datetime64_any_dtype(df_display['Data_da_operacao']):
        granularity = st.sidebar.selectbox(
            "Granularidade Temporal (Análise Geral)",
            options=['Diária', 'Semanal', 'Mensal', 'Trimestral'],
            index=2,
            key='granularity_filter'
        )

    # Filtro de Tipo de Ocorrência
    selected_ocorrencia = 'Todas'
    if 'Ocorrencia' in df_display.columns:
        ocorrencias_options = ['Todas'] + sorted(df_display['Ocorrencia'].astype(str).fillna('N/A').unique().tolist())
        selected_ocorrencia = st.sidebar.selectbox(
            "Tipo de Ocorrência",
            options=ocorrencias_options,
            key='ocorrencia_filter'
        )
        if selected_ocorrencia != 'Todas':
             original_len = len(df_display)
             if selected_ocorrencia == 'N/A':
                 df_display = df_display[df_display['Ocorrencia'].isna()]
             else:
                 df_display = df_display[df_display['Ocorrencia'] == selected_ocorrencia]
             if df_display.empty and original_len > 0:
                  st.sidebar.warning("Nenhum dado encontrado para a ocorrência selecionada.")


    st.sidebar.caption(f"Registros após filtros: {len(df_display)}")

    # --- Geração da Lista de Envolvidos ---
    if not df_display.empty:
        envolvidos_filtrados = df_display[['nomeEnvolvido', 'cpfCnpjEnvolvido']].drop_duplicates()
        envolvidos_filtrados = envolvidos_filtrados[envolvidos_filtrados['cpfCnpjEnvolvido'] != 'DESCONHECIDO']
        envolvidos_filtrados = envolvidos_filtrados.sort_values('nomeEnvolvido')
        options_envolvidos = ["Selecione..."] + [f"{row['nomeEnvolvido']} ({row['cpfCnpjEnvolvido']})" for _, row in envolvidos_filtrados.iterrows()]
    else:
        options_envolvidos = ["Selecione..."]

    # --- Criação das Abas ---
    #tab_geral, tab_patterns, tabranking,  tab_individual, tabranking_com, tab_comunicacao, tab_network = st.tabs([
    tab_geral, tabranking,  tab_individual, tabranking_com, tab_comunicacao, tab_network = st.tabs([
        "📊 Análise Geral",
        #"⚠️ Padrões Suspeitos",
        "🏆 Ranking de Envolvidos",
        "👤 Análise Individual Detalhada",
        "💬 Ranking de Comunicações",
        "🔎 Análise por Comunicação",
        "🌐 Análise de Rede Individual",

    ])

    # --- Conteúdo da Aba 1: Análise Geral ---
    with tab_geral:
        st.header("📊 Análise Geral")
        st.caption("Agregações baseadas principalmente no ValorTotal (CampoA). O significado exato varia por segmento.")

        if not df_display.empty:
            # Métricas rápidas
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Comunicações (Filtradas)", df_display['idComunicacao'].nunique())
            col2.metric("Envolvidos Únicos (Filtrados)", df_display['cpfCnpjEnvolvido'].nunique())
            col3.metric("Tipos Ocorrências (Filtradas)", df_display['idOcorrencia'].nunique())

            # Recalcular soma real para a métrica total
            valid_indexadores_geral = df_display['Indexador_x'].unique()
            valor_total_filtrado_real_geral = st.session_state.df_comunicacoes[
                st.session_state.df_comunicacoes['Indexador'].isin(valid_indexadores_geral)
            ]['ValorCampoA'].sum()
            col4.metric("Valor Total (R$) (Soma CampoA)", f"R$ {valor_total_filtrado_real_geral:,.2f}")


            # Quantidade de transações por tipo de ocorrência
            st.subheader("📋 Transações Comunicadas por Tipo de Ocorrência")
            st.info("⚠️ Os valores totais representam a soma dos valores no CampoA do RIF.")
            transactions_by_ocorrencia_agg_base = df_display.groupby(['idOcorrencia', 'Ocorrencia']).agg(
                Quantidade=('Indexador_x', 'nunique'),
            ).reset_index()

            comm_filtered_tab1 = st.session_state.df_comunicacoes[st.session_state.df_comunicacoes['Indexador'].isin(valid_indexadores_geral)]
            ocor_filtered_tab1 = st.session_state.df_ocorrencias[st.session_state.df_ocorrencias['Indexador'].isin(valid_indexadores_geral)][['Indexador', 'idOcorrencia', 'Ocorrencia']].drop_duplicates()

            value_by_indexador_filt_tab1 = comm_filtered_tab1.groupby('Indexador')['ValorCampoA'].sum().reset_index()
            transactions_by_ocorrencia_filt_tab1 = pd.merge(ocor_filtered_tab1, value_by_indexador_filt_tab1, on='Indexador', how='left')

            transactions_by_ocorrencia_agg_val_tab1 = transactions_by_ocorrencia_filt_tab1.groupby(['idOcorrencia', 'Ocorrencia']).agg(
                 ValorTotalReal=('ValorCampoA', 'sum')
            ).reset_index()

            transactions_final_agg = pd.merge(
                transactions_by_ocorrencia_agg_base,
                transactions_by_ocorrencia_agg_val_tab1,
                on=['idOcorrencia', 'Ocorrencia'],
                how='left'
            ).fillna({'ValorTotalReal': 0})

            transactions_final_agg = transactions_final_agg.sort_values('Quantidade', ascending=False)
            transactions_final_agg['ValorTotal_fmt'] = transactions_final_agg['ValorTotalReal'].apply(lambda x: f"R$ {x:,.2f}")

            st.dataframe(transactions_final_agg[['idOcorrencia', 'Ocorrencia', 'Quantidade', 'ValorTotal_fmt']],
                         width='stretch',
                         column_config={
                             "idOcorrencia": "ID Ocorrência", "Ocorrencia": "Ocorrência",
                             "Quantidade": "Qtd. Comunicações", "ValorTotal_fmt": "Valor Total (R$)"
                         },
                         hide_index=True # Ocultar índice numérico padrão
                         )


            #st.subheader("📋 Top 20 Ocorrências por Quantidade (Filtrado)")
            # Selecionar e renomear colunas para a tabela
            #top_ocorrencias_tabela = transactions_final_agg[['idOcorrencia', 'Ocorrencia', 'Quantidade', 'ValorTotal_fmt']].head(20)
            #st.dataframe(
            #    top_ocorrencias_tabela,
            #    width='stretch',
            #    column_config={
            #        "idOcorrencia": "ID Ocorrência",
            #        "Ocorrencia": st.column_config.TextColumn("Ocorrência", width="large"), # Aumentar largura
            #        "Quantidade": "Qtd. Comunicações",
            #        "ValorTotal_fmt": "Valor Total (R$)"
            #     },
            #     hide_index=True # Ocultar índice numérico padrão
            #)


            # Comunicações por Segmento
            st.subheader("📋 Comunicações por Segmento")
            st.info("⚠️ Para cada segmento, os campos de valores (CampoA,...,CampoE) do RIF possuem significados diferentes. Os valores totais desta tabela representam a soma dos valores no CampoA do RIF.")

            if 'comm_filtered_tab1' in locals():
                segment_communications = comm_filtered_tab1.groupby('CodigoSegmento').agg({
                    'idComunicacao': 'nunique',
                    'ValorTotal': 'sum' # ValorTotal é igual a ValorCampoA
                }).reset_index()
                segment_communications = pd.merge(segment_communications, df_segmento_desc, on='CodigoSegmento', how='left')
                segment_communications['DescricaoCampos'].fillna('N/A', inplace=True)

                segment_communications.columns = ['CodigoSegmento', 'Quantidade', 'ValorTotal', 'DescricaoCampos']
                segment_communications = segment_communications.sort_values('Quantidade', ascending=False)
                segment_communications['ValorTotal_fmt'] = segment_communications['ValorTotal'].apply(lambda x: f"R$ {x:,.2f}")
                st.dataframe(segment_communications[['CodigoSegmento', 'Quantidade', 'ValorTotal_fmt', 'DescricaoCampos']], width='stretch', column_config={
                    "CodigoSegmento": st.column_config.TextColumn("Código", width="small"),
                    "Quantidade": st.column_config.NumberColumn("Qtd. Com.", help="Número de Comunicações"),
                    "ValorTotal_fmt": st.column_config.TextColumn("Valor Total (R$)", help="Soma dos Valores (CampoA)"),
                    "DescricaoCampos": st.column_config.TextColumn("Significado Campos", width="large")
                },hide_index=True # Ocultar índice numérico padrão
                )

            # Análise temporal
            st.subheader("📊 Evolução mensal das Comunicações")

            if 'Data_da_operacao' in df_display.columns and pd.api.types.is_datetime64_any_dtype(df_display['Data_da_operacao']):
                df_temp = df_display.copy()
                df_temp = df_temp.dropna(subset=['Data_da_operacao'])
                if granularity == 'Diária':
                    df_temp['Período'] = df_temp['Data_da_operacao'].dt.date
                elif granularity == 'Semanal':
                     if not df_temp.empty:
                         df_temp['Período'] = df_temp['Data_da_operacao'].dt.to_period('W').apply(lambda p: p.strftime('%Y-%U'))
                     else: df_temp['Período'] = None
                elif granularity == 'Mensal':
                    df_temp['Período'] = df_temp['Data_da_operacao'].dt.to_period('M').astype(str)
                elif granularity == 'Trimestral':
                    df_temp['Período'] = df_temp['Data_da_operacao'].dt.to_period('Q').astype(str)

                if 'Período' in df_temp.columns and not df_temp.empty:
                    temporal = df_temp.groupby('Período').size().reset_index(name='Comunicações')
                    temporal = temporal.sort_values('Período')

                    fig = px.line(temporal, x='Período', y='Comunicações', title=f'Evolução {granularity} das Comunicações (Filtrado)',
                                  text='Comunicações')
                    fig.update_traces(textposition='top center')
                    st.plotly_chart(fig, use_container_width=True)
                # else: st.info("Não foi possível gerar análise temporal.") # Removido por redundância
            # else: st.warning("Dados de data insuficientes.")

            # Top 10 Ocorrências
            #st.subheader("🔎 Top 10 Ocorrências Mais Frequentes (Filtrado)")
            #if 'transactions_final_agg' in locals() and not transactions_final_agg.empty:
            #    top_ocorrencias_display = transactions_final_agg.head(10)
            #    fig = px.bar(top_ocorrencias_display, x='Ocorrencia', y='Quantidade', title='Top 10 Ocorrências (Filtrado)',
            #                 labels={'Ocorrencia': 'Ocorrência', 'Quantidade': 'Qtd. Comunicações'},
            #                 hover_data=['idOcorrencia'])
            #    st.plotly_chart(fig, use_container_width=True)

            # Top 50 Envolvidos
            st.subheader("🏆 Top 50 Envolvidos (por Quantidade de Comunicações)")
            top_envolvidos = df_display.groupby(['cpfCnpjEnvolvido', 'nomeEnvolvido']).agg(
                Quantidade=('idComunicacao', 'nunique'),
                ValorTotal=('ValorTotal', 'sum') # Usar ValorTotal (CampoA)
            ).reset_index()
            top_envolvidos.columns = ['CPF/CNPJ', 'Nome', 'Qtd_Comunicacoes', 'Valor_Total_A']
            top_envolvidos = top_envolvidos[top_envolvidos['CPF/CNPJ'] != 'DESCONHECIDO']
            top_envolvidos = top_envolvidos.sort_values('Qtd_Comunicacoes', ascending=False).head(50)
            top_envolvidos['Valor_Total_A_fmt'] = top_envolvidos['Valor_Total_A'].apply(lambda x: f"R$ {x:,.2f}")
            st.dataframe(top_envolvidos[['CPF/CNPJ', 'Nome', 'Qtd_Comunicacoes', 'Valor_Total_A_fmt']], width='stretch',hide_index=True)

            # --- NOVO: Top 510 Titulares/Sócios/Etc. ---
            if 'tipoEnvolvido' in df_display.columns:
                # Aplica a função de normalização (maiusculas, sem acentos)
                df_display['tipoEnvolvido_Norm'] = df_display['tipoEnvolvido'].apply(normalize_string)
            else:
                # Criar coluna vazia se não existir para evitar erros
                df_display['tipoEnvolvido_Norm'] = "DESCONHECIDO"

            st.subheader("🏆 Top 50 Titulares, Sócios, Procuradores e Repres. (por Qtd. Comunicações)")
            if 'tipoEnvolvido_Norm' in df_display.columns:
                # Lista de papéis centrais NORMALIZADOS
                papeis_centrais_norm = ['TITULAR', 'TITULAR DA CONTA', 'SOCIO', 'PROCURADOR', 'REPRESENTANTE', 'RESPONSAVEL', 'ADMINISTRADOR', 'PROCURADOR / REPRESENTANTE LEGAL']
                df_centrais = df_display[df_display['tipoEnvolvido_Norm'].isin(papeis_centrais_norm)]

                if not df_centrais.empty:
                    top_centrais = df_centrais.groupby(['cpfCnpjEnvolvido', 'nomeEnvolvido']).agg(
                        Quantidade=('idComunicacao', 'nunique'),
                        ValorTotalA=('ValorTotal', 'sum') # ValorTotal é CampoA
                    ).reset_index()

                    top_centrais.columns = ['CPF/CNPJ', 'Nome', 'Qtd_Comunicacoes', 'Valor_Total_A']
                    top_centrais = top_centrais[top_centrais['CPF/CNPJ'] != 'DESCONHECIDO']
                    top_centrais = top_centrais.sort_values('Qtd_Comunicacoes', ascending=False).head(50)
                    top_centrais['Valor_Total_A_fmt'] = top_centrais['Valor_Total_A'].apply(lambda x: f"R$ {x:,.2f}")
                    st.dataframe(top_centrais[['CPF/CNPJ', 'Nome', 'Qtd_Comunicacoes', 'Valor_Total_A_fmt']], width='stretch', hide_index=True)
                else:
                    st.info("Nenhum envolvido com papéis centrais (Titular, Sócio, etc.) encontrado nos dados filtrados.")
            else:
                st.info("Coluna 'tipoEnvolvido' ausente.")


            # --- MODIFICADO: Top 50 Remetentes (por Valor Campo A) ---
            st.subheader("📤 Top 50 Remetentes (por Valor Total Campo A)")
            st.caption("Baseado em envolvidos com papel 'remetente' e somando ValorTotal (CampoA).")
            # Verificar 'ValorTotal' (CampoA) em vez de 'ValorCampoB'
            if 'tipoEnvolvido_Norm' in df_display.columns and 'ValorTotal' in df_display.columns:
                # Usar coluna normalizada
                df_remetentes = df_display[df_display['tipoEnvolvido_Norm'] == 'REMETENTE']

                if not df_remetentes.empty:
                    top_remetentes = df_remetentes.groupby(['cpfCnpjEnvolvido', 'nomeEnvolvido']).agg(
                        ValorTotalA=('ValorTotal', 'sum'), # Somar ValorTotal (CampoA)
                        Quantidade=('idComunicacao', 'nunique')
                    ).reset_index()

                    top_remetentes.columns = ['CPF/CNPJ', 'Nome', 'Valor_Total_A', 'Qtd_Comunicacoes']
                    top_remetentes = top_remetentes[top_remetentes['CPF/CNPJ'] != 'DESCONHECIDO']
                    top_remetentes = top_remetentes[top_remetentes['Valor_Total_A'] > 0]
                    top_remetentes = top_remetentes.sort_values('Valor_Total_A', ascending=False).head(50)
                    top_remetentes['Valor_Total_A_fmt'] = top_remetentes['Valor_Total_A'].apply(lambda x: f"R$ {x:,.2f}")
                    # Exibir colunas corretas
                    st.dataframe(top_remetentes[['CPF/CNPJ', 'Nome', 'Valor_Total_A_fmt', 'Qtd_Comunicacoes']], width='stretch', hide_index=True)
                else:
                    st.info("Nenhum envolvido com papel 'remetente' encontrado nos dados filtrados.")
            else:
                st.info("Colunas 'tipoEnvolvido' ou 'ValorTotal' ausentes para esta análise.")
            # --- FIM MODIFICAÇÃO ---

            # --- MODIFICADO: Top 50 Beneficiários (por Valor Campo A) ---
            st.subheader("📥 Top 50 Beneficiários (por Valor Total Campo A)")
            st.caption("Baseado em envolvidos com papel 'beneficiário' e somando ValorTotal (CampoA).")
            # Verificar 'ValorTotal' (CampoA) em vez de 'ValorCampoC'
            if 'tipoEnvolvido_Norm' in df_display.columns and 'ValorTotal' in df_display.columns:
                # Usar coluna normalizada (já cobre 'beneficiário', 'beneficiario', etc.)
                df_benef = df_display[df_display['tipoEnvolvido_Norm'] == 'BENEFICIARIO']

                if not df_benef.empty:
                    top_benef = df_benef.groupby(['cpfCnpjEnvolvido', 'nomeEnvolvido']).agg(
                        ValorTotalA=('ValorTotal', 'sum'), # Somar ValorTotal (CampoA)
                        Quantidade=('idComunicacao', 'nunique')
                    ).reset_index()

                    top_benef.columns = ['CPF/CNPJ', 'Nome', 'Valor_Total_A', 'Qtd_Comunicacoes']
                    top_benef = top_benef[top_benef['CPF/CNPJ'] != 'DESCONHECIDO']
                    top_benef = top_benef[top_benef['Valor_Total_A'] > 0]
                    top_benef = top_benef.sort_values('Valor_Total_A', ascending=False).head(50)
                    top_benef['Valor_Total_A_fmt'] = top_benef['Valor_Total_A'].apply(lambda x: f"R$ {x:,.2f}")
                    # Exibir colunas corretas
                    st.dataframe(top_benef[['CPF/CNPJ', 'Nome', 'Valor_Total_A_fmt', 'Qtd_Comunicacoes']], width='stretch', hide_index=True)
                else:
                    st.info("Nenhum envolvido com papel 'beneficiário' encontrado nos dados filtrados.")
            else:
                st.info("Colunas 'tipoEnvolvido' ou 'ValorTotal' ausentes para esta análise.")
            # --- FIM MODIFICAÇÃO ---

            # Comunicações por Cidade da Agência
            st.subheader("🏙️ Comunicações por Cidade da Agência (Filtrado)")
            if 'comm_filtered_tab1' in locals() and 'CidadeAgencia' in comm_filtered_tab1.columns:
                 # Usar .copy() para evitar SettingWithCopyWarning
                 comm_filtered_city = comm_filtered_tab1.dropna(subset=['CidadeAgencia', 'UFAgencia']).copy()

                 if not comm_filtered_city.empty:
                     # --- CORREÇÃO: Normalizar Nomes de Cidades ---
                     comm_filtered_city['Cidade_Norm'] = comm_filtered_city['CidadeAgencia'].apply(normalize_string)
                     # Também normalizar UF para consistência
                     comm_filtered_city['UF_Norm'] = comm_filtered_city['UFAgencia'].apply(normalize_string)

                     # Agrupar por Indexador e CIDADE/UF NORMALIZADA
                     comm_city_val = comm_filtered_city.groupby(['Indexador', 'Cidade_Norm', 'UF_Norm'])['ValorCampoA'].sum().reset_index()

                     # Agrupar novamente pela CIDADE/UF NORMALIZADA para a tabela final
                     city_communications = comm_city_val.groupby(['Cidade_Norm', 'UF_Norm']).agg(
                         ValorTotal=('ValorCampoA', 'sum'),
                         Quantidade=('Indexador', 'nunique')
                     ).reset_index()
                     # --- FIM CORREÇÃO ---

                     city_communications.columns = ['Cidade', 'UF', 'Valor Total', 'Quantidade'] # Renomear Cidade_Norm -> Cidade
                     city_communications = city_communications.sort_values('Valor Total', ascending=False)
                     city_communications['Valor Total (R$)'] = city_communications['Valor Total'].apply(lambda x: f"R$ {x:,.2f}")
                     st.dataframe(city_communications[['Cidade', 'UF', 'Valor Total (R$)', 'Quantidade']].head(20), width='stretch',hide_index=True)
                 else:
                     st.info("Nenhuma comunicação com info de cidade nos dados filtrados.")
            else:
                st.info("Coluna 'CidadeAgencia' ausente ou sem dados.")

            # --- MODIFICADO: Top 10 Depositantes em ESPÉCIE ---
            st.subheader("💰 Top 10 Depositantes (em Espécie)")
            st.caption("Baseado em envolvidos com papel 'depositante' em comunicações com idOcorrencia '1161'.")
            if 'tipoEnvolvido' in df_display.columns and 'idOcorrencia' in df_display.columns:
                deposito_especie_ids = ['1161'] # ID para depósito em espécie (conforme Padrões Suspeitos)

                # Filtrar df_display por tipo "depositante" E pelo ID de ocorrência de depósito em espécie
                depositantes_especie = df_display[
                    (df_display['tipoEnvolvido'].str.lower() == 'depositante') &
                    (df_display['idOcorrencia'].isin(deposito_especie_ids))
                ]

                if not depositantes_especie.empty:
                    # Agrupar por CPF/Nome e somar o ValorTotal (CampoA)
                    depositantes_agg = depositantes_especie.groupby(['cpfCnpjEnvolvido', 'nomeEnvolvido']).agg(
                         ValorTotal=('ValorTotal', 'sum') # ValorTotal é baseado no CampoA
                    ).reset_index()

                    depositantes_agg.columns = ['CPF/CNPJ', 'Nome', 'Valor Total']
                    depositantes_agg = depositantes_agg[depositantes_agg['CPF/CNPJ'] != 'DESCONHECIDO']
                    depositantes_agg = depositantes_agg.sort_values('Valor Total', ascending=False).head(10)
                    depositantes_agg['Valor Total (R$)'] = depositantes_agg['Valor Total'].apply(lambda x: f"R$ {x:,.2f}")

                    st.dataframe(depositantes_agg[['CPF/CNPJ', 'Nome', 'Valor Total (R$)']], width='stretch', hide_index=True)
                else:
                    st.info("Nenhum depositante em espécie (Ocorrência 1161) encontrado nos dados filtrados.")
            else:
                st.info("Colunas 'tipoEnvolvido' ou 'idOcorrencia' ausentes para esta análise.")
            # --- FIM MODIFICAÇÃO ---


            # --- MODIFICADO: Top 10 Sacadores em ESPÉCIE ---
            st.subheader("💸 Top 10 Sacadores (em Espécie)")
            st.caption("Baseado em envolvidos com papel 'sacador' em comunicações com idOcorrencia '891', '894', '1163' ou '1159'.")
            if 'tipoEnvolvido' in df_display.columns and 'idOcorrencia' in df_display.columns:
                saque_especie_ids = ['891', '894', '1163', '1159'] # IDs para saque em espécie (conforme Padrões Suspeitos)

                # Filtrar df_display por tipo "sacador" E pelos IDs de ocorrência de saque em espécie
                sacadores_especie = df_display[
                    (df_display['tipoEnvolvido'].str.lower() == 'sacador') &
                    (df_display['idOcorrencia'].isin(saque_especie_ids))
                ]

                if not sacadores_especie.empty:
                    # Agrupar por CPF/Nome e somar o ValorTotal (CampoA)
                    sacadores_agg = sacadores_especie.groupby(['cpfCnpjEnvolvido', 'nomeEnvolvido']).agg(
                         ValorTotal=('ValorTotal', 'sum') # ValorTotal é baseado no CampoA
                    ).reset_index()

                    sacadores_agg.columns = ['CPF/CNPJ', 'Nome', 'Valor Total']
                    sacadores_agg = sacadores_agg[sacadores_agg['CPF/CNPJ'] != 'DESCONHECIDO']
                    sacadores_agg = sacadores_agg.sort_values('Valor Total', ascending=False).head(10)
                    sacadores_agg['Valor Total (R$)'] = sacadores_agg['Valor Total'].apply(lambda x: f"R$ {x:,.2f}")

                    st.dataframe(sacadores_agg[['CPF/CNPJ', 'Nome', 'Valor Total (R$)']], width='stretch', hide_index=True)
                else:
                    st.info("Nenhum sacador em espécie (Ocorrências 891, 894, 1163, 1159) encontrado nos dados filtrados.")
            else:
                st.info("Colunas 'tipoEnvolvido' ou 'idOcorrencia' ausentes para esta análise.")
            # --- FIM MODIFICAÇÃO ---
            
            st.subheader("Lei de Benford – Valores das Transações (CampoA)")
            fig_benford = analise_benford(df_display)  # dfdisplay = dffinal filtrado
            if fig_benford is not None:
                st.plotly_chart(fig_benford, use_container_width=True)
            else:
                st.caption("Não há valores positivos suficientes em 'ValorTotal' para aplicar Benford.")

            # Análises de PEPs, Pessoas Obrigadas, Servidores
            if 'bitPepCitado' in df_display.columns:
                st.subheader("👤 PEPs Identificados e Comunicações Associadas")
                st.info("⚠️ Use o Identificador para localizar a comunicação na aba Análise por Comunicação.")
                # Filtrar o dataframe filtrado (df_display) para encontrar linhas onde bitPepCitado é True
                peps_identificados_df = df_display[df_display['bitPepCitado'] == True].copy() # Use .copy()

                if not peps_identificados_df.empty:
                    # Selecionar colunas relevantes para a tabela
                    cols_to_show_pep = [
                        'Indexador_x', 'idComunicacao', 'Data_da_operacao',
                        'cpfCnpjEnvolvido', 'nomeEnvolvido', 'tipoEnvolvido', # Papel do PEP na comunicação
                        'ValorTotal', # Valor principal (CampoA)
                        'Ocorrencia', # Ocorrência associada
                        'DescricaoCampos' # Contexto dos valores (se disponível)
                    ]
                    # Garantir que as colunas existem no dataframe
                    cols_exist_pep = [col for col in cols_to_show_pep if col in peps_identificados_df.columns]

                    # Opcional: Ordenar para agrupar por PEP ou por data
                    peps_identificados_df = peps_identificados_df.sort_values(by=['nomeEnvolvido', 'Data_da_operacao'], ascending=[True, False])

                    # Exibir a tabela
                    st.dataframe(
                        peps_identificados_df[cols_exist_pep],
                        width='stretch',
                        column_config={
                            "Indexador_x": "Indexador",
                            "idComunicacao": "ID Com.",
                            "Data_da_operacao": st.column_config.DatetimeColumn("Data Operação", format="DD/MM/YYYY"),
                            "cpfCnpjEnvolvido": "CPF/CNPJ PEP",
                            "nomeEnvolvido": "Nome PEP",
                            "tipoEnvolvido": "Papel na Com.",
                            "ValorTotal": st.column_config.NumberColumn("Valor Principal (CampoA)", format="R$ %.2f"),
                            "Ocorrencia": st.column_config.TextColumn("Ocorrência", width="medium"),
                            "DescricaoCampos": st.column_config.TextColumn("Contexto Valor", width="medium", help="Significado dos Campos A-E para o Segmento")
                        },
                        hide_index=True # Ocultar índice numérico padrão
                    )
                else:
                    st.info("Nenhum PEP identificado nos dados filtrados.")

            if 'bitPessoaObrigadaCitado' in df_display.columns:
                st.subheader("👥 Análise de Pessoas Obrigadas (Filtrado)")
                obrigada_counts = df_display.drop_duplicates(subset=['cpfCnpjEnvolvido'])['bitPessoaObrigadaCitado'].value_counts().reset_index()
                obrigada_counts.columns = ['PessoaObrigada', 'Contagem']
                fig = px.pie(obrigada_counts, names=['Sim' if x else 'Não' for x in obrigada_counts['PessoaObrigada']],
                             values='Contagem', title='Distribuição de Envolvidos Únicos por Pessoa Obrigada (Filtrado)')
                st.plotly_chart(fig, use_container_width=True)

            if 'intServidorCitado' in df_display.columns:
                st.subheader("🧑‍💼 Análise de Servidores Públicos (Filtrado)")
                servidor_counts = df_display.drop_duplicates(subset=['cpfCnpjEnvolvido'])['intServidorCitado'].value_counts().reset_index()
                servidor_counts.columns = ['Servidor', 'Contagem']
                fig = px.pie(servidor_counts, names=['Sim' if x else 'Não' for x in servidor_counts['Servidor']],
                             values='Contagem', title='Distribuição de Envolvidos Únicos por Servidor Público (Filtrado)')
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nenhum dado corresponde aos filtros selecionados para a Análise Geral.")
    
#''' NOTA: A ABA DE PADRÕES SUSPEITOS FOI INTEGRADA AO RANKING DE ENVOLVIDOS PARA SIMPLIFICAR
##        MANTEMOS O CÓDIGO AQUI APENAS PARA REFERÊNCIAS FUTURAS
#        
#    # --- Conteúdo da Aba 2: Padrões Suspeitos ---
#    with tab_patterns:
#        st.header("⚠️ Padrões Suspeitos (Baseado nos Dados Filtrados)")
#
#        if not df_display.empty:
#            with st.spinner("Analisando padrões suspeitos e calculando scores..."):
#                suspicious_df_filtered = analyze_suspicious_patterns(
#                    df_display,
#                    st.session_state.df_ocorrencias,
#                    st.session_state.df_comunicacoes,
#                    st.session_state.df_envolvidos
#                )
#
#            if suspicious_df_filtered is not None and not suspicious_df_filtered.empty:
#                # --- NOVO: Placar de Risco (Scoring) ---
#                st.subheader("🔥 Ranking de Risco dos Envolvidos")
#
#                # Definir pesos para os riscos
#                risk_weights = {'Crítico': 10, 'Alto': 5, 'Moderado': 2, 'Baixo': 1}
#
#                # Calcular score
#                score_df = suspicious_df_filtered.copy()
#                score_df['Pontos'] = score_df['Risco'].map(risk_weights).fillna(1)
#
#                # Agrupar por CPF/CNPJ e Nome
#                ranking = score_df.groupby(['cpfCnpj', 'Nome']).agg(
#                    Score_Total=('Pontos', 'sum'),
#                    Qtd_Alertas=('Motivo', 'count'),
#                    Tipos_Risco=('Risco', lambda x: list(x.unique()))
#                ).reset_index()
#
#                # Filtrar 'N/A' e ordenar
#                ranking = ranking[~ranking['cpfCnpj'].str.contains('N/A', na=False)]
#                ranking = ranking.sort_values('Score_Total', ascending=False).head(20) # Top 20
#
#                # Exibir Tabela de Ranking
#                st.dataframe(
#                    ranking,
#                    width='stretch',
#                    hide_index=True,
#                    column_config={
#                        "cpfCnpj": "CPF/CNPJ",
#                        "Score_Total": st.column_config.ProgressColumn("Score de Risco", format="%d", min_value=0, max_value=int(ranking['Score_Total'].max() * 1.2)),
#                        "Qtd_Alertas": "Qtd. Alertas",
#                        "Tipos_Risco": "Níveis Detectados"
#                    }
#                )
#                st.divider()
#                # --- FIM NOVO ---
#
#                st.subheader("Detalhe dos Padrões Identificados")
#
#                # Correção para Arrow (string conversion)
#                suspicious_df_display = suspicious_df_filtered.copy()
#                if 'Indexador' in suspicious_df_display.columns:
#                    suspicious_df_display['Indexador'] = suspicious_df_display['Indexador'].astype(str)
#                if 'idComunicacao' in suspicious_df_display.columns:
#                    suspicious_df_display['idComunicacao'] = suspicious_df_display['idComunicacao'].astype(str)
#
#                st.dataframe(
#                    suspicious_df_display,
#                    width='stretch',
#                    column_config={
#                        "Indexador": st.column_config.TextColumn("Indexador", width="medium"),
#                        "idComunicacao": st.column_config.TextColumn("ID Com.", width="medium"),
#                        "cpfCnpj": st.column_config.TextColumn("CPF/CNPJ", width="medium"),
#                        "Nome": st.column_config.TextColumn("Nome", width="large"),
#                        "Motivo": st.column_config.TextColumn("Motivo", width="large"),
#                        "Risco": st.column_config.TextColumn("Risco", width="small")
#                    },hide_index=True
#                )
#
#                # Gráfico de distribuição de riscos
#                risk_counts = suspicious_df_filtered['Risco'].value_counts().reset_index()
#                risk_counts.columns = ['Risco', 'Contagem']
#                fig = px.bar(risk_counts, x='Risco', y='Contagem', title="Distribuição dos Níveis de Risco",
#                             color='Risco', color_discrete_map={'Alto': '#FF6B6B', 'Crítico': '#D00000', 'Moderado': '#FFB703'},
#                             category_orders={"Risco": ["Moderado", "Alto", "Crítico"]}
#                            )
#                st.plotly_chart(fig, use_container_width=True)
#            else:
#                st.info("Nenhum padrão suspeito detectado nos dados que correspondem aos filtros selecionados.")
#        else:
#            st.info("Nenhum dado para analisar padrões (verifique filtros).")
#'''
    
    # --- Conteúdo da Aba 3: Análise de Rede Individual ---
    with tab_network:
        st.header("🌐 Análise de Rede Individual")
        st.info("Selecione um envolvido abaixo para visualizar sua rede de conexões diretas (baseado nos dados filtrados).")

        selected_option_net = st.selectbox(
            "Selecione um Envolvido para Análise de Rede:",
            options=options_envolvidos,
            key='select_network'
        )

        selected_cpf_network = None
        if selected_option_net != "Selecione...":
            try: selected_cpf_network = selected_option_net.split('(')[-1].strip(')')
            except IndexError: selected_cpf_network = None

        if selected_cpf_network:
            st.subheader(f"Rede de Conexões para: {selected_option_net}")
            if not df_display.empty:
                with st.spinner(f"Construindo rede completa para {selected_cpf_network}..."):
                    # Chamar a função original que retorna G, partição e contagem de arestas
                    G_sub_completo, partition_completa_dict, edge_count_completo = analyze_individual_network(df_display, selected_cpf_network)

                if G_sub_completo is not None and G_sub_completo.number_of_nodes() > 0:

                    # --- LÓGICA DE ESCOLHA E EXIBIÇÃO ---
                    st.divider() # Separador visual

                    # Definir opção padrão com base na contagem de arestas
                    default_view_index = 1 if edge_count_completo > MAX_CONEXOES_REDE else 0 # 0: Completo, 1: Simplificado
                    view_choice = st.radio(
                        "Selecione o tipo de visualização:",
                        ("Completo", "Simplificado (Nó central + Vizinhos diretos)"),
                        index=default_view_index,
                        key=f"view_choice_{selected_cpf_network}",
                        horizontal=True
                    )
                    if edge_count_completo > MAX_CONEXOES_REDE:
                         st.warning(f"A rede completa possui {edge_count_completo} conexões, o que pode tornar a visualização lenta. A visualização simplificada foi pré-selecionada.")

                    # Definir qual grafo e partição usar
                    G_to_visualize = None
                    partition_to_visualize = {}
                    displaying_simplified = False

                    if view_choice == "Simplificado":
                        displaying_simplified = True
                        with st.spinner("Gerando grafo simplificado..."):
                            G_to_visualize = simplify_graph(G_sub_completo, selected_cpf_network)
                            # Recalcular partição para o grafo simplificado (opcional, pode ser rápido o suficiente)
                            if G_to_visualize.number_of_nodes() > 0:
                                try:
                                    undirected_simple = G_to_visualize.to_undirected()
                                    if undirected_simple.number_of_edges() > 0:
                                        partition_to_visualize = community_louvain.best_partition(undirected_simple)
                                    else:
                                         partition_to_visualize = {node: i for i, node in enumerate(undirected_simple.nodes())}
                                except Exception as e:
                                     st.warning(f"Não foi possível calcular comunidades para grafo simplificado: {e}")
                                     partition_to_visualize = {node: 0 for node in G_to_visualize.nodes()}
                    else: # Escolheu Completo
                        G_to_visualize = G_sub_completo
                        partition_to_visualize = partition_completa_dict # Usar a partição já calculada

                    # Exibir Métricas (baseadas no grafo que será visualizado)
                    st.subheader("Métricas da Rede Exibida")
                    col1_net, col2_net, col3_net = st.columns(3)
                    node_count_display = G_to_visualize.number_of_nodes() if G_to_visualize else 0
                    edge_count_display = G_to_visualize.number_of_edges() if G_to_visualize else 0
                    community_count_display = len(set(partition_to_visualize.values())) if partition_to_visualize else 0

                    col1_net.metric("Nós na Rede Exibida", node_count_display)
                    col2_net.metric("Conexões Exibidas", edge_count_display)
                    col3_net.metric("Comunidades (Rede Exibida)", community_count_display)


                    # Visualização do grafo selecionado (G_to_visualize)
                    if G_to_visualize is not None and G_to_visualize.number_of_nodes() > 0:
                        graph_type_msg = "simplificada" if displaying_simplified else "completa"
                        with st.spinner(f"Renderizando visualização {graph_type_msg}..."):
                            network_file_sub = visualize_network(G_to_visualize, partition_to_visualize, selected_cpf_network)

                        if network_file_sub:
                            st.components.v1.html(open(network_file_sub, 'r', encoding='utf-8').read(), height=800)
                            st.html(generate_network_legend())

                        else:
                            st.warning(f"Não foi possível gerar a visualização da rede {graph_type_msg}.")
                    else:
                         st.info("O grafo selecionado está vazio.")

                else:
                    st.info("Nenhuma conexão encontrada para este envolvido nos dados filtrados.")
            else:
                 st.info("Não há dados filtrados para construir a rede.")
        else:
            st.info("Selecione um envolvido acima.")

    # --- Conteúdo da Aba 4: Análise Individual Detalhada ---
    with tab_individual:
        st.header("👤 Análise Individual Detalhada")

        selected_option_ind = st.selectbox(
            "Selecione um Envolvido para Detalhes:",
            options=options_envolvidos,
            key='select_individual'
        )

        selected_cpf_individual = None
        if selected_option_ind != "Selecione...":
            try: selected_cpf_individual = selected_option_ind.split('(')[-1].strip(')')
            except IndexError: selected_cpf_individual = None


        if selected_cpf_individual:
            envolvido_data = df_display[df_display['cpfCnpjEnvolvido'] == selected_cpf_individual].copy()

            if not envolvido_data.empty:
                nome = envolvido_data['nomeEnvolvido'].iloc[0] if not envolvido_data['nomeEnvolvido'].empty else "Nome Desconhecido"
                st.subheader(f"Análise de {nome} ({selected_cpf_individual})")

                # Métricas individuais
                col1_ind, col2_ind, col3_ind, col4_ind, col5_ind = st.columns(5)
                col1_ind.metric("Total Comunicações (Filtradas)", envolvido_data['idComunicacao'].nunique())

                valid_indexadores_ind = envolvido_data['Indexador_x'].unique()
                valor_total_ind_real = st.session_state.df_comunicacoes[
                     st.session_state.df_comunicacoes['Indexador'].isin(valid_indexadores_ind)
                 ]['ValorCampoA'].sum()
                col2_ind.metric("Valor Total (R$) (Soma CampoA)", f"R$ {valor_total_ind_real:,.2f}")

                pep_flag = envolvido_data['bitPepCitado'].any()
                obr_flag = envolvido_data['bitPessoaObrigadaCitado'].any()
                ser_flag = envolvido_data['intServidorCitado'].any()
                col3_ind.metric("PEP", "Sim" if pep_flag else "Não")
                col4_ind.metric("Pessoa Obrigada", "Sim" if obr_flag else "Não")
                col5_ind.metric("Servidor Público", "Sim" if ser_flag else "Não")

                # Comunicações
                st.subheader("📋 Comunicações e Ocorrências (Filtradas)")
                cols_to_show_base = ['Indexador_x','idComunicacao', 'Data_da_operacao', 'Ocorrencia',
                                'CidadeAgencia', 'NumeroAgencia', 'tipoEnvolvido',
                                'CodigoSegmento', 'DescricaoCampos']
                # Mostrar colunas de valor apenas se existirem E tiverem soma > 0
                cols_to_show_vals = [f'Valor{c}' for c in ['A','B','C','D','E']
                                     if f'Valor{c}' in envolvido_data.columns and envolvido_data[f'Valor{c}'].sum() > 0]
                cols_to_show_info = ['informacoesAdicionais']

                cols_exist = [col for col in cols_to_show_base + cols_to_show_vals + cols_to_show_info if col in envolvido_data.columns]

                column_config_ind = {
                     "idComunicacao": st.column_config.TextColumn("ID Com.", width="small"),
                     "Data_da_operacao": st.column_config.DatetimeColumn("Data Operação", format="DD/MM/YYYY HH:mm"),
                     "Ocorrencia": st.column_config.TextColumn("Ocorrência", width="medium"),
                     "CidadeAgencia": "Cidade",
                     "NumeroAgencia": "Agência",
                     "tipoEnvolvido": "Papel",
                     "CodigoSegmento": "Seg.",
                     "DescricaoCampos": st.column_config.TextColumn("Descrição Campos", width="medium", help="Significado dos Campos A-E para este Segmento"),
                     "ValorCampoA": st.column_config.NumberColumn("Campo A", format="R$ %.2f"),
                     "ValorCampoB": st.column_config.NumberColumn("Campo B", format="R$ %.2f"),
                     "ValorCampoC": st.column_config.NumberColumn("Campo C", format="R$ %.2f"),
                     "ValorCampoD": st.column_config.NumberColumn("Campo D", format="R$ %.2f"),
                     "ValorCampoE": st.column_config.NumberColumn("Campo E", format="R$ %.2f"),
                     "informacoesAdicionais": st.column_config.TextColumn("Info Adicional", width="large")
                }
                column_config_ind_filtered = {k: v for k, v in column_config_ind.items() if k in cols_exist}

                st.dataframe(envolvido_data[cols_exist], width='stretch', column_config=column_config_ind_filtered,hide_index=True)

                # Análise temporal individual
                if 'Data_da_operacao' in envolvido_data.columns and pd.api.types.is_datetime64_any_dtype(envolvido_data['Data_da_operacao']):
                    envolvido_data_clean = envolvido_data.dropna(subset=['Data_da_operacao'])
                    if not envolvido_data_clean.empty:
                        temporal_ind = envolvido_data_clean.groupby(envolvido_data_clean['Data_da_operacao'].dt.date).size().reset_index(name='Comunicações')
                        fig_ind = px.line(temporal_ind, x='Data_da_operacao', y='Comunicações', title='Comunicações ao Longo do Tempo (Individual)')
                        st.plotly_chart(fig_ind, use_container_width=True)

                # Padrões suspeitos específicos
                st.subheader("⚠️ Padrões Suspeitos Identificados (Filtrados)")
                # Tentar buscar do cache ou recalcular
                try:
                    suspicious_df_all = analyze_suspicious_patterns(
                             st.session_state.df_final, # Analisa todos os dados cacheados
                             st.session_state.df_ocorrencias,
                             st.session_state.df_comunicacoes,
                             st.session_state.df_envolvidos
                         )
                    suspicious_envolvido = suspicious_df_all[suspicious_df_all['cpfCnpj'] == selected_cpf_individual]
                    if not suspicious_envolvido.empty:
                        st.dataframe(suspicious_envolvido, width='stretch')
                    else:
                        st.info("Nenhum padrão suspeito detectado para este envolvido.")
                except Exception as e:
                    st.warning(f"Falha ao obter/calcular padrões suspeitos: {e}")

                # --- Gráfico de relacionamentos ---
                st.divider()
                st.subheader("Relacionamento com Contrapartes (Força dos Vínculos)")

                # Usa o df_final filtrado atual (df_display) como base
                if not df_display.empty and selected_cpf_individual:
                    fig_rel = plot_relacionamentos_envolvido(df_display, selected_cpf_individual)
                    if fig_rel is not None:
                        st.plotly_chart(fig_rel, use_container_width=True)
                    else:
                        st.caption("Não foi possível identificar contrapartes suficientes para este envolvido nos dados filtrados.")
                else:
                    st.caption("Dados insuficientes para calcular vínculos para o envolvido selecionado.")



                # --- NOVO: Navegação para Análise por Comunicação ---
                #st.divider()
                #st.subheader("Navegar para Detalhes da Comunicação")

                # Obter lista única de Indexadores exibidos nesta tabela individual
                
                #indexadores_na_tabela = envolvido_data["Indexador_x"].astype(str).unique().tolist()
                #if indexadores_na_tabela:
                #    selected_indexador_jump = st.selectbox(
                #        "Selecione um Indexador desta tabela para ver detalhes",
                #        options=["Selecione..."] + indexadores_na_tabela,
                #        key=f"jump_select_{selected_cpf_individual}",
                #    )

                #    if st.button("Ver Detalhes da Comunicação Selecionada", key=f"jump_button_{selected_cpf_individual}"):
                #        if selected_indexador_jump != "Selecione...":
                #            st.markdown("---")
                #            st.subheader(f"Detalhamento completo da comunicação (Indexador {selected_indexador_jump})")
                #            render_analise_comunicacao(str(selected_indexador_jump))
                #        else:
                #            st.warning("Por favor, selecione um Indexador da lista.")
                #else:
                #    st.info("Nenhuma comunicação específica para selecionar nesta visualização.")

            else:
                st.warning("Nenhum dado encontrado para este envolvido com os filtros atuais.")
        else:
            st.info("Selecione um envolvido acima para ver os detalhes.")

    # --- Conteúdo da Aba 5: Análise por Comunicação ---
    with tab_comunicacao:
        st.header("🔎 Análise por Comunicação (Indexador)")

        # Verificar se os dataframes base existem
        if 'df_comunicacoes' not in st.session_state or st.session_state.df_comunicacoes is None or \
           'df_envolvidos' not in st.session_state or st.session_state.df_envolvidos is None or \
           'df_ocorrencias' not in st.session_state or st.session_state.df_ocorrencias is None:
            st.warning("DataFrames base não estão carregados no estado da sessão.")
        else:
            # Pegar lista de Indexadores únicos do df_comunicacoes original para garantir que todos estejam disponíveis
            lista_indexadores = ["Selecione..."] + sorted(st.session_state.df_comunicacoes['Indexador'].unique().tolist())

            default_index = 0 # Padrão é "Selecione..."
            jump_indexador = st.session_state.get('jump_target_indexador', None)
            if jump_indexador and jump_indexador in lista_indexadores:
                try:
                    default_index = lista_indexadores.index(jump_indexador)
                except ValueError:
                    default_index = 0 # Mantém padrão se não encontrar por algum motivo

            selected_indexador = st.selectbox(
                "Selecione o Indexador da Comunicação:",
                options=lista_indexadores,
                index=default_index, # Usa o índice calculado
                key='select_indexador'
            )

            if jump_indexador:
                st.session_state.jump_target_indexador = None
                st.session_state.trigger_jump = False

            if selected_indexador != "Selecione...":
                st.subheader(f"Detalhes da Comunicação Indexador: {selected_indexador}")

                # Filtrar dados para o Indexador selecionado
                comunicacao_detalhe = st.session_state.df_comunicacoes[st.session_state.df_comunicacoes['Indexador'] == selected_indexador]
                envolvidos_detalhe = st.session_state.df_envolvidos[st.session_state.df_envolvidos['Indexador'].astype(str).str.strip() == str(selected_indexador).strip()]
                ocorrencias_detalhe = st.session_state.df_ocorrencias[st.session_state.df_ocorrencias['Indexador'] == selected_indexador]

                if not comunicacao_detalhe.empty:
                    comunicacao_info = comunicacao_detalhe.iloc[0] # Pega a primeira (e única) linha

                    # Exibir Informações Gerais da Comunicação
                    col1_comm, col2_comm, col3_comm = st.columns(3)
                    with col1_comm:
                        st.metric("ID Comunicação", comunicacao_info.get('idComunicacao', 'N/A'))
                        st.metric("Data Operação", comunicacao_info.get('Data_da_operacao', pd.NaT).strftime('%d/%m/%Y') if pd.notna(comunicacao_info.get('Data_da_operacao')) else 'N/A')
                    with col2_comm:
                        st.metric("Comunicante", comunicacao_info.get('nomeComunicante', 'N/A'))
                        st.metric("Cidade/UF Agência", f"{comunicacao_info.get('CidadeAgencia', 'N/A')} / {comunicacao_info.get('UFAgencia', 'N/A')}")
                    with col3_comm:
                        st.metric("Segmento", comunicacao_info.get('CodigoSegmento', 'N/A'))
                        # Buscar descrição do segmento
                        desc_campos = df_segmento_desc[df_segmento_desc['CodigoSegmento'] == str(comunicacao_info.get('CodigoSegmento', ''))]
                        if not desc_campos.empty:
                            #st.caption(f"Descrição Campos: {desc_campos['DescricaoCampos'].iloc[0]}")
                            st.info(f"Descrição Campos do Segmento: {desc_campos['DescricaoCampos'].iloc[0]}")
                        else:
                            st.caption("Descrição Campos: Segmento não mapeado")

                    st.divider()

                    # --- NOVO: Exibir Titular(es) da Comunicação (com DESTAQUE) ---
                    st.subheader("👤 Titular(es) da Comunicação")
                    if not envolvidos_detalhe.empty:
                        # Filtrar pelos papéis de titular
                        titulares_df = envolvidos_detalhe[
                            envolvidos_detalhe['tipoEnvolvido'].str.lower().isin(['titular', 'titular da conta'])
                        ]

                        if not titulares_df.empty:
                            # Exibir cada titular encontrado
                            for _, titular_row in titulares_df.iterrows():
                                nome_titular = titular_row.get('nomeEnvolvido', 'N/A')
                                cpf_titular = titular_row.get('cpfCnpjEnvolvido', 'N/A')

                                # Formatar tags de PEP e Servidor com estilo
                                pep_info = ""
                                servidor_info = ""
                                if str(titular_row.get('bitPepCitado', 'Não')).lower() == 'sim':
                                    # Estilo para a tag PEP (fundo vermelho, texto branco)
                                    pep_info = ' <span style="background-color: #FF6B6B; color: #FFF; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; font-weight: bold;">PEP</span>'
                                if str(titular_row.get('intServidorCitado', 'Não')).lower() == 'sim':
                                    # Estilo para a tag Servidor (fundo amarelo, texto escuro)
                                    servidor_info = ' <span style="background-color: #FFD700; color: #333; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; font-weight: bold;">SERVIDOR</span>'

                                # --- MODIFICADO: Bloco HTML para destaque ---
                                # Usamos um <div> com estilo para criar a caixa.
                                # Ajuste as cores (background-color, border, color) para o seu tema.
                                # Estas cores são otimizadas para o tema escuro das suas screenshots.
                                st.markdown(f"""
                                <div style="background-color: #222226; border: 1px solid #4C4E54; border-radius: 7px; padding: 12px; margin-bottom: 10px;">
                                    <div style="font-size: 1.25em; font-weight: bold; color: #FAFAFA; margin-bottom: 5px;">
                                        {nome_titular} {pep_info} {servidor_info}
                                    </div>
                                    <div style="font-size: 1.1em; color: #ADADAD; font-family: monospace;">
                                        {cpf_titular}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                                # --- FIM MODIFICAÇÃO ---
                        else:
                            st.info("Nenhum envolvido com papel 'Titular' ou 'Titular da Conta' encontrado para este Indexador.")
                    else:
                        st.info("Nenhum envolvido encontrado para este Indexador.")
                    # --- FIM NOVO ---

                    st.divider()

                    # Exibir Valores (Campos A-E) em destaque
                    st.subheader("Valores Reportados")
                    val_cols = st.columns(5)
                    campos = ['A', 'B', 'C', 'D', 'E']
                    for i, campo in enumerate(campos):
                        valor_col_name = f'ValorCampo{campo}'
                        if valor_col_name in comunicacao_info and pd.notna(comunicacao_info[valor_col_name]):
                            with val_cols[i]:
                                st.metric(f"Valor Campo {campo}", f"R$ {comunicacao_info[valor_col_name]:,.2f}")
                        else:
                             with val_cols[i]:
                                st.metric(f"Valor Campo {campo}", "R$ 0,00") # Ou N/A

                    st.divider()

                    # Exibir Informações Adicionais
                    st.subheader("Informações Adicionais")
                    st.info("⚠️ IMPORTANTE. Nunca usar LLM abertas para analisar esses dados.")

                    info_adicional = comunicacao_info.get('informacoesAdicionais', 'Nenhuma informação adicional disponível.')
                    if pd.isna(info_adicional) or info_adicional.strip() == '':
                         info_adicional = 'Nenhuma informação adicional disponível.'
                    # Usar text_area para textos longos, definir altura
                    st.markdown(f"""
                    <div style="height: 300px; overflow-y: auto; border: 1px solid #e0e0e0; padding: 10px; border-radius: 5px; background-color: #f9f9f9; color: #333;">
                        {info_adicional.replace('<','&lt;').replace('>','&gt;')}
                    </div>
                    """, unsafe_allow_html=True)
                    # st.code(info_adicional, language=None) # language=None evita highlight # Mostra o conteúdo em uma única linha permitindo cópia.
                    # st.text_area("Detalhes:", value=info_adicional, height=300, disabled=True, key=f"info_{selected_indexador}") # Mostra o conteúdo bloqueado.

                    # --- NOVO: Nuvem de Palavras e Keywords ---
                    st.divider()
                    st.subheader("Nuvem de Palavras e Termos Financeiros Frequentes")
                    with st.spinner("Gerando nuvem de palavras e analisando termos..."):
                         wordcloud_img, df_fin_keywords, context_map = generate_word_cloud_and_keywords(info_adicional)

                    if wordcloud_img:
                        st.image(wordcloud_img, caption="Nuvem das palavras mais frequentes (após remoção de stopwords)")
                    else:
                        st.caption("Não foi possível gerar a nuvem de palavras.")

                    if df_fin_keywords is not None and not df_fin_keywords.empty:
                        st.markdown("##### Top Termos Financeiros:")
                        st.dataframe(df_fin_keywords, hide_index=True, width=400) # Tabela menor

                        st.markdown("##### Contexto dos Termos:")
                        if context_map:
                            for keyword, snippets in context_map.items():
                                with st.expander(f"Contexto para '{keyword}' ({len(snippets)} trechos)"):
                                    for i, snippet in enumerate(snippets):
                                        #st.markdown(f"_{i+1}_: ...{snippet}...") # Usar markdown para itálico
                                        st.text_area(
                                        label=f"Trecho {i+1}", # Rótulo para a caixa de texto
                                        value=snippet,
                                        height=100, # Ajuste a altura conforme necessário
                                        key=f"context_{selected_indexador}_{keyword}_{i}" # Chave única
                                        )
                                        if i < len(snippets) - 1: st.markdown("---") # Divisor
                        else:
                            st.caption("Não foi possível encontrar contexto para os termos financeiros.")
                    elif wordcloud_img: # Se a nuvem foi gerada mas keywords não
                         st.caption("Nenhum termo financeiro relevante encontrado entre as palavras mais frequentes.")
                    # --- FIM NOVO ---

                    st.divider()

                    # Exibir Ocorrências Vinculadas
                    st.subheader("Ocorrências Vinculadas")
                    if not ocorrencias_detalhe.empty:
                        st.dataframe(ocorrencias_detalhe[['idOcorrencia', 'Ocorrencia']], width='stretch', hide_index=True)
                    else:
                        st.info("Nenhuma ocorrência vinculada encontrada para este Indexador.")

                    st.divider()

                    # Exibir Envolvidos Vinculados
                    st.subheader("Envolvidos Vinculados")
                    if not envolvidos_detalhe.empty:
                        # Selecionar e formatar colunas para exibição
                        cols_envolvidos = ['cpfCnpjEnvolvido', 'nomeEnvolvido', 'tipoEnvolvido',
                                           'bitPepCitado', 'bitPessoaObrigadaCitado', 'intServidorCitado',
                                           'agenciaEnvolvido', 'contaEnvolvido']
                        cols_envolvidos_exist = [c for c in cols_envolvidos if c in envolvidos_detalhe.columns]

                        # Criar cópia para formatação
                        envolvidos_display = envolvidos_detalhe[cols_envolvidos_exist].copy()

                        # Formatar booleanos
                        for flag in ['bitPepCitado', 'bitPessoaObrigadaCitado', 'intServidorCitado']:
                             if flag in envolvidos_display.columns:
                                 envolvidos_display[flag] = envolvidos_display[flag].apply(lambda x: "Sim" if str(x).lower()=='sim' or x==True else "Não")

                        st.dataframe(envolvidos_display, width='stretch', hide_index=True,
                                     column_config={
                                         "cpfCnpjEnvolvido": "CPF/CNPJ",
                                         "nomeEnvolvido": "Nome",
                                         "tipoEnvolvido": "Papel",
                                         "bitPepCitado": "PEP",
                                         "bitPessoaObrigadaCitado": "P. Obrigada",
                                         "intServidorCitado": "Servidor P.",
                                         "agenciaEnvolvido": "Agência Env.",
                                         "contaEnvolvido": "Conta Env."
                                     })
                    else:
                        st.info("Nenhum envolvido vinculado encontrado para este Indexador.")


                    # --- NOVO: Visualização do Grafo da Comunicação ---
                    st.divider()
                    st.subheader("Visualização dos Vínculos na Comunicação")
                    if not envolvidos_detalhe.empty:
                        with st.spinner("Gerando grafo da comunicação..."):
                            G_comm, titulares_comm = create_communication_graph(envolvidos_detalhe)

                        if G_comm.number_of_nodes() > 0:

                            # Visualizar o grafo
                            with st.spinner("Renderizando visualização do grafo..."):
                                comm_graph_file = visualize_communication_graph(G_comm, titulares_comm)

                            if comm_graph_file:
                                st.components.v1.html(open(comm_graph_file, 'r', encoding='utf-8').read(), height=550)
                                st.html(generate_network_legend())
                            else:
                                st.warning("Não foi possível renderizar o grafo da comunicação.")
                        else:
                            st.info("Não há envolvidos suficientes ou válidos para gerar um grafo para esta comunicação.")
                    else:
                        st.info("Não há envolvidos vinculados para gerar o grafo.")


                    # --- MODIFICADO: Tabelas e Gráficos de Fluxo Baseados em Informações Adicionais ---
                    st.divider()
                    st.subheader("Resumo do Fluxo (Extraído de Informações Adicionais)")
                    st.info("⚠️ IMPORTANTE. É possível que esses dados estejam incompletos. Os valores aqui informados não substituem a análise mais detida do conteúdo do campo Informações Adicionais.")

                    if pd.notna(info_adicional) and info_adicional != 'Nenhuma informação adicional disponível.':
                        with st.spinner("Analisando texto de informações adicionais..."):
                            # Chamar a nova função que retorna 3 DataFrames
                            df_creditos_ext, df_debitos_ext, df_cartao_ext = extract_all_financial_data(info_adicional)

                            # --- NOVO: Diagrama de Sankey ---
                            st.markdown("##### 🌊 Diagrama de Fluxo (Sankey)")

                            # Determinar o nome do titular para o centro do gráfico
                            nome_titular_sankey = "Titular/Conta"
                            # Tentar pegar o nome do titular identificado anteriormente na aba
                            if not envolvidos_detalhe.empty:
                                 tits = envolvidos_detalhe[envolvidos_detalhe['tipoEnvolvido'].str.lower().isin(['titular', 'titular da conta'])]
                                 if not tits.empty:
                                     nome_titular_sankey = tits.iloc[0]['nomeEnvolvido']

                            if not df_creditos_ext.empty or not df_debitos_ext.empty:
                                fig_sankey = plot_sankey_fluxo(df_creditos_ext, df_debitos_ext, nome_titular_sankey)
                                if fig_sankey:
                                    st.plotly_chart(fig_sankey, use_container_width=True)
                                else:
                                    st.caption("Dados insuficientes para gerar o diagrama de fluxo.")
                            # --- FIM NOVO ---
                        # --- FIM MODIFICAÇÃO ---

                        st.markdown("##### Principais Origens de Crédito")
                        if not df_creditos_ext.empty:
                            # Ordenar por valor para exibição
                            df_creditos_ext = df_creditos_ext.sort_values('Valor (R$)', ascending=False)
                            st.dataframe(df_creditos_ext, width='stretch', hide_index=True,
                                         column_config={
                                            "Valor (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                                            "Percentual (%)": st.column_config.NumberColumn(format="%.2f%%")
                                            # Remover 'Detalhe' se não estiver mais presente
                                         })
                            fig_cred = px.bar(df_creditos_ext.head(10), y='Origem do Crédito', x='Valor (R$)',
                                              orientation='h', title='Top 10 Origens de Crédito',
                                              labels={'Origem do Crédito': 'Origem', 'Valor (R$)': 'Valor Recebido (R$)'},
                                              text='Valor (R$)', height=400)
                            fig_cred.update_traces(texttemplate='R$ %{x:,.2f}', textposition='outside')
                            fig_cred.update_layout(yaxis={'categoryorder':'total ascending'})
                            st.plotly_chart(fig_cred, use_container_width=True)
                        # else: st.caption("Não foi possível extrair origens de crédito.") # Já tratado na função

                        st.markdown("##### Principais Destinos de Débito")
                        if not df_debitos_ext.empty:
                            # Ordenar por valor para exibição
                            df_debitos_ext = df_debitos_ext.sort_values('Valor (R$)', ascending=False)
                            st.dataframe(df_debitos_ext, width='stretch', hide_index=True,
                                         column_config={
                                            "Valor (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                                            "Percentual (%)": st.column_config.NumberColumn(format="%.2f%%")
                                            # Remover 'Detalhe' se não estiver mais presente
                                         })
                            fig_deb = px.bar(df_debitos_ext.head(10), y='Destino do Débito', x='Valor (R$)',
                                             orientation='h', title='Top 10 Destinos de Débito',
                                             labels={'Destino do Débito': 'Destino', 'Valor (R$)': 'Valor Enviado (R$)'},
                                             text='Valor (R$)', height=400)
                            fig_deb.update_traces(texttemplate='R$ %{x:,.2f}', textposition='outside')
                            fig_deb.update_layout(yaxis={'categoryorder':'total ascending'})
                            st.plotly_chart(fig_deb, use_container_width=True)
                        # else: st.caption("Não foi possível extrair destinos de débito.") # Já tratado na função

                        st.markdown("##### Principais Gastos no Cartão")
                        if not df_cartao_ext.empty:
                             # Ordenar por valor para exibição
                             df_cartao_ext = df_cartao_ext.sort_values('Valor (R$)', ascending=False)
                             st.dataframe(df_cartao_ext, width='stretch', hide_index=True,
                                         column_config={
                                            "Valor (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                                            "Percentual (%)": st.column_config.NumberColumn(format="%.2f%%")
                                         })
                             fig_card = px.bar(df_cartao_ext.head(10), y='Estabelecimento', x='Valor (R$)',
                                               orientation='h', title='Top 10 Gastos no Cartão de Crédito',
                                               labels={'Estabelecimento': 'Estabelecimento', 'Valor (R$)': 'Valor Gasto (R$)'},
                                               text='Valor (R$)', height=400)
                             fig_card.update_traces(texttemplate='R$ %{x:,.2f}', textposition='outside')
                             fig_card.update_layout(yaxis={'categoryorder':'total ascending'})
                             st.plotly_chart(fig_card, use_container_width=True)
                        # else: st.caption("Não foi possível extrair gastos no cartão.") # Já tratado na função

                    else:
                        st.info("Campo 'Informações Adicionais' vazio ou indisponível para gerar gráficos de fluxo.")
                    # --- FIM MODIFICAÇÃO Bloco Gráficos ---

                else:
                    st.warning(f"Nenhum detalhe de comunicação encontrado para o Indexador {selected_indexador}.")
            else:
                 st.info("Selecione um Indexador na lista acima para ver os detalhes.")

    # --- Conteúdo da Aba 6: Ranking de Envolvidos (INTERATIVO) ---
    with tabranking:
        st.header("🏆 Ranking de Risco Consolidado")
        st.caption("O Score Total soma pontos de indicadores matemáticos e padrões suspeitos detectados.")
        # --- SEÇÃO DE AJUDA SOLICITADA ---
        with st.expander("❓ Como é calculado o score de risco"):
            st.markdown("""
            O **Score Total** é uma pontuação integrada que combina a análise comportamental (padrões qualitativos) com métricas estatísticas (indicadores quantitativos).
            
            ### 1. Padrões Comportamentais (Qualitativos)
            Estes alertas são extraídos diretamente das narrativas e ocorrências reportadas, classificados por gravidade:
            * **Crítico (10 pts):** Fracionamento de valores, PEP com múltiplas comunicações, Alto valor em espécie ou Keywords de alto risco (ex: 'Laranja', 'Doleiro').
            * **Alto (5 pts):** Burla de limites (Structuring), Transações de altíssimo valor (> R$ 1Mi), Saques/Depósitos vultosos em espécie ou Alta Frequência.
            * **Moderado (2 pts):** Contas recém-abertas (< 30 dias), Movimentação em múltiplas cidades no mesmo dia ou Resistência a informações.
            
            ### 2. Indicadores Matemáticos (Quantitativos)
            Métricas calculadas sobre o histórico consolidado do envolvido:
            * **HHI (Concentração):** O Índice de Herfindahl-Hirschman mede se o dinheiro está concentrado em poucas contrapartes (Risco de contas-âncora).
            * **Fracionamento Temporal:** Identifica dias com 3 ou mais operações, sugerindo tentativa de divisão de valores para evitar reporte.
            * **Proximidade de Limites:** Monitora operações que ficam propositalmente entre 90% e 99% do limite de R$ 50 mil.
            
            ### 3. Regra de Cálculo do Score
            A pontuação final é a soma de:
            1.  **Pontos Qualitativos:** Soma de todos os alertas detectados pela análise de padrões.
            2.  **Bônus de Perfil:** +5 pontos se for PEP, +5 se Servidor Público e +5 se Pessoa Obrigada.
            3.  **Bônus de Concentração:** +10 pontos se o índice HHI for superior a 0.6.
            4.  **Bônus de Fracionamento:** +2 pontos para cada dia identificado com alta frequência de operações simultâneas.
            """)
        # --- FIM DA SEÇÃO DE AJUDA ---

        if "df_final" in st.session_state:
            with st.spinner("Consolidando Score de Risco..."):
                # A. Indicadores Matemáticos
                df_env_math = rif_ind.calc_indicadores_envolvido(st.session_state.df_final)
                
                # B. Alertas Qualitativos (Função do script principal)
                df_alertas_brutos = analyze_suspicious_patterns(
                    df_display, st.session_state.df_ocorrencias,
                    st.session_state.df_comunicacoes, st.session_state.df_envolvidos
                )

                # C. Cruzamento de Dados
                if not df_alertas_brutos.empty:
                    df_resumo_alertas = df_alertas_brutos.groupby('cpfCnpj').agg(
                        Score_Quali=('Pontos', 'sum'),
                        Qtd_Alertas=('Motivo', 'count')
                    ).reset_index()
                    df_ranking = pd.merge(df_env_math, df_resumo_alertas, left_on='cpfCnpjEnvolvido', right_on='cpfCnpj', how='left').fillna(0)
                else:
                    df_ranking = df_env_math.assign(Score_Quali=0, Qtd_Alertas=0)

                # D. Aplicação das Regras de Score
                df_ranking['ScoreTotal'] = df_ranking['Score_Quali']
                df_ranking['ScoreTotal'] += df_ranking['flag_pep'].astype(int) * 5
                df_ranking['ScoreTotal'] += df_ranking['flag_servidor'].astype(int) * 5
                df_ranking['ScoreTotal'] += (df_ranking['hhi_contrapartes'] > 0.6).astype(int) * 10
                df_ranking['ScoreTotal'] += df_ranking['fracionamento_dias_com_3+_ops'] * 2

                df_ranking = df_ranking.sort_values('ScoreTotal', ascending=False).reset_index(drop=True)
                df_ranking.insert(0, "Pos.", range(1, len(df_ranking) + 1))

                # E. Tabela de Ranking Interativa (Formatada BRL)
                st.subheader("Classificação de Risco")
                st.caption("Clique em uma linha para ver os padrões detalhados do envolvido abaixo.")
                
                # Selecionamos as colunas
                df_to_show = df_ranking[["Pos.", "cpfCnpjEnvolvido", "nomeEnvolvido", "n_comunicacoes", "ScoreTotal", "valor_total"]].head(100)

                # Aplicamos a formatação brasileira via Styler do Pandas
                df_styled = df_to_show.style.format({
                    "valor_total": lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                })

                sel_rank = st.dataframe(
                    df_styled,
                    use_container_width=True, 
                    hide_index=True,
                    on_select="rerun", 
                    selection_mode="single-row", 
                    key="rank_table_select",
                    column_config={
                        "n_comunicacoes": "Qtd. Com.",
                        "ScoreTotal": st.column_config.ProgressColumn(
                            "Score", 
                            format="%d pts", 
                            min_value=0, 
                            max_value=int(df_ranking['ScoreTotal'].max())
                        ),
                        "valor_total": st.column_config.NumberColumn("Valor Total") 
                    }
                )

                # F. Gráfico
                fig_risk = px.scatter(df_ranking.head(30), x='valor_total', y='ScoreTotal', size='ScoreTotal', color='ScoreTotal',
                                     hover_name='nomeEnvolvido', title="Dispersão: Valor vs Score")
                st.plotly_chart(fig_risk, use_container_width=True)

                # G. DETALHAMENTO AO SELECIONAR (Tabela solicitada)
                selection = sel_rank.get("selection", {}).get("rows", [])
                if selection:
                    row_idx = selection[0]
                    sel_cpf = df_ranking.iloc[row_idx]["cpfCnpjEnvolvido"]
                    sel_nome = df_ranking.iloc[row_idx]["nomeEnvolvido"]

                    st.markdown("---")
                    st.subheader(f"🔍 Padrões Identificados: {sel_nome}")
                    
                    detalhes_alvo = df_alertas_brutos[df_alertas_brutos['cpfCnpj'] == sel_cpf].copy()
                    if not detalhes_alvo.empty:
                        st.dataframe(
                            detalhes_alvo[['Indexador', 'idComunicacao', 'Motivo', 'Risco']],
                            use_container_width=True, hide_index=True,
                            column_config={"Motivo": st.column_config.TextColumn("Descrição do Alerta", width="large")}
                        )
                    else:
                        st.info("Este alvo possui score baseado apenas em indicadores matemáticos (HHI, PEP ou Volume).")


    # --- Conteúdo da Aba 7: Ranking de Comunicações ---
    with tabranking_com:
        st.header("Ranking de Comunicações")
        st.caption(
            "Ranking de comunicações (Indexador_x) baseado em valor total, quantidade de envolvidos, "
            "uso de espécie e presença de PEP/servidores/pessoas obrigadas."
        )

        if "df_final" not in st.session_state or st.session_state.df_final is None or st.session_state.df_final.empty:
            st.info("Nenhum dado disponível para calcular o ranking de comunicações. Verifique o upload e os filtros.")
        else:
            with st.spinner("Calculando indicadores por comunicação..."):
                df_com = rif_ind.calc_indicadores_comunicacao(st.session_state.df_final)

            if df_com is None or df_com.empty:
                st.info("Não foi possível calcular indicadores de comunicação para os dados atuais.")
            else:
                st.subheader("Parâmetros do Ranking")

                criterio_map_com = {
                    "Valor total (R$)": "valor_total",
                    "Quantidade de envolvidos": "n_envolvidos",
                    "% valor em espécie CampoA": "pct_valor_especie_A",
                    "% valor em espécie CampoB": "pct_valor_especie_B",
                }

                criterio_escolhido_com = st.selectbox(
                    "Ordenar por:",
                    options=list(criterio_map_com.keys()),
                    index=0,
                    key="ranking_com_criterio",
                )

                col_ordenacao_com = criterio_map_com[criterio_escolhido_com]
                df_rank_com = df_com.copy()

                if col_ordenacao_com not in df_rank_com.columns:
                    st.warning(
                        f"O critério selecionado ('{col_ordenacao_com}') não está disponível nos indicadores calculados."
                    )
                    st.stop()

                df_rank_com = df_rank_com.sort_values(col_ordenacao_com, ascending=False).reset_index(drop=True)

                top_n_com = st.slider(
                    "Quantidade de comunicações a exibir",
                    min_value=10,
                    max_value=200,
                    value=50,
                    step=10,
                    key="ranking_com_topn",
                )

                df_rank_com_top = df_rank_com.head(top_n_com).copy()
                df_rank_com_top.insert(0, "Posição", range(1, len(df_rank_com_top) + 1))
                
                df_env_base = st.session_state.df_envolvidos.copy()
                df_env_base["Indexador"] = df_env_base["Indexador"].astype(str)

                # Filtrar titulares
                mask_titular = df_env_base["tipoEnvolvido"].str.lower().isin(["titular", "titular da conta"])
                df_titulares = df_env_base[mask_titular].copy()

                if not df_titulares.empty:
                    # Nome(s) do(s) titular(es) por Indexador (se houver mais de um, junta com '; ')
                    titulares_por_idx = (
                        df_titulares.groupby("Indexador")["nomeEnvolvido"]
                        .agg(lambda x: "; ".join(sorted(set(x))))
                        .reset_index()
                        .rename(columns={"nomeEnvolvido": "Titular"})
                    )
                else:
                    titulares_por_idx = pd.DataFrame(columns=["Indexador", "Titular"])

              
                
                # Métricas-resumo rápidas                
                col1c, col2c, col3c, col4c = st.columns(4)
                col1c.metric("Total de Comunicações no Ranking", int(df_rank_com.shape[0]))
                col2c.metric(
                    "Maior valor total (R$)",
                    f"R$ {df_rank_com['valor_total'].max():,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    if "valor_total" in df_rank_com.columns and not df_rank_com["valor_total"].isna().all()
                    else "N/D",
                )
                col3c.metric(
                    "Máx. nº de envolvidos em uma comunicação",
                    int(df_rank_com["n_envolvidos"].max())
                    if "n_envolvidos" in df_rank_com.columns
                    else 0,
                )
                col4c.metric(
                    "Máx. % espécie CampoA",
                    f"{df_rank_com['pct_valor_especie_A'].max():.1f}%"
                    if "pct_valor_especie_A" in df_rank_com.columns
                    else "0,0%",
                )

                st.subheader("Tabela de Ranking de Comunicações")
                
                # df_rank_com_top tem Indexador_x, titulares_por_idx tem Indexador
                df_rank_com_top = df_rank_com_top.merge(
                    titulares_por_idx,
                    left_on="Indexador_x",
                    right_on="Indexador",
                    how="left",
                )

                df_rank_com_top["Titular"] = df_rank_com_top["Titular"].fillna("N/D")


                # Colunas principais
                cols_basicas_com = [
                    "Posição",
                    "Indexador_x",
                    "Titular",
                    "n_envolvidos",
                    "valor_total",
                    "pct_valor_especie_A",
                    "pct_valor_especie_B",
                    "flag_pep_na_com",
                    "flag_servidor_na_com",
                    "flag_pessoa_obrigada_na_com",
                ]

                cols_exist_com = [c for c in cols_basicas_com if c in df_rank_com_top.columns]
                df_show_com = df_rank_com_top[cols_exist_com].copy()

                # Formatação visual (sem alterar o Indexador_x)
                if "valor_total" in df_show_com.columns:
                    df_show_com["valor_total_fmt"] = df_show_com["valor_total"].apply(
                        lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    )
                if "pct_valor_especie_A" in df_show_com.columns:
                    df_show_com["pct_valor_especie_A_fmt"] = df_show_com["pct_valor_especie_A"].apply(
                        lambda x: f"{x:.1f}%"
                    )
                if "pct_valor_especie_B" in df_show_com.columns:
                    df_show_com["pct_valor_especie_B_fmt"] = df_show_com["pct_valor_especie_B"].apply(
                        lambda x: f"{x:.1f}%"
                    )

                cols_view_com = ["Posição", "Indexador_x"]
    
                if "Titular" in df_show_com.columns:
                    cols_view_com.append("Titular")
                if "n_envolvidos" in df_show_com.columns:
                    cols_view_com.append("n_envolvidos")
                if "valor_total_fmt" in df_show_com.columns:
                    cols_view_com.append("valor_total_fmt")
                elif "valor_total" in df_show_com.columns:
                    cols_view_com.append("valor_total")

                if "pct_valor_especie_A_fmt" in df_show_com.columns:
                    cols_view_com.append("pct_valor_especie_A_fmt")
                if "pct_valor_especie_B_fmt" in df_show_com.columns:
                    cols_view_com.append("pct_valor_especie_B_fmt")

                for flag_col in [
                    "flag_pep_na_com",
                    "flag_servidor_na_com",
                    "flag_pessoa_obrigada_na_com",
                ]:
                    if flag_col in df_show_com.columns:
                        cols_view_com.append(flag_col)

                df_show_com = df_show_com[cols_view_com]

                # Data editor com seleção de linha
                column_config_com = {
                    "Posição": st.column_config.NumberColumn("Posição", format="%d"),
                    "Indexador_x": st.column_config.TextColumn("Indexador"),
                    "Titular": st.column_config.TextColumn(
                        "Titular(es)",
                        help="Nome(s) do(s) titular(es) da comunicação, quando identificado(s)",
                    ),
                    "n_envolvidos": st.column_config.NumberColumn(
                        "Qtd. Envolvidos",
                        help="Número de envolvidos distintos na comunicação",
                    ),
                    "valor_total_fmt": st.column_config.TextColumn(
                        "Valor Total (CampoA)",
                        help="Soma do valor principal (CampoA) na comunicação",
                    ),
                    "pct_valor_especie_A_fmt": st.column_config.TextColumn(
                        "% espécie CampoA",
                        help="Percentual do valor total em segmentos de espécie (CampoA)",
                    ),
                    "pct_valor_especie_B_fmt": st.column_config.TextColumn(
                        "% espécie CampoB",
                        help="Percentual do valor total em segmentos de espécie (CampoB)",
                    ),
                    "flag_pep_na_com": st.column_config.CheckboxColumn(
                        "PEP na comunicação",
                        help="Comunicação envolve ao menos um PEP",
                    ),
                    "flag_servidor_na_com": st.column_config.CheckboxColumn(
                        "Servidor na comunicação",
                        help="Comunicação envolve ao menos um servidor público",
                    ),
                    "flag_pessoa_obrigada_na_com": st.column_config.CheckboxColumn(
                        "Pessoa Obrigada na comunicação",
                        help="Comunicação envolve ao menos uma pessoa obrigada",
                    ),
                }

                edited = st.dataframe(
                    df_show_com,
                    use_container_width=True,
                    hide_index=True,
                    column_config={k: v for k, v in column_config_com.items() if k in df_show_com.columns},
                    key="ranking_com_table",
                    height=400,
                    selection_mode="single-row",
                    on_select="rerun",  # opcional, força rerun ao selecionar linha
                )


                # Recuperar seleção
                selection = st.session_state["ranking_com_table"].get("selection", {})
                selected_rows = selection.get("rows", [])

                selected_indexador = None
                if selected_rows:
                    row_idx = selected_rows[0]
                    if 0 <= row_idx < len(df_show_com):
                        selected_indexador = df_show_com.iloc[row_idx]["Indexador_x"]

                if selected_indexador:
                    st.markdown("---")
                    st.subheader(f"Detalhamento completo da comunicação (Indexador {selected_indexador})")

                    # Reutiliza o mecanismo já usado na Análise Individual Detalhada
                    st.session_state.jumptargetindexador = str(selected_indexador)
                    st.session_state.triggerjump = True

                    # Chama a mesma lógica da aba "Análise por Comunicação"
                    # (copie o bloco central da tabcomunicacao para dentro de uma função
                    #  e invoque aqui, ou reproduza sucintamente os trechos principais)
                    listaindexadores = ["Selecione..."] + sorted(
                        st.session_state.df_comunicacoes["Indexador"].astype(str).unique().tolist()
                    )

                    # Força o selectedindexador a ser o nosso escolhido
                    # e executa o mesmo conteúdo que você já tem em tabcomunicacao.
                    comunicacao_detalhe = st.session_state.df_comunicacoes[
                        st.session_state.df_comunicacoes["Indexador"].astype(str) == str(selected_indexador)
                    ]
                    envolvidos_detalhe = st.session_state.df_envolvidos[
                        st.session_state.df_envolvidos["Indexador"].astype(str).str.strip()
                        == str(selected_indexador).strip()
                    ]
                    ocorrencias_detalhe = st.session_state.df_ocorrencias[
                        st.session_state.df_ocorrencias["Indexador"].astype(str) == str(selected_indexador)
                    ]

                    if not comunicacao_detalhe.empty:
                        comunicacao_info = comunicacao_detalhe.iloc[0]

                        # Exibir Informações Gerais da Comunicação
                        col1_comm, col2_comm, col3_comm = st.columns(3)
                        with col1_comm:
                            st.metric("ID Comunicação", comunicacao_info.get('idComunicacao', 'N/A'))
                            st.metric("Data Operação", comunicacao_info.get('Data_da_operacao', pd.NaT).strftime('%d/%m/%Y') if pd.notna(comunicacao_info.get('Data_da_operacao')) else 'N/A')
                        with col2_comm:
                            st.metric("Comunicante", comunicacao_info.get('nomeComunicante', 'N/A'))
                            st.metric("Cidade/UF Agência", f"{comunicacao_info.get('CidadeAgencia', 'N/A')} / {comunicacao_info.get('UFAgencia', 'N/A')}")
                        with col3_comm:
                            st.metric("Segmento", comunicacao_info.get('CodigoSegmento', 'N/A'))
                            # Buscar descrição do segmento
                            desc_campos = df_segmento_desc[df_segmento_desc['CodigoSegmento'] == str(comunicacao_info.get('CodigoSegmento', ''))]
                            if not desc_campos.empty:
                                #st.caption(f"Descrição Campos: {desc_campos['DescricaoCampos'].iloc[0]}")
                                st.info(f"Descrição Campos do Segmento: {desc_campos['DescricaoCampos'].iloc[0]}")
                            else:
                                st.caption("Descrição Campos: Segmento não mapeado")

                        st.divider()

                        # --- NOVO: Exibir Titular(es) da Comunicação (com DESTAQUE) ---
                        st.subheader("👤 Titular(es) da Comunicação")
                        if not envolvidos_detalhe.empty:
                            # Filtrar pelos papéis de titular
                            titulares_df = envolvidos_detalhe[
                                envolvidos_detalhe['tipoEnvolvido'].str.lower().isin(['titular', 'titular da conta'])
                            ]

                            if not titulares_df.empty:
                                # Exibir cada titular encontrado
                                for _, titular_row in titulares_df.iterrows():
                                    nome_titular = titular_row.get('nomeEnvolvido', 'N/A')
                                    cpf_titular = titular_row.get('cpfCnpjEnvolvido', 'N/A')

                                    # Formatar tags de PEP e Servidor com estilo
                                    pep_info = ""
                                    servidor_info = ""
                                    if str(titular_row.get('bitPepCitado', 'Não')).lower() == 'sim':
                                        # Estilo para a tag PEP (fundo vermelho, texto branco)
                                        pep_info = ' <span style="background-color: #FF6B6B; color: #FFF; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; font-weight: bold;">PEP</span>'
                                    if str(titular_row.get('intServidorCitado', 'Não')).lower() == 'sim':
                                        # Estilo para a tag Servidor (fundo amarelo, texto escuro)
                                        servidor_info = ' <span style="background-color: #FFD700; color: #333; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; font-weight: bold;">SERVIDOR</span>'

                                    # --- MODIFICADO: Bloco HTML para destaque ---
                                    # Usamos um <div> com estilo para criar a caixa.
                                    # Ajuste as cores (background-color, border, color) para o seu tema.
                                    # Estas cores são otimizadas para o tema escuro das suas screenshots.
                                    st.markdown(f"""
                                    <div style="background-color: #222226; border: 1px solid #4C4E54; border-radius: 7px; padding: 12px; margin-bottom: 10px;">
                                        <div style="font-size: 1.25em; font-weight: bold; color: #FAFAFA; margin-bottom: 5px;">
                                            {nome_titular} {pep_info} {servidor_info}
                                        </div>
                                        <div style="font-size: 1.1em; color: #ADADAD; font-family: monospace;">
                                            {cpf_titular}
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    # --- FIM MODIFICAÇÃO ---
                            else:
                                st.info("Nenhum envolvido com papel 'Titular' ou 'Titular da Conta' encontrado para este Indexador.")
                        else:
                            st.info("Nenhum envolvido encontrado para este Indexador.")
                        # --- FIM NOVO ---

                        st.divider()

                        # Exibir Valores (Campos A-E) em destaque
                        st.subheader("Valores Reportados")
                        val_cols = st.columns(5)
                        campos = ['A', 'B', 'C', 'D', 'E']
                        for i, campo in enumerate(campos):
                            valor_col_name = f'ValorCampo{campo}'
                            if valor_col_name in comunicacao_info and pd.notna(comunicacao_info[valor_col_name]):
                                with val_cols[i]:
                                    st.metric(f"Valor Campo {campo}", f"R$ {comunicacao_info[valor_col_name]:,.2f}")
                            else:
                                 with val_cols[i]:
                                    st.metric(f"Valor Campo {campo}", "R$ 0,00") # Ou N/A

                        st.divider()

                        # Exibir Informações Adicionais
                        st.subheader("Informações Adicionais")
                        st.info("⚠️ IMPORTANTE. Nunca usar LLM abertas para analisar esses dados.")

                        info_adicional = comunicacao_info.get('informacoesAdicionais', 'Nenhuma informação adicional disponível.')
                        if pd.isna(info_adicional) or info_adicional.strip() == '':
                             info_adicional = 'Nenhuma informação adicional disponível.'
                        # Usar text_area para textos longos, definir altura
                        st.markdown(f"""
                        <div style="height: 300px; overflow-y: auto; border: 1px solid #e0e0e0; padding: 10px; border-radius: 5px; background-color: #f9f9f9; color: #333;">
                            {info_adicional.replace('<','&lt;').replace('>','&gt;')}
                        </div>
                        """, unsafe_allow_html=True)
                        # st.code(info_adicional, language=None) # language=None evita highlight # Mostra o conteúdo em uma única linha permitindo cópia.
                        # st.text_area("Detalhes:", value=info_adicional, height=300, disabled=True, key=f"info_{selected_indexador}") # Mostra o conteúdo bloqueado.

                        # --- NOVO: Nuvem de Palavras e Keywords ---
                        st.divider()
                        st.subheader("Nuvem de Palavras e Termos Financeiros Frequentes")
                        with st.spinner("Gerando nuvem de palavras e analisando termos..."):
                             wordcloud_img, df_fin_keywords, context_map = generate_word_cloud_and_keywords(info_adicional)

                        if wordcloud_img:
                            st.image(wordcloud_img, caption="Nuvem das palavras mais frequentes (após remoção de stopwords)")
                        else:
                            st.caption("Não foi possível gerar a nuvem de palavras.")

                        if df_fin_keywords is not None and not df_fin_keywords.empty:
                            st.markdown("##### Top Termos Financeiros:")
                            st.dataframe(df_fin_keywords, hide_index=True, width=400) # Tabela menor

                            st.markdown("##### Contexto dos Termos:")
                            if context_map:
                                for keyword, snippets in context_map.items():
                                    with st.expander(f"Contexto para '{keyword}' ({len(snippets)} trechos)"):
                                        for i, snippet in enumerate(snippets):
                                            #st.markdown(f"_{i+1}_: ...{snippet}...") # Usar markdown para itálico
                                            st.text_area(
                                            label=f"Trecho {i+1}", # Rótulo para a caixa de texto
                                            value=snippet,
                                            height=100, # Ajuste a altura conforme necessário
                                            key=f"context_{selected_indexador}_{keyword}_{i}" # Chave única
                                            )
                                            if i < len(snippets) - 1: st.markdown("---") # Divisor
                            else:
                                st.caption("Não foi possível encontrar contexto para os termos financeiros.")
                        elif wordcloud_img: # Se a nuvem foi gerada mas keywords não
                             st.caption("Nenhum termo financeiro relevante encontrado entre as palavras mais frequentes.")
                        # --- FIM NOVO ---

                        st.divider()

                        # Exibir Ocorrências Vinculadas
                        st.subheader("Ocorrências Vinculadas")
                        if not ocorrencias_detalhe.empty:
                            st.dataframe(ocorrencias_detalhe[['idOcorrencia', 'Ocorrencia']], width='stretch', hide_index=True)
                        else:
                            st.info("Nenhuma ocorrência vinculada encontrada para este Indexador.")

                        st.divider()

                        # Exibir Envolvidos Vinculados
                        st.subheader("Envolvidos Vinculados")
                        if not envolvidos_detalhe.empty:
                            # Selecionar e formatar colunas para exibição
                            cols_envolvidos = ['cpfCnpjEnvolvido', 'nomeEnvolvido', 'tipoEnvolvido',
                                               'bitPepCitado', 'bitPessoaObrigadaCitado', 'intServidorCitado',
                                               'agenciaEnvolvido', 'contaEnvolvido']
                            cols_envolvidos_exist = [c for c in cols_envolvidos if c in envolvidos_detalhe.columns]

                            # Criar cópia para formatação
                            envolvidos_display = envolvidos_detalhe[cols_envolvidos_exist].copy()

                            # Formatar booleanos
                            for flag in ['bitPepCitado', 'bitPessoaObrigadaCitado', 'intServidorCitado']:
                                 if flag in envolvidos_display.columns:
                                     envolvidos_display[flag] = envolvidos_display[flag].apply(lambda x: "Sim" if str(x).lower()=='sim' or x==True else "Não")

                            st.dataframe(envolvidos_display, width='stretch', hide_index=True,
                                         column_config={
                                             "cpfCnpjEnvolvido": "CPF/CNPJ",
                                             "nomeEnvolvido": "Nome",
                                             "tipoEnvolvido": "Papel",
                                             "bitPepCitado": "PEP",
                                             "bitPessoaObrigadaCitado": "P. Obrigada",
                                             "intServidorCitado": "Servidor P.",
                                             "agenciaEnvolvido": "Agência Env.",
                                             "contaEnvolvido": "Conta Env."
                                         })
                        else:
                            st.info("Nenhum envolvido vinculado encontrado para este Indexador.")


                        # --- NOVO: Visualização do Grafo da Comunicação ---
                        st.divider()
                        st.subheader("Visualização dos Vínculos na Comunicação")
                        if not envolvidos_detalhe.empty:
                            with st.spinner("Gerando grafo da comunicação..."):
                                G_comm, titulares_comm = create_communication_graph(envolvidos_detalhe)

                            if G_comm.number_of_nodes() > 0:

                                # Visualizar o grafo
                                with st.spinner("Renderizando visualização do grafo..."):
                                    comm_graph_file = visualize_communication_graph(G_comm, titulares_comm)

                                if comm_graph_file:
                                    st.components.v1.html(open(comm_graph_file, 'r', encoding='utf-8').read(), height=550)
                                    st.html(generate_network_legend())
                                else:
                                    st.warning("Não foi possível renderizar o grafo da comunicação.")
                            else:
                                st.info("Não há envolvidos suficientes ou válidos para gerar um grafo para esta comunicação.")
                        else:
                            st.info("Não há envolvidos vinculados para gerar o grafo.")


                        # --- MODIFICADO: Tabelas e Gráficos de Fluxo Baseados em Informações Adicionais ---
                        st.divider()
                        st.subheader("Resumo do Fluxo (Extraído de Informações Adicionais)")
                        st.info("⚠️ IMPORTANTE. É possível que esses dados estejam incompletos. Os valores aqui informados não substituem a análise mais detida do conteúdo do campo Informações Adicionais.")

                        if pd.notna(info_adicional) and info_adicional != 'Nenhuma informação adicional disponível.':
                            with st.spinner("Analisando texto de informações adicionais..."):
                                # Chamar a nova função que retorna 3 DataFrames
                                df_creditos_ext, df_debitos_ext, df_cartao_ext = extract_all_financial_data(info_adicional)

                                # --- NOVO: Diagrama de Sankey ---
                                st.markdown("##### 🌊 Diagrama de Fluxo (Sankey)")

                                # Determinar o nome do titular para o centro do gráfico
                                nome_titular_sankey = "Titular/Conta"
                                # Tentar pegar o nome do titular identificado anteriormente na aba
                                if not envolvidos_detalhe.empty:
                                     tits = envolvidos_detalhe[envolvidos_detalhe['tipoEnvolvido'].str.lower().isin(['titular', 'titular da conta'])]
                                     if not tits.empty:
                                         nome_titular_sankey = tits.iloc[0]['nomeEnvolvido']

                                if not df_creditos_ext.empty or not df_debitos_ext.empty:
                                    fig_sankey = plot_sankey_fluxo(df_creditos_ext, df_debitos_ext, nome_titular_sankey)
                                    if fig_sankey:
                                        st.plotly_chart(fig_sankey, use_container_width=True)
                                    else:
                                        st.caption("Dados insuficientes para gerar o diagrama de fluxo.")
                                # --- FIM NOVO ---
                            # --- FIM MODIFICAÇÃO ---

                            st.markdown("##### Principais Origens de Crédito")
                            if not df_creditos_ext.empty:
                                # Ordenar por valor para exibição
                                df_creditos_ext = df_creditos_ext.sort_values('Valor (R$)', ascending=False)
                                st.dataframe(df_creditos_ext, width='stretch', hide_index=True,
                                             column_config={
                                                "Valor (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                                                "Percentual (%)": st.column_config.NumberColumn(format="%.2f%%")
                                                # Remover 'Detalhe' se não estiver mais presente
                                             })
                                fig_cred = px.bar(df_creditos_ext.head(10), y='Origem do Crédito', x='Valor (R$)',
                                                  orientation='h', title='Top 10 Origens de Crédito',
                                                  labels={'Origem do Crédito': 'Origem', 'Valor (R$)': 'Valor Recebido (R$)'},
                                                  text='Valor (R$)', height=400)
                                fig_cred.update_traces(texttemplate='R$ %{x:,.2f}', textposition='outside')
                                fig_cred.update_layout(yaxis={'categoryorder':'total ascending'})
                                st.plotly_chart(fig_cred, use_container_width=True)
                            # else: st.caption("Não foi possível extrair origens de crédito.") # Já tratado na função

                            st.markdown("##### Principais Destinos de Débito")
                            if not df_debitos_ext.empty:
                                # Ordenar por valor para exibição
                                df_debitos_ext = df_debitos_ext.sort_values('Valor (R$)', ascending=False)
                                st.dataframe(df_debitos_ext, width='stretch', hide_index=True,
                                             column_config={
                                                "Valor (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                                                "Percentual (%)": st.column_config.NumberColumn(format="%.2f%%")
                                                # Remover 'Detalhe' se não estiver mais presente
                                             })
                                fig_deb = px.bar(df_debitos_ext.head(10), y='Destino do Débito', x='Valor (R$)',
                                                 orientation='h', title='Top 10 Destinos de Débito',
                                                 labels={'Destino do Débito': 'Destino', 'Valor (R$)': 'Valor Enviado (R$)'},
                                                 text='Valor (R$)', height=400)
                                fig_deb.update_traces(texttemplate='R$ %{x:,.2f}', textposition='outside')
                                fig_deb.update_layout(yaxis={'categoryorder':'total ascending'})
                                st.plotly_chart(fig_deb, use_container_width=True)
                            # else: st.caption("Não foi possível extrair destinos de débito.") # Já tratado na função

                            st.markdown("##### Principais Gastos no Cartão")
                            if not df_cartao_ext.empty:
                                 # Ordenar por valor para exibição
                                 df_cartao_ext = df_cartao_ext.sort_values('Valor (R$)', ascending=False)
                                 st.dataframe(df_cartao_ext, width='stretch', hide_index=True,
                                             column_config={
                                                "Valor (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                                                "Percentual (%)": st.column_config.NumberColumn(format="%.2f%%")
                                             })
                                 fig_card = px.bar(df_cartao_ext.head(10), y='Estabelecimento', x='Valor (R$)',
                                                   orientation='h', title='Top 10 Gastos no Cartão de Crédito',
                                                   labels={'Estabelecimento': 'Estabelecimento', 'Valor (R$)': 'Valor Gasto (R$)'},
                                                   text='Valor (R$)', height=400)
                                 fig_card.update_traces(texttemplate='R$ %{x:,.2f}', textposition='outside')
                                 fig_card.update_layout(yaxis={'categoryorder':'total ascending'})
                                 st.plotly_chart(fig_card, use_container_width=True)
                            # else: st.caption("Não foi possível extrair gastos no cartão.") # Já tratado na função

                        else:
                            st.info("Campo 'Informações Adicionais' vazio ou indisponível para gerar gráficos de fluxo.")
                        # --- FIM MODIFICAÇÃO Bloco Gráficos ---                        
                        
                    else:
                        st.warning(f"Nenhum detalhe de comunicação encontrado para o Indexador {selected_indexador}.")
                else:
                    st.caption("Selecione uma linha na tabela acima para ver o detalhamento completo da comunicação.")
    

    # --- Seção de Exportação (Fora das Abas) ---
    if not df_display.empty:
        st.divider()
        st.header("📤 Exportar Resultados (Baseado nos Dados Filtrados)")
        export_button = st.button("Gerar Relatório Excel (Filtrado)")

        if export_button:
            with st.spinner("Gerando arquivo Excel..."):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"relatorio_RIF_filtrado_{timestamp}.xlsx"

                try:
                    with pd.ExcelWriter(filename) as writer:
                        df_display_export = df_display.copy()
                        cols_to_drop = ['IdadeConta', 'CidadeAgenciaNorm', 'Período']
                        fmt_cols = [f'Valor{c}_fmt' for c in ['A','B','C','D','E']]
                        cols_to_drop.extend([c for c in fmt_cols if c in df_display_export.columns])
                        df_display_export = df_display_export.drop(columns=[col for col in cols_to_drop if col in df_display_export.columns], errors='ignore')
                        df_display_export.to_excel(writer, sheet_name='Dados Consolidados Filtrados', index=False)

                        # Usar variáveis locais se existirem e não estiverem vazias
                        if 'transactions_final_agg' in locals() and not transactions_final_agg.empty:
                            transactions_final_agg.to_excel(writer, sheet_name='Transações por Ocorrência', index=False)
                        if 'segment_communications' in locals() and not segment_communications.empty:
                            segment_communications.to_excel(writer, sheet_name='Comunicações por Segmento', index=False)

                        # Recalcular Top 10s para exportação
                        top_envolvidos_exp = df_display.groupby(['cpfCnpjEnvolvido', 'nomeEnvolvido']).agg(
                            Qtd_Comunicacoes=('idComunicacao', 'nunique'),
                            Valor_Total_A=('ValorTotal', 'sum')
                        ).reset_index()
                        top_envolvidos_exp = top_envolvidos_exp[top_envolvidos_exp['cpfCnpjEnvolvido'] != 'DESCONHECIDO']
                        top_envolvidos_exp = top_envolvidos_exp.sort_values('Qtd_Comunicacoes', ascending=False).head(10)
                        if not top_envolvidos_exp.empty: top_envolvidos_exp.to_excel(writer, sheet_name='Top 10 Envolvidos', index=False)

                        if 'city_communications' in locals() and not city_communications.empty:
                            city_communications.to_excel(writer, sheet_name='Comunicações por Cidade', index=False)

                        if 'tipoEnvolvido' in df_display.columns:
                            depositantes_exp = df_display[df_display['tipoEnvolvido'].str.lower() == 'depositante'].groupby(['cpfCnpjEnvolvido', 'nomeEnvolvido']).agg(
                                Valor_Total_A=('ValorTotal', 'sum')
                            ).reset_index()
                            depositantes_exp = depositantes_exp[depositantes_exp['cpfCnpjEnvolvido'] != 'DESCONHECIDO']
                            depositantes_exp = depositantes_exp.sort_values('Valor_Total_A', ascending=False).head(10)
                            if not depositantes_exp.empty: depositantes_exp.to_excel(writer, sheet_name='Top 10 Depositantes', index=False)

                            sacadores_exp = df_display[df_display['tipoEnvolvido'].str.lower() == 'sacador'].groupby(['cpfCnpjEnvolvido', 'nomeEnvolvido']).agg(
                                Valor_Total_A=('ValorTotal', 'sum')
                            ).reset_index()
                            sacadores_exp = sacadores_exp[sacadores_exp['cpfCnpjEnvolvido'] != 'DESCONHECIDO']
                            sacadores_exp = sacadores_exp.sort_values('Valor_Total_A', ascending=False).head(10)
                            if not sacadores_exp.empty: sacadores_exp.to_excel(writer, sheet_name='Top 10 Sacadores', index=False)

                        # Recalcular padrões suspeitos para garantir que estão atualizados
                        suspicious_df_to_export = analyze_suspicious_patterns(
                            df_display, # Usa o dataframe filtrado atual
                            st.session_state.df_ocorrencias,
                            st.session_state.df_comunicacoes,
                            st.session_state.df_envolvidos
                        )
                        if suspicious_df_to_export is not None and not suspicious_df_to_export.empty:
                            suspicious_df_to_export.to_excel(writer, sheet_name='Padrões Suspeitos Filtrados', index=False)

                        df_segmento_desc.to_excel(writer, sheet_name='Legenda Segmentos', index=False)


                    with open(filename, "rb") as fp:
                        st.download_button(
                            label="Baixar Relatório Filtrado",
                            data=fp,
                            file_name=filename,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    st.success(f"Relatório '{filename}' gerado com sucesso!")
                except Exception as e:
                     st.error(f"Erro ao gerar o arquivo Excel: {e}")
                     st.code(traceback.format_exc())
    else:
        st.info("Aplique filtros que retornem dados para habilitar a exportação.")


# --- Mensagem se nenhum arquivo foi carregado ou botão não pressionado ---
elif not process_button and not st.session_state.data_loaded:
    st.warning("Por favor, carregue todos os arquivos CSV necessários e clique em 'Processar Arquivos Carregados' na barra lateral.")
    st.sidebar.info("Aguardando carregamento e processamento...")
elif process_button and (not file_ocorrencias or not file_envolvidos or not file_comunicacoes):
     st.sidebar.error("Faltam arquivos! Carregue os 3 arquivos CSV e clique em 'Processar'.")


# --- Seção de Ajuda (Sempre visível) ---
with st.expander("❓ Ajuda"):
    st.markdown("""
    **Como usar:**
    1. Faça upload dos 3 arquivos CSV (`Ocorrencias`, `Envolvidos`, `Comunicacoes`) na barra lateral.
    2. Clique no botão **Processar Arquivos Carregados** na barra lateral. O processamento inicial pode levar um tempo.
    3. Utilize os filtros na barra lateral para refinar a análise por data ou tipo de ocorrência. Os dados nas abas serão atualizados automaticamente.
    4. Explore a aba **Análise Geral** para ter uma visão macro dos dados filtrados. Note que as agregações de valor usam o CampoA por padrão.
    5. Verifique a aba **Padrões Suspeitos** para alertas de alto risco identificados nos dados filtrados, incluindo o novo padrão de "Alto Valor em Espécie".
    6. Vá para a aba **Análise de Rede Individual**, selecione um envolvido para visualizar sua rede de conexões diretas (baseado nos filtros atuais).
    7. Na aba **Análise Individual Detalhada**, selecione um envolvido para ver seu dossiê completo, incluindo o significado dos Campos A-E para o segmento da comunicação e os valores corretos.
    8. A aba **Análise por Comunicação** apresenta uma análise detalhada da comunicação. Selecione o indexador da comunicação desejada.
    9. Clique em **Gerar Relatório Excel** (se habilitado) para baixar as tabelas e análises baseadas nos filtros correntes, incluindo uma aba com a legenda dos segmentos.

    **Formato esperado:**
    - Arquivos CSV com separador `;`
    - Colunas de data no formato DD/MM/AAAA (com ou sem hora)
    - Valores numéricos no formato brasileiro (ex: 1.234,56) ou americano (1234.56).
    - Valores nulos/ausentes como campos vazios, `-`, `#N/D`, `N/A`.
    - Codificação UTF-8 ou Latin1 (ou similar compatível)

    **Abas:**
    - **Análise Geral:** Visão macro dos dados filtrados.
    - **Padrões Suspeitos:** Detecção de comportamentos atípicos nos dados filtrados.
    - **Análise de Rede Individual:** Visualização da rede de conexões para um envolvido específico.
    - **Análise Individual Detalhada:** Detalhes específicos por envolvido, com contexto e valores corretos dos campos de valor.
    - **Análise por Comunicação:** Análise detalhada da comunicação. O Diagrama de Fluxo (Sankey) e as tabelas de origens dos créditos e destinos dos débitos são extraídas do campo 'Informações Adicionais'. Por se tratar de uma extração em texto livre, pode conter erros. **Sempre confirme analisando o texto original**.
    """)
