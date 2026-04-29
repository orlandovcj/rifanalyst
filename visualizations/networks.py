# visualizations/networks.py - Visualização de Redes
"""
Módulo para visualização de grafos de relacionamento com Pyvis.
"""
from __future__ import annotations
import tempfile
import streamlit as st
import networkx as nx
from typing import Dict, Optional
from pyvis.network import Network


def visualize_network(
    G: nx.DiGraph,
    partition: Dict,
    selected_cpf: str = None
) -> Optional[str]:
    """
    Gera visualização Pyvis para o grafo, destacando o fluxo do nó selecionado.

    Args:
        G: Grafo NetworkX
        partition: Dicionário de partições/comunidades (não utilizado para coloração)
        selected_cpf: CPF/CNPJ do nó central selecionado para destaque do fluxo.
        
    Returns:
        Caminho do arquivo HTML gerado ou None se erro.
    """
    if G is None or G.number_of_nodes() == 0:
        st.warning("Nenhuma conexão para visualizar.")
        return None

    net = Network(
        height="750px",
        width="100%",
        bgcolor="#f0f2f6",
        font_color="black",
        directed=True
    )

    for node in G.nodes():
        node_data = G.nodes[node]
        is_selected = node == selected_cpf

        node_size = 25 if is_selected else 15
        node_color = "#E74C3C" if is_selected else "#556270"  # Vermelho se selecionado, senão cinza

        # Montar título (tooltip)
        title_lines = [
            f"Nome: {node_data.get('label', 'N/A')}",
            f"CPF/CNPJ: {node}",
            f"Papel: {node_data.get('role', 'N/A')}"
        ]
        if is_selected:
            title_lines.insert(0, "**Selecionado:**")

        net.add_node(
            node,
            label=node_data.get('label', 'DESCONHECIDO'),
            size=node_size,
            color=node_color,
            title="\n".join(title_lines)
        )
    
    # Adicionar arestas com cores baseadas no fluxo
    for edge in G.edges(data=True):
        source, target, data = edge
        if source in G and target in G:
            op = data.get('operation', 'conexão')
            weight = data.get('weight', 1)
            display_value = min(weight * 2, 10)
            
            # Lógica de cor da aresta
            if source == selected_cpf:
                edge_color = "#E74C3C"  # Vermelho para SAÍDA
            elif target == selected_cpf:
                edge_color = "#2B7CE9"  # Azul para ENTRADA
            else:
                edge_color = "#848484"  # Cinza para outros

            net.add_edge(source, target, value=display_value, title=f"{op} (Peso: {weight})", color=edge_color)
    
    # Configurar física
    net.repulsion(
        node_distance=250,
        central_gravity=0.1,
        spring_length=200,
        spring_strength=0.05,
        damping=0.1
    )
    net.show_buttons(filter_=['physics'])
    
    try:
        # Sanitização do nome do arquivo
        file_id_base = "network"
        if selected_cpf:
            sanitized_cpf = str(selected_cpf).replace('/', '_').replace('.', '_').replace('-', '_')
            file_id_base = f"net_{sanitized_cpf}"
        
        file_id_base = file_id_base[:50]
        suffix = f"_{file_id_base}.html"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, mode='w', encoding='utf-8') as tmpfile:
            net.save_graph(tmpfile.name)
            return tmpfile.name
            
    except Exception as e:
        st.error(f"Erro ao gerar visualização da rede: {str(e)}")
        return None


def visualize_communication_graph(
    G: nx.DiGraph,
    titulares_cpf: list
) -> Optional[str]:
    """
    Gera visualização Pyvis destacando fluxos financeiros (sólidos) e associações (tracejadas).
    
    Args:
        G: Grafo NetworkX da comunicação
        titulares_cpf: Lista de CPFs dos titulares
        
    Returns:
        Caminho do arquivo HTML ou None se erro
    """
    if G is None or G.number_of_nodes() == 0:
        st.warning("Grafo da comunicação está vazio.")
        return None
    
    net = Network(
        height="500px",
        width="100%",
        bgcolor="#f0f2f6",
        font_color="black",
        directed=True
    )
    
    # Configuração visual dos Nós
    for node in G.nodes():
        node_data = G.nodes[node]
        is_titular = node in titulares_cpf
        
        node_size = 25 if is_titular else 15
        node_color = (
            "#E74C3C" if is_titular else
            "#FF6B6B" if node_data.get('pep', False) else
            "#FFD700" if node_data.get('servidor', False) else
            "#556270"
        )
        
        title = (
            f"Nome: {node_data.get('label', 'N/A')}\n"
            f"CPF/CNPJ: {node}\n"
            f"Papel: {node_data.get('role', 'N/A')}\n"
            f"PEP: {'Sim' if node_data.get('pep', False) else 'Não'}\n"
            f"Servidor: {'Sim' if node_data.get('servidor', False) else 'Não'}"
            + ("\n**Titular da Conta**" if is_titular else "")
        )
        
        net.add_node(
            node,
            label=node_data.get('label', 'DESCONHECIDO'),
            size=node_size,
            color=node_color,
            title=title
        )
    
    # Configuração visual das Arestas
    for edge in G.edges(data=True):
        source, target, data = edge
        if source in G and target in G:
            is_dashed = data.get('dash', False)
            op = data.get('operation', '')
            
            # Determinação da cor
            if is_dashed:
                edge_color = "#848484"  # Cinza para vínculos associativos
            elif "Entrada" in op:
                edge_color = "#2B7CE9"  # Azul para Entradas
            elif "Saída" in op:
                edge_color = "#E74C3C"  # Vermelho para Saídas
            else:
                edge_color = "#2B7CE9"
            
            net.add_edge(
                source,
                target,
                title=op,
                dashes=is_dashed,
                color=edge_color,
                width=1 if is_dashed else 2,
                arrows='to' if not is_dashed else ''
            )
    
    net.repulsion(node_distance=150, central_gravity=0.2, spring_length=100)
    net.show_buttons(filter_=['physics'])
    
    try:
        file_id = "comm"
        if titulares_cpf:
            clean_cpf_cnpj = ''.join(filter(str.isalnum, titulares_cpf[0]))
            file_id = f"comm_{clean_cpf_cnpj}"
        
        suffix = f"_{file_id}.html"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, mode='w', encoding='utf-8') as tmpfile:
            net.save_graph(tmpfile.name)
            return tmpfile.name
            
    except Exception as e:
        st.error(f"Erro ao gerar visualização do grafo da comunicação: {str(e)}")
        return None


def generate_network_legend(group_colors: Optional[Dict[int, str]] = None) -> str:
    """
    Gera o HTML para a legenda de cores do gráfico de rede, incluindo subgrupos dinâmicos.

    Args:
        group_colors: Dicionário mapeando ID de grupo para cor.

    Returns:
        HTML com legenda de cores.
    """
    # Cores estáticas para papéis específicos
    static_colors = {
        "Selecionado / Titular (Com.)": "#E74C3C",
        "PEP": "#FF6B6B",
        "Servidor Público": "#FFD700",
        "Titular (Rede Ind.)": "#3498DB",
        "Pessoa Obrigada": "#4ECDC4",
    }

    legend_html = "<div style='display: flex; flex-wrap: wrap; justify-content: center; margin-bottom: 15px;'>"

    # Adicionar cores estáticas
    for label, color in static_colors.items():
        legend_html += f"""
        <div style='margin: 5px; display: flex; align-items: center;'>
            <span style='background-color:{color}; width: 15px; height: 15px; border-radius: 50%; display: inline-block; margin-right: 5px;'></span>
            <span>{label}</span>
        </div>
        """
    
    # Adicionar cores de grupos dinâmicos, se houver
    if group_colors:
        sorted_groups = sorted(group_colors.items())
        for i, (group_id, color) in enumerate(sorted_groups):
            # Se a cor do grupo for a mesma de "Outro", pula para evitar duplicidade
            if color == "#556270":
                continue
            legend_html += f"""
            <div style='margin: 5px; display: flex; align-items: center;'>
                <span style='background-color:{color}; width: 15px; height: 15px; border-radius: 50%; display: inline-block; margin-right: 5px;'></span>
                <span>Subgrupo {i + 1}</span>
            </div>
            """

    # Adicionar a cor "Outro" por último
    legend_html += f"""
    <div style='margin: 5px; display: flex; align-items: center;'>
        <span style='background-color:#556270; width: 15px; height: 15px; border-radius: 50%; display: inline-block; margin-right: 5px;'></span>
        <span>Outro / Padrão</span>
    </div>
    """
    
    legend_html += "</div>"
    return legend_html
