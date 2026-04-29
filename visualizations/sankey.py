# visualizations/sankey.py - Diagramas Sankey
"""
Módulo para criação de diagramas Sankey para visualização de fluxos financeiros.
"""
from __future__ import annotations
import pandas as pd
import plotly.graph_objects as go
from typing import Optional, List


def plot_sankey_fluxo(
    df_cred: pd.DataFrame,
    df_deb: pd.DataFrame,
    titular_nome: str
) -> Optional[go.Figure]:
    """
    Gera um Diagrama de Sankey conectando: Origens (Crédito) -> Titular -> Destinos (Débito).
    
    Args:
        df_cred: DataFrame com origens de crédito
        df_deb: DataFrame com destinos de débito
        titular_nome: Nome do titular central
        
    Returns:
        Figura Plotly ou None se dados insuficientes
    """
    if df_cred.empty and df_deb.empty:
        return None
    
    # Lista de nós (labels) - índice 0 será sempre o Titular
    labels = [titular_nome]
    
    # Listas para construir os links
    sources = []
    targets = []
    values = []
    custom_data = []
    link_colors = []
    
    # Processar Créditos (Origem -> Titular)
    if not df_cred.empty:
        df_cred_top = df_cred.sort_values('Valor (R$)', ascending=False).head(15)
        
        for _, row in df_cred_top.iterrows():
            origem = row['Origem do Crédito']
            valor = row['Valor (R$)']
            
            if origem not in labels:
                labels.append(origem)
            
            idx_origem = labels.index(origem)
            
            sources.append(idx_origem)
            targets.append(0)  # 0 é o Titular
            values.append(valor)
            custom_data.append(f"Crédito: {origem}")
            link_colors.append("rgba(46, 204, 113, 0.4)")  # Verde translúcido
    
    # Processar Débitos (Titular -> Destino)
    if not df_deb.empty:
        df_deb_top = df_deb.sort_values('Valor (R$)', ascending=False).head(15)
        
        for _, row in df_deb_top.iterrows():
            destino = row['Destino do Débito']
            valor = row['Valor (R$)']
            
            if destino not in labels:
                labels.append(destino)
            
            idx_destino = labels.index(destino)
            
            sources.append(0)  # 0 é o Titular
            targets.append(idx_destino)
            values.append(valor)
            custom_data.append(f"Débito: {destino}")
            link_colors.append("rgba(231, 76, 60, 0.4)")  # Vermelho translúcido
    
    if not values:
        return None
    
    # Criar a figura
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=labels,
            color=["#3498DB"] + ["#556270"] * (len(labels) - 1)  # Azul para titular
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color=link_colors,
            hovertemplate='%{value:$.2f}<br />%{customdata}<extra></extra>',
            customdata=custom_data
        )
    )])
    
    fig.update_layout(
        title_text=f"Fluxo Financeiro: {titular_nome}",
        font_size=12,
        height=500
    )
    
    return fig


def plot_sankey_envolvido_estruturado(
    df_envolvido_full: pd.DataFrame,
    selected_cpf: str,
    selected_nome: str,
    min_value: float = 0,
    top_n: int = 10
) -> Optional[go.Figure]:
    """
    Gera um Sankey com filtros de valor mínimo e limitador de contrapartes.
    Agrupa valores pequenos em um nó 'Outros'.
    
    Args:
        df_envolvido_full: DataFrame com dados dos envolvidos
        selected_cpf: CPF/CNPJ do envolvido selecionado
        selected_nome: Nome do envolvido
        min_value: Valor mínimo para incluir contraparte
        top_n: Número máximo de contrapartes por lado
        
    Returns:
        Figura Plotly ou None se dados insuficientes
    """
    # Filtrar comunicações do alvo
    rifs_do_alvo = df_envolvido_full[
        df_envolvido_full['cpfCnpjEnvolvido'] == selected_cpf
    ]['Indexador_x'].unique()
    
    df_contexto = df_envolvido_full[
        df_envolvido_full['Indexador_x'].isin(rifs_do_alvo)
    ].copy()
    
    # Normalizar tipo de envolvido
    if 'tipoEnvolvido_Norm' not in df_contexto.columns:
        df_contexto['tipoEnvolvido_Norm'] = (
            df_contexto['tipoEnvolvido']
            .astype(str)
            .str.upper()
            .str.strip()
        )
    
    # Achatamento para evitar duplicidade
    df_unique = df_contexto.groupby(
        ['Indexador_x', 'cpfCnpjEnvolvido', 'tipoEnvolvido_Norm']
    ).agg({
        'nomeEnvolvido': 'first',
        'ValorTotal': 'max'
    }).reset_index()
    
    # Agregação por contraparte
    fluxos = []
    
    for idx in rifs_do_alvo:
        rif_data = df_unique[df_unique['Indexador_x'] == idx]
        v = rif_data['ValorTotal'].max()
        
        for _, row in rif_data.iterrows():
            if row['cpfCnpjEnvolvido'] == selected_cpf:
                continue
            
            tipo_norm = row.get('tipoEnvolvido_Norm', '')
            
            tipo = None
            if tipo_norm in ['REMETENTE', 'DEPOSITANTE', 'VENDEDOR', 'OUTORGANTE']:
                tipo = 'Entrada'
            elif tipo_norm in ['BENEFICIARIO', 'SACADOR', 'COMPRADOR', 'OUTORGADO']:
                tipo = 'Saída'
            
            if tipo:
                fluxos.append({
                    'Entidade': row['nomeEnvolvido'],
                    'Valor': v,
                    'Tipo': tipo
                })
    
    if not fluxos:
        return None
    
    df_f = pd.DataFrame(fluxos).groupby(['Entidade', 'Tipo'])['Valor'].sum().reset_index()
    
    # Aplicação de Filtros: Valor Mínimo e Top N
    df_f = df_f[df_f['Valor'] >= min_value]
    df_f = df_f.sort_values('Valor', ascending=False).head(top_n * 2)
    
    if df_f.empty:
        return None
    
    sources, targets, values, labels, colors = [], [], [], [selected_nome], []
    
    for _, row in df_f.iterrows():
        if row['Entidade'] not in labels:
            labels.append(row['Entidade'])
        
        idx_ent = labels.index(row['Entidade'])
        
        if row['Tipo'] == 'Entrada':
            sources.append(idx_ent)
            targets.append(0)
            colors.append("rgba(46, 204, 113, 0.4)")
        else:
            sources.append(0)
            targets.append(idx_ent)
            colors.append("rgba(231, 76, 60, 0.4)")
        
        values.append(row['Valor'])
    
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=labels,
            color="#3498DB"
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color=colors
        )
    )])
    
    fig.update_layout(
        title_text=f"Fluxo Financeiro Filtrado (Top {top_n}): {selected_nome}",
        font_size=10,
        height=600
    )
    
    return fig
