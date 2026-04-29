# visualizations/charts.py - Gráficos Plotly
"""
Módulo para criação de gráficos interativos com Plotly.
"""
from __future__ import annotations
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional


def plot_temporal_evolution(
    df: pd.DataFrame,
    date_col: str = 'Data_da_operacao',
    granularity: str = 'Mensal',
    title: str = 'Evolução Temporal'
) -> Optional[go.Figure]:
    """
    Cria gráfico de linha para evolução temporal das comunicações.
    
    Args:
        df: DataFrame com dados
        date_col: Nome da coluna de data
        granularity: Granularidade ('Diária', 'Semanal', 'Mensal', 'Trimestral')
        title: Título do gráfico
        
    Returns:
        Figura Plotly ou None se dados insuficientes
    """
    if df.empty or date_col not in df.columns:
        return None
    
    df_temp = df.copy()
    df_temp = df_temp.dropna(subset=[date_col])
    
    if df_temp.empty:
        return None
    
    # Definir período baseado na granularidade
    if granularity == 'Diária':
        df_temp['Período'] = df_temp[date_col].dt.date
    elif granularity == 'Semanal':
        df_temp['Período'] = df_temp[date_col].dt.to_period('W').apply(lambda p: p.strftime('%Y-%U'))
    elif granularity == 'Mensal':
        df_temp['Período'] = df_temp[date_col].dt.to_period('M').astype(str)
    elif granularity == 'Trimestral':
        df_temp['Período'] = df_temp[date_col].dt.to_period('Q').astype(str)
    
    # Agregar por período
    temporal = df_temp.groupby('Período').agg(
        Comunicações=('Indexador_x', 'nunique')
    ).reset_index()
    
    temporal = temporal.sort_values('Período')
    
    fig = px.line(
        temporal,
        x='Período',
        y='Comunicações',
        title=f'{title} ({granularity})',
        text='Comunicações',
        markers=True
    )
    
    fig.update_traces(textposition='top center')
    fig.update_layout(
        xaxis_title='Período',
        yaxis_title='Quantidade de Comunicações',
        hovermode='x unified'
    )
    
    return fig


def plot_bar_top_items(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    orientation: str = 'h',
    color_col: str = None,
    top_n: int = 20
) -> Optional[go.Figure]:
    """
    Cria gráfico de barras para top N itens.
    
    Args:
        df: DataFrame com dados
        x_col: Coluna para eixo X
        y_col: Coluna para eixo Y
        title: Título do gráfico
        orientation: Orientação ('h' para horizontal, 'v' para vertical)
        color_col: Coluna para colorir barras
        top_n: Número de itens a mostrar
        
    Returns:
        Figura Plotly ou None se dados insuficientes
    """
    if df.empty:
        return None
    
    df_plot = df.nlargest(top_n, y_col)
    
    fig = px.bar(
        df_plot,
        x=x_col if orientation == 'v' else y_col,
        y=y_col if orientation == 'v' else x_col,
        color=color_col,
        orientation=orientation,
        title=title
    )
    
    if orientation == 'h':
        fig.update_layout(yaxis={'categoryorder': 'total ascending'})
    
    return fig


def plot_pie_distribution(
    df: pd.DataFrame,
    names_col: str,
    values_col: str,
    title: str
) -> Optional[go.Figure]:
    """
    Cria gráfico de pizza para distribuição.
    
    Args:
        df: DataFrame com dados
        names_col: Coluna com nomes/categorias
        values_col: Coluna com valores
        title: Título do gráfico
        
    Returns:
        Figura Plotly ou None se dados insuficientes
    """
    if df.empty:
        return None
    
    fig = px.pie(
        df,
        names=names_col,
        values=values_col,
        title=title
    )
    
    fig.update_traces(textposition='inside', textinfo='percent+label')
    
    return fig


def plot_scatter_risk(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    size_col: str = None,
    color_col: str = None,
    hover_name: str = None,
    title: str = 'Dispersão de Risco'
) -> Optional[go.Figure]:
    """
    Cria gráfico de dispersão para análise de risco.
    
    Args:
        df: DataFrame com dados
        x_col: Coluna para eixo X (geralmente valor)
        y_col: Coluna para eixo Y (geralmente score)
        size_col: Coluna para tamanho dos pontos
        color_col: Coluna para cor dos pontos
        hover_name: Coluna para nome no hover
        title: Título do gráfico
        
    Returns:
        Figura Plotly ou None se dados insuficientes
    """
    if df.empty:
        return None
    
    fig = px.scatter(
        df,
        x=x_col,
        y=y_col,
        size=size_col or y_col,
        color=color_col or y_col,
        hover_name=hover_name,
        title=title,
        labels={
            x_col: 'Valor Total (R$)',
            y_col: 'Score de Risco'
        }
    )
    
    fig.update_layout(
        xaxis_title='Valor Total (R$)',
        yaxis_title='Score de Risco'
    )
    
    return fig


def plot_relationship_strength(
    df_full: pd.DataFrame,
    cpf_base: str
) -> Optional[go.Figure]:
    """
    Gera gráfico de barras mostrando força dos vínculos de um envolvido.
    
    Args:
        df_full: DataFrame completo
        cpf_base: CPF/CNPJ do envolvido base
        
    Returns:
        Figura Plotly ou None se dados insuficientes
    """
    if df_full is None or df_full.empty:
        return None
    
    required_cols = ["cpfCnpjEnvolvido", "Indexador_x", "ValorTotal"]
    for col in required_cols:
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
    df_sub = df_sub.drop_duplicates(subset=["Indexador_x", "cpfCnpjEnvolvido"])
    
    # Self-merge para obter pares
    df_pairs = df_sub.merge(
        df_sub,
        on="Indexador_x",
        suffixes=("_orig", "_contra"),
    )
    
    # Mantém apenas pares onde orig é base e contra é outro
    df_pairs = df_pairs[
        (df_pairs["cpfCnpjEnvolvido_orig"] == str(cpf_base)) &
        (df_pairs["cpfCnpjEnvolvido_contra"] != str(cpf_base))
    ].copy()
    
    if df_pairs.empty:
        return None
    
    df_pairs["valor_vinculo"] = df_pairs["ValorTotal_contra"]
    
    # Agrega por contraparte
    agg = (
        df_pairs.groupby("cpfCnpjEnvolvido_contra", as_index=False)
        .agg(
            n_comunicacoes=("Indexador_x", "nunique"),
            valor_total=("valor_vinculo", "sum"),
        )
    )
    
    # Junta nome da contraparte
    if "nomeEnvolvido_contra" in df_pairs.columns:
        nomes = (
            df_pairs.groupby("cpfCnpjEnvolvido_contra", as_index=False)["nomeEnvolvido_contra"]
            .agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else x.iloc[0])
            .rename(columns={"nomeEnvolvido_contra": "NomeContraparte"})
        )
        agg = agg.merge(nomes, on="cpfCnpjEnvolvido_contra", how="left")
    else:
        agg["NomeContraparte"] = agg["cpfCnpjEnvolvido_contra"]
    
    # Ordena e limita
    agg = agg.sort_values("valor_total", ascending=False).head(30)
    agg["Label"] = agg["NomeContraparte"] + " (" + agg["cpfCnpjEnvolvido_contra"] + ")"
    
    fig = px.bar(
        agg,
        y="Label",
        x="valor_total",
        orientation="h",
        color="n_comunicacoes",
        labels={
            "valor_total": "Valor Total (R$)",
            "n_comunicacoes": "Qtd. Comunicações",
            "Label": "Contraparte",
        },
        title="Força dos vínculos (Valor Total e nº de comunicações)",
        hover_data=["n_comunicacoes"],
        height=600,
    )
    
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    
    return fig


def plot_benford_analysis(df: pd.DataFrame, value_col: str = 'ValorTotal') -> Optional[go.Figure]:
    """
    Calcula e plota a Lei de Benford para detecção de anomalias numéricas.
    
    Args:
        df: DataFrame com dados
        value_col: Coluna com valores numéricos
        
    Returns:
        Figura Plotly ou None se dados insuficientes
    """
    import math
    
    if value_col not in df.columns or df.empty:
        return None
    
    # Pegar primeiro dígito de valores > 0
    valores = df[df[value_col] > 0][value_col].astype(str).str[0].astype(int)
    valores = valores[valores > 0]  # Filtrar dígitos 1-9
    
    if len(valores) < 100:
        return None
    
    contagem = valores.value_counts(normalize=True).sort_index()
    df_benford = pd.DataFrame({
        'Dígito': contagem.index,
        'Real (%)': contagem.values * 100
    })
    
    # Probabilidades esperadas por Benford
    df_benford['Esperado (%)'] = [
        math.log10(1 + 1/d) * 100 for d in df_benford['Dígito']
    ]
    
    fig = px.bar(
        df_benford,
        x='Dígito',
        y=['Real (%)', 'Esperado (%)'],
        barmode='group',
        title='Análise da Lei de Benford (Detecção de Anomalias Numéricas)',
        labels={'value': 'Frequência (%)', 'variable': 'Tipo'}
    )
    
    return fig
