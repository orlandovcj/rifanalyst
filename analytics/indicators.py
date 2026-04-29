# analytics/indicators.py - Cálculo de Indicadores
"""
Módulo para cálculo de indicadores de risco e métricas estatísticas.
"""
from __future__ import annotations
import pandas as pd
import numpy as np
import streamlit as st
from typing import Optional

from project_utils.helpers import safe_div, normalize_string


def calc_indicadores_envolvido(
    df: pd.DataFrame,
    valor_col: str = "ValorTotal",
    data_col: str = "Data_da_operacao"
) -> pd.DataFrame:
    """
    Calcula indicadores agregados por CPF/CNPJ de envolvido.
    
    Args:
        df: DataFrame com dados consolidados
        valor_col: Nome da coluna de valor
        data_col: Nome da coluna de data
        
    Returns:
        DataFrame com indicadores por envolvido
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    df_local = df.copy()
    
    # Detecção automática da coluna de data
    if data_col not in df_local.columns and "Datadaoperacao" in df_local.columns:
        data_col = "Datadaoperacao"
    
    if data_col not in df_local.columns:
        df_local[data_col] = pd.NaT
    
    df_local[valor_col] = pd.to_numeric(df_local[valor_col], errors="coerce").fillna(0.0)
    
    # 1. Achatamento: 1 linha por Envolvido + Comunicação
    agg_dict = {
        "nomeEnvolvido": "first",
        valor_col: "max",
        "idComunicacao": "first",
        "bitPepCitado": "max",
        "bitPessoaObrigadaCitado": "max",
        "intServidorCitado": "max"
    }
    
    if data_col in df_local.columns:
        agg_dict[data_col] = "first"
    
    df_unique = df_local.groupby(
        ["cpfCnpjEnvolvido", "Indexador_x"], dropna=False
    ).agg(agg_dict).reset_index()
    
    # 2. Agregação por Envolvido
    base_agg = df_unique.groupby("cpfCnpjEnvolvido", dropna=False).agg(
        nomeEnvolvido=("nomeEnvolvido", "first"),
        n_comunicacoes=("Indexador_x", "nunique"),
        valor_total=(valor_col, "sum"),
        flag_pep=("bitPepCitado", "max"),
        flag_servidor=("intServidorCitado", "max"),
        flag_pessoa_obrigada=("bitPessoaObrigadaCitado", "max")
    ).reset_index()
    
    # 3. Fracionamento (Baseado em dias distintos)
    if data_col in df_local.columns and not df_local[data_col].isna().all():
        df_local['dia'] = pd.to_datetime(df_local[data_col], errors='coerce').dt.date
        daily = df_local.dropna(subset=['dia']).groupby(
            ['cpfCnpjEnvolvido', 'dia']
        ).agg(n_ops=('Indexador_x', 'nunique')).reset_index()
        frac = daily[daily['n_ops'] >= 3].groupby('cpfCnpjEnvolvido').size().reset_index(
            name='fracionamento_dias_com_3+_ops'
        )
    else:
        frac = pd.DataFrame(columns=['cpfCnpjEnvolvido', 'fracionamento_dias_com_3+_ops'])
    
    # 4. HHI (Concentração de Contrapartes)
    df_contra = df_unique.merge(
        df_unique[['Indexador_x', 'cpfCnpjEnvolvido', valor_col]],
        on='Indexador_x', suffixes=('', '_c')
    )
    df_contra = df_contra[df_contra['cpfCnpjEnvolvido'] != df_contra['cpfCnpjEnvolvido_c']]
    
    if not df_contra.empty:
        pares = df_contra.groupby(
            ['cpfCnpjEnvolvido', 'cpfCnpjEnvolvido_c']
        )[valor_col + '_c'].sum().reset_index(name='v_par')
        totais = pares.groupby('cpfCnpjEnvolvido')['v_par'].sum().reset_index(name='v_tot')
        pares = pares.merge(totais, on='cpfCnpjEnvolvido')
        pares['share'] = pares.apply(lambda r: safe_div(r['v_par'], r['v_tot']), axis=1)
        hhi = pares.groupby('cpfCnpjEnvolvido')['share'].apply(
            lambda x: float(np.sum(x**2))
        ).reset_index(name='hhi_contrapartes')
    else:
        hhi = pd.DataFrame(columns=['cpfCnpjEnvolvido', 'hhi_contrapartes'])
    
    # Merge final
    result = base_agg.merge(frac, on='cpfCnpjEnvolvido', how='left')
    result = result.merge(hhi, on='cpfCnpjEnvolvido', how='left').fillna(0)
    
    return result


def calc_indicadores_comunicacao(
    df: pd.DataFrame,
    valor_col: str = "ValorTotal"
) -> pd.DataFrame:
    """
    Calcula indicadores agregados por comunicação.
    
    Args:
        df: DataFrame com dados consolidados
        valor_col: Nome da coluna de valor
        
    Returns:
        DataFrame com indicadores por comunicação
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    return df.groupby("Indexador_x").agg(
        n_envolvidos=("cpfCnpjEnvolvido", "nunique"),
        valor_total=(valor_col, "max"),
        flag_pep_na_com=("bitPepCitado", "max")
    ).reset_index().sort_values("valor_total", ascending=False)


def calc_indicadores_pares(
    df: pd.DataFrame,
    valor_col: str = "ValorTotal"
) -> pd.DataFrame:
    """
    Calcula indicadores de pares de envolvidos (contrapartes).
    
    Args:
        df: DataFrame com dados consolidados
        valor_col: Nome da coluna de valor
        
    Returns:
        DataFrame com indicadores por par
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    df_base = df.groupby(["Indexador_x", "cpfCnpjEnvolvido"])[valor_col].max().reset_index()
    df_p = df_base.merge(df_base, on="Indexador_x", suffixes=("_orig", "_contra"))
    df_p = df_p[df_p["cpfCnpjEnvolvido_orig"] != df_p["cpfCnpjEnvolvido_contra"]]
    
    return df_p.groupby(["cpfCnpjEnvolvido_orig", "cpfCnpjEnvolvido_contra"]).agg(
        valor_total_par=(valor_col + "_contra", "sum"),
        n_comunicacoes_compartilhadas=("Indexador_x", "nunique")
    ).reset_index().rename(columns={
        "cpfCnpjEnvolvido_orig": "cpf_origem",
        "cpfCnpjEnvolvido_contra": "cpf_contraparte"
    })


def calcular_hhi(series: pd.Series) -> float:
    """
    Calcula o Índice de Herfindahl-Hirschman para uma série de valores.
    
    O HHI mede a concentração de mercado. Valores:
    - < 0.15: Baixa concentração
    - 0.15 - 0.25: Concentração moderada
    - > 0.25: Alta concentração
    
    Args:
        series: Series com valores
        
    Returns:
        HHI (0 a 1)
    """
    if series is None or series.empty or series.sum() == 0:
        return 0.0
    
    shares = series / series.sum()
    return float((shares ** 2).sum())


def calcular_gini(series: pd.Series) -> float:
    """
    Calcula o coeficiente de Gini para uma série de valores.
    
    O Gini mede a desigualdade:
    - 0: Igualdade perfeita
    - 1: Desigualdade máxima
    
    Args:
        series: Series com valores
        
    Returns:
        Coeficiente de Gini (0 a 1)
    """
    if series is None or series.empty:
        return 0.0
    
    values = series.dropna().values
    if len(values) == 0:
        return 0.0
    
    values = np.sort(values)
    n = len(values)
    index = np.arange(1, n + 1)
    
    return (2 * np.sum(index * values) - (n + 1) * np.sum(values)) / (n * np.sum(values))


def detectar_outliers_iqr(series: pd.Series, multiplier: float = 1.5) -> pd.Series:
    """
    Detecta outliers usando o método IQR (Intervalo Interquartil).
    
    Args:
        series: Series com valores
        multiplier: Multiplicador do IQR (padrão 1.5)
        
    Returns:
        Series booleano indicando outliers
    """
    if series is None or series.empty:
        return pd.Series(dtype=bool)
    
    Q1 = series.quantile(0.25)
    Q3 = series.quantile(0.75)
    IQR = Q3 - Q1
    
    lower_bound = Q1 - multiplier * IQR
    upper_bound = Q3 + multiplier * IQR
    
    return (series < lower_bound) | (series > upper_bound)


def calcular_zscore(series: pd.Series) -> pd.Series:
    """
    Calcula o Z-Score para uma série de valores.
    
    Args:
        series: Series com valores
        
    Returns:
        Series com Z-Scores
    """
    if series is None or series.empty:
        return pd.Series(dtype=float)
    
    mean = series.mean()
    std = series.std()
    
    if std == 0:
        return pd.Series([0.0] * len(series), index=series.index)
    
    return (series - mean) / std


def resumo_estatistico(df: pd.DataFrame, coluna: str) -> dict:
    """
    Gera resumo estatístico de uma coluna.
    
    Args:
        df: DataFrame
        coluna: Nome da coluna
        
    Returns:
        Dicionário com estatísticas
    """
    if coluna not in df.columns:
        return {}
    
    series = df[coluna].dropna()
    
    if series.empty:
        return {}
    
    return {
        'count': len(series),
        'mean': series.mean(),
        'std': series.std(),
        'min': series.min(),
        'q25': series.quantile(0.25),
        'median': series.median(),
        'q75': series.quantile(0.75),
        'max': series.max(),
        'skewness': series.skew(),
        'kurtosis': series.kurtosis(),
        'hhi': calcular_hhi(series),
        'gini': calcular_gini(series)
    }
