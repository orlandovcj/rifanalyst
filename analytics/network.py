# analytics/network.py - Análise de Redes
"""
Módulo para análise de redes de relacionamento entre envolvidos.

IMPORTANTE: Usa imports ABSOLUTOS (não relativos) para compatibilidade
quando main.py está na raiz do projeto.
"""
from __future__ import annotations
import networkx as nx
import pandas as pd
import streamlit as st
from typing import Tuple, Dict, Set, Optional
from itertools import product, combinations

# IMPORT ABSOLUTO (não usar ..)
from project_utils.helpers import normalize_string


def analyze_individual_network(
    df_full: pd.DataFrame,
    selected_cpf: str
) -> Tuple[nx.DiGraph, Dict, int]:
    """
    Realiza análise de redes DIRECIONAL (DiGraph) para UM envolvido e suas conexões.
    
    Args:
        df_full: DataFrame completo com dados
        selected_cpf: CPF/CNPJ do envolvido selecionado
        
    Returns:
        Tupla com (Grafo, Partição de comunidades, Número de arestas)
    """
    if selected_cpf is None or selected_cpf == 'DESCONHECIDO':
        return nx.DiGraph(), {}, 0
    
    # Filtra dados pelo CPF selecionado
    df_filtered = df_full[df_full['cpfCnpjEnvolvido'] == selected_cpf]
    
    if 'Indexador_x' not in df_filtered.columns:
        st.error("Coluna 'Indexador_x' não encontrada.")
        return nx.DiGraph(), {}, 0
    
    indexadores_selecionado = df_filtered['Indexador_x'].unique()
    
    if len(indexadores_selecionado) == 0:
        return nx.DiGraph(), {}, 0
    
    # Filtra DataFrame para incluir APENAS essas comunicações
    relevant_df = df_full[df_full['Indexador_x'].isin(indexadores_selecionado)].copy()
    
    G = nx.DiGraph()
    
    # Garantir colunas necessárias e tratar NaNs
    relevant_df['cpfCnpjEnvolvido'] = (
        relevant_df['cpfCnpjEnvolvido']
        .fillna('DESCONHECIDO')
        .astype(str)
    )
    relevant_df['nomeEnvolvido'] = (
        relevant_df['nomeEnvolvido']
        .fillna('DESCONHECIDO')
        .apply(normalize_string)
    )
    relevant_df['tipoEnvolvido'] = (
        relevant_df['tipoEnvolvido']
        .fillna('Desconhecido')
        .str.lower()
    )
    
    for flag in ['bitPepCitado', 'bitPessoaObrigadaCitado', 'intServidorCitado']:
        if flag not in relevant_df.columns:
            relevant_df[flag] = False
        else:
            relevant_df[flag] = (
                relevant_df[flag]
                .fillna(False)
                .apply(lambda x: True if str(x).strip().lower() == 'sim' else False)
            )
    
    # Adicionar nós
    node_attributes = (
        relevant_df
        .drop_duplicates(subset=['cpfCnpjEnvolvido'])
        .set_index('cpfCnpjEnvolvido')
    )
    
    for node_id, row in node_attributes.iterrows():
        if node_id == 'DESCONHECIDO':
            continue
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
        
        if num_envolvidos > 100 or num_envolvidos < 2:
            continue
        
        # Identificar papéis
        depositantes = set(
            group.loc[group['tipoEnvolvido'] == 'depositante', 'cpfCnpjEnvolvido'].astype(str)
        ) - {'DESCONHECIDO'}
        
        sacadores = set(
            group.loc[group['tipoEnvolvido'] == 'sacador', 'cpfCnpjEnvolvido'].astype(str)
        ) - {'DESCONHECIDO'}
        
        titulares = set(
            group.loc[group['tipoEnvolvido'].isin(['titular da conta', 'titular']), 'cpfCnpjEnvolvido'].astype(str)
        ) - {'DESCONHECIDO'}
        
        beneficiarios = set(
            group.loc[group['tipoEnvolvido'].isin(['beneficiário', 'beneficiario']), 'cpfCnpjEnvolvido'].astype(str)
        ) - {'DESCONHECIDO'}
        
        remetentes = set(
            group.loc[group['tipoEnvolvido'] == 'remetente', 'cpfCnpjEnvolvido'].astype(str)
        ) - {'DESCONHECIDO'}
        
        outros_envolvidos = (
            set(group['cpfCnpjEnvolvido'].astype(str)) -
            depositantes - sacadores - titulares - beneficiarios - remetentes -
            {'DESCONHECIDO'}
        )
        
        # Lógica de conexão com Titular como centro
        if titulares:
            # Fluxo: Remetente/Depositante -> Titular
            for r, t in product(remetentes.union(depositantes), titulares):
                if r != t and G.has_node(r) and G.has_node(t):
                    G.add_edge(r, t, weight=1, operation='Entrada')
            
            # Fluxo: Titular -> Beneficiário/Sacador
            for t, b in product(titulares, beneficiarios.union(sacadores)):
                if t != b and G.has_node(t) and G.has_node(b):
                    G.add_edge(t, b, weight=1, operation='Saída')
            
            # Conectar 'Outros' APENAS ao(s) Titular(es) (BIDIRECIONAL)
            for o, t in product(outros_envolvidos, titulares):
                if o != t and G.has_node(o) and G.has_node(t):
                    G.add_edge(o, t, weight=0.5, operation='Associado')
                    G.add_edge(t, o, weight=0.5, operation='Associado')
        else:
            # Caso SEM titular explícito
            for r, b in product(remetentes.union(depositantes), beneficiarios.union(sacadores)):
                if r != b and G.has_node(r) and G.has_node(b):
                    G.add_edge(r, b, weight=0.8, operation='Fluxo Direto')
    
    # Detectar comunidades
    partition = {}
    if G.number_of_nodes() > 0:
        try:
            import community as community_louvain
            undirected_G = G.to_undirected()
            if undirected_G.number_of_edges() > 0:
                partition = community_louvain.best_partition(undirected_G, resolution=1.5)
            else:
                partition = {node: i for i, node in enumerate(undirected_G.nodes())}
        except ImportError:
            st.warning("Biblioteca 'python-louvain' não instalada. Comunidades não detectadas.")
            partition = {node: 0 for node in G.nodes()}
        except Exception as e:
            st.warning(f"Não foi possível calcular comunidades: {e}")
            partition = {node: 0 for node in G.nodes()}
    
    return G, partition, G.number_of_edges()


def create_communication_graph(
    df_envolvidos_comunicacao: pd.DataFrame
) -> Tuple[nx.DiGraph, list]:
    """
    Cria um grafo NetworkX DIRECIONAL para os envolvidos de uma única comunicação.
    
    Args:
        df_envolvidos_comunicacao: DataFrame com envolvidos de uma comunicação
        
    Returns:
        Tupla com (Grafo, Lista de CPFs dos titulares)
    """
    G_comm = nx.DiGraph()
    
    node_roles = {}
    titulares = []
    
    # Adicionar nós com atributos e mapear papéis principais
    for _, row in df_envolvidos_comunicacao.iterrows():
        node_id = str(row.get('cpfCnpjEnvolvido', 'DESCONHECIDO')).strip()
        if node_id == 'DESCONHECIDO':
            continue
        
        nome = normalize_string(row.get('nomeEnvolvido', 'DESCONHECIDO'))
        tipo = str(row.get('tipoEnvolvido', 'Desconhecido')).lower().strip()
        
        # Priorização de papel
        if node_id not in node_roles or tipo in ['titular da conta', 'titular']:
            node_roles[node_id] = tipo
        
        if node_id not in G_comm:
            G_comm.add_node(
                node_id,
                label=nome,
                pep=True if str(row.get('bitPepCitado', 'Não')).lower() == 'sim' else False,
                servidor=True if str(row.get('intServidorCitado', 'Não')).lower() == 'sim' else False
            )
    
    # Identificar titulares e definir roles
    for node_id, role in node_roles.items():
        if role in ['titular da conta', 'titular']:
            titulares.append(node_id)
            G_comm.nodes[node_id]['role'] = 'Titular'
        else:
            G_comm.nodes[node_id]['role'] = role.capitalize()
    
    # Categorias para tipo de linha
    financeiro_entrada = ['remetente', 'vendedor', 'depositante', 'outorgante']
    financeiro_saida = ['beneficiário', 'beneficiario', 'comprador', 'sacador', 'outorgado']
    associativo = ['sócio', 'socio', 'procurador', 'representante', 'responsável', 
                   'responsavel', 'outros', 'procurador / representante legal']
    
    # Criação das Arestas
    if titulares:
        for node_id, role in node_roles.items():
            role_l = role.lower().strip()
            
            for t in titulares:
                if node_id == t:
                    continue
                
                # FLUXO FINANCEIRO: Linha Sólida
                if any(x in role_l for x in financeiro_entrada):
                    G_comm.add_edge(node_id, t, operation='Fluxo: Entrada', dash=False)
                elif any(x in role_l for x in financeiro_saida):
                    G_comm.add_edge(t, node_id, operation='Fluxo: Saída', dash=False)
                
                # VÍNCULO ASSOCIATIVO: Linha Pontilhada
                elif any(a in role_l for a in associativo):
                    G_comm.add_edge(node_id, t, operation='Vínculo: Associativo', dash=True)
                    G_comm.add_edge(t, node_id, operation='Vínculo: Associativo', dash=True)
    
    return G_comm, titulares


def simplify_graph(G_original: nx.DiGraph, central_node: str) -> nx.DiGraph:
    """
    Cria um grafo simplificado contendo apenas o nó central e seus vizinhos diretos.
    
    Args:
        G_original: Grafo original
        central_node: Nó central
        
    Returns:
        Grafo simplificado
    """
    if central_node not in G_original:
        return nx.DiGraph()
    
    G_simplified = nx.DiGraph()
    
    # Pega vizinhos diretos
    predecessors = list(G_original.predecessors(central_node))
    successors = list(G_original.successors(central_node))
    neighbors = set(predecessors + successors)
    
    # Adicionar nó central
    if G_original.has_node(central_node):
        G_simplified.add_node(central_node, **G_original.nodes[central_node])
    
    # Adicionar vizinhos e arestas
    for neighbor in neighbors:
        if G_original.has_node(neighbor):
            G_simplified.add_node(neighbor, **G_original.nodes[neighbor])
            
            if G_original.has_edge(neighbor, central_node):
                G_simplified.add_edge(neighbor, central_node, **G_original.edges[neighbor, central_node])
            if G_original.has_edge(central_node, neighbor):
                G_simplified.add_edge(central_node, neighbor, **G_original.edges[central_node, neighbor])
    
    return G_simplified


@st.cache_data
def analyze_global_network_actors(df_full: pd.DataFrame) -> pd.DataFrame:
    """
    Cria um grafo global e calcula a centralidade de intermediação para todos os envolvidos.

    Args:
        df_full: DataFrame completo com todos os dados.

    Returns:
        DataFrame com CPF/CNPJ, Nome e Score de Centralidade.
    """
    if df_full.empty or 'Indexador_x' not in df_full.columns or 'cpfCnpjEnvolvido' not in df_full.columns:
        return pd.DataFrame(columns=['cpfCnpjEnvolvido', 'nomeEnvolvido', 'centrality_score'])

    G_global = nx.Graph()

    # Adicionar nós para garantir que todos os envolvidos estejam no grafo
    nodes_df = df_full[['cpfCnpjEnvolvido', 'nomeEnvolvido']].drop_duplicates()
    for _, row in nodes_df.iterrows():
        cpf = row['cpfCnpjEnvolvido']
        nome = row['nomeEnvolvido']
        if cpf != 'DESCONHECIDO':
            G_global.add_node(cpf, label=nome)

    # Agrupar por comunicação e criar arestas
    grouped = df_full.groupby('Indexador_x')['cpfCnpjEnvolvido'].unique()
    for _, envolvidos in grouped.items():
        nodes_in_comm = [e for e in envolvidos if e != 'DESCONHECIDO']
        if len(nodes_in_comm) > 1:
            for node1, node2 in combinations(nodes_in_comm, 2):
                if G_global.has_edge(node1, node2):
                    G_global[node1][node2]['weight'] += 1
                else:
                    G_global.add_edge(node1, node2, weight=1)

    if G_global.number_of_nodes() == 0:
        return pd.DataFrame(columns=['cpfCnpjEnvolvido', 'nomeEnvolvido', 'centrality_score'])

    # Calcular centralidade de intermediação
    centrality = nx.betweenness_centrality(G_global, weight='weight')

    # Criar DataFrame com os resultados
    centrality_df = pd.DataFrame(centrality.items(), columns=['cpfCnpjEnvolvido', 'centrality_score'])
    
    # Adicionar nomes
    centrality_df = pd.merge(centrality_df, nodes_df, on='cpfCnpjEnvolvido', how='left')
    
    # Ordenar e retornar
    return centrality_df.sort_values('centrality_score', ascending=False).reset_index(drop=True)


def calculate_network_metrics(G: nx.DiGraph) -> Dict:
    """
    Calcula métricas de centralidade e estrutura do grafo.
    
    Args:
        G: Grafo NetworkX
        
    Returns:
        Dicionário com métricas calculadas
    """
    if G is None or G.number_of_nodes() == 0:
        return {}
    
    metrics = {
        'nodes': G.number_of_nodes(),
        'edges': G.number_of_edges(),
        'density': nx.density(G) if G.number_of_nodes() > 1 else 0,
    }
    
    # Centralidade de grau
    try:
        degree_cent = nx.degree_centrality(G)
        metrics['max_degree_centrality'] = max(degree_cent.values()) if degree_cent else 0
        metrics['avg_degree_centrality'] = sum(degree_cent.values()) / len(degree_cent) if degree_cent else 0
    except:
        pass
    
    # Centralidade de intermediação (betweenness)
    try:
        betweenness = nx.betweenness_centrality(G)
        metrics['max_betweenness'] = max(betweenness.values()) if betweenness else 0
    except:
        pass
    
    # Componentes conectados
    try:
        undirected = G.to_undirected()
        components = list(nx.connected_components(undirected))
        metrics['num_components'] = len(components)
        metrics['largest_component_size'] = max(len(c) for c in components) if components else 0
    except:
        pass
    
    return metrics


def get_top_central_nodes(G: nx.DiGraph, metric: str = 'degree', top_n: int = 10) -> list:
    """
    Retorna os nós mais centrais do grafo.
    
    Args:
        G: Grafo NetworkX
        metric: Métrica de centralidade ('degree', 'betweenness', 'closeness')
        top_n: Número de nós a retornar
        
    Returns:
        Lista de tuplas (nó, valor_centralidade)
    """
    if G is None or G.number_of_nodes() == 0:
        return []
    
    try:
        if metric == 'degree':
            centrality = nx.degree_centrality(G)
        elif metric == 'betweenness':
            centrality = nx.betweenness_centrality(G)
        elif metric == 'closeness':
            centrality = nx.closeness_centrality(G)
        else:
            centrality = nx.degree_centrality(G)
        
        sorted_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
        return sorted_nodes[:top_n]
    except:
        return []
