# core/data_processor.py - Processamento de Dados
"""
Módulo para processamento e transformação de dados do RIF.

IMPORTANTE: Usa imports ABSOLUTOS (não relativos) para compatibilidade
quando main.py está na raiz do projeto.
"""
from __future__ import annotations
import pandas as pd
import numpy as np
import streamlit as st
from typing import Optional

# IMPORTS ABSOLUTOS (não usar .. ou .)
from config import SEGMENTO_MAP
from project_utils.helpers import normalize_string, clean_numeric_br
from core.data_loader import safe_merge


def process_raw_data(
    df_ocorrencias: pd.DataFrame,
    df_envolvidos: pd.DataFrame,
    df_comunicacoes: pd.DataFrame
) -> Optional[pd.DataFrame]:
    """
    Processa e mergeia os dados brutos carregados dos três arquivos CSV.
    
    Args:
        df_ocorrencias: DataFrame de ocorrências
        df_envolvidos: DataFrame de envolvidos
        df_comunicacoes: DataFrame de comunicações
        
    Returns:
        DataFrame consolidado ou None se houver erro
    """
    st.write("Iniciando processamento dos dados...")
    
    # 1. Pré-processamento
    df_ocor, df_env, df_comm = _preprocess_dataframes(
        df_ocorrencias, df_envolvidos, df_comunicacoes
    )
    
    # 2. Merge Comunicações + Envolvidos
    st.write("Realizando merge: Comunicações + Envolvidos...")
    df_merged = _merge_communications_envolvidos(df_comm, df_env)
    if df_merged is None:
        return None
    
    # 3. Merge com Ocorrências
    st.write("Realizando merge: + Ocorrências...")
    df_final = _merge_with_ocorrencias(df_merged, df_ocor)
    if df_final is None:
        return None
    
    # 4. Pós-processamento
    st.write("Finalizando processamento...")
    df_final = _postprocess_dataframe(df_final)
    
    st.success(f"Processamento concluído: {len(df_final)} registros")
    return df_final


def _preprocess_dataframes(
    df_ocorrencias: pd.DataFrame,
    df_envolvidos: pd.DataFrame,
    df_comunicacoes: pd.DataFrame
) -> tuple:
    """
    Aplica pré-processamento necessário aos DataFrames.
    """
    df_ocor = df_ocorrencias.copy()
    df_env = df_envolvidos.copy()
    df_comm = df_comunicacoes.copy()
    
    # Normaliza Indexadores
    df_env['Indexador'] = df_env['Indexador'].astype(str).str.strip()
    df_comm['Indexador'] = df_comm['Indexador'].astype(str).str.strip()
    df_ocor['Indexador'] = df_ocor['Indexador'].astype(str).str.strip()
    
    # Normaliza CPF/CNPJ
    df_env['cpfCnpjEnvolvido'] = df_env['cpfCnpjEnvolvido'].astype(str).str.strip()
    
    # Processa código do segmento
    if 'CodigoSegmento' in df_comm.columns:
        df_comm['CodigoSegmento'] = (
            df_comm['CodigoSegmento']
            .astype(str)
            .str.split('.')
            .str[0]
            .str.strip()
        )
    
    # As colunas de valor (ValorCampoA, ValorTotal, etc.) já foram
    # processadas por prepare_value_columns em data_loader.py
    
    return df_ocor, df_env, df_comm


def _merge_communications_envolvidos(
    df_comm: pd.DataFrame,
    df_env: pd.DataFrame
) -> Optional[pd.DataFrame]:
    """
    Realiza merge entre comunicações e envolvidos.
    """
    comm_cols = [
        'Indexador', 'idComunicacao', 'Data_da_operacao', 'CodigoSegmento',
        'ValorTotal', 'ValorCampoA', 'ValorCampoB', 'ValorCampoC', 
        'ValorCampoD', 'ValorCampoE'
    ]
    
    # Adiciona colunas opcionais
    optional_cols = [
        'informacoesAdicionais', 'CidadeAgencia', 'NumeroAgencia', 
        'UFAgencia', 'nomeComunicante', 'cpfCnpjComunicante'
    ]
    for col in optional_cols:
        if col in df_comm.columns:
            comm_cols.append(col)
    
    comm_cols = [col for col in comm_cols if col in df_comm.columns]
    
    env_cols = [
        'Indexador', 'cpfCnpjEnvolvido', 'nomeEnvolvido', 'tipoEnvolvido',
        'bitPepCitado', 'bitPessoaObrigadaCitado', 'intServidorCitado',
        'DataAberturaConta'
    ]
    env_cols = [col for col in env_cols if col in df_env.columns]
    
    return safe_merge(
        df_comm[comm_cols],
        df_env[env_cols],
        'Indexador', 'Indexador',
        how='left',
        suffixes=('_comm', '_env')
    )


def _merge_with_ocorrencias(
    df_merged: pd.DataFrame,
    df_ocor: pd.DataFrame
) -> Optional[pd.DataFrame]:
    """
    Realiza merge com ocorrências.
    """
    ocor_cols = ['Indexador', 'idOcorrencia', 'Ocorrencia']
    ocor_cols = [col for col in ocor_cols if col in df_ocor.columns]
    
    return safe_merge(
        df_merged,
        df_ocor[ocor_cols],
        'Indexador', 'Indexador',
        how='left',
        suffixes=('', '_ocor')
    )


def _postprocess_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica pós-processamento ao DataFrame consolidado.
    """
    df_final = df.copy()
    
    # Renomeia Indexador
    if 'Indexador_comm' in df_final.columns:
        df_final.rename(columns={'Indexador_comm': 'Indexador_x'}, inplace=True)
    elif 'Indexador_x' not in df_final.columns and 'Indexador' in df_final.columns:
        df_final.rename(columns={'Indexador': 'Indexador_x'}, inplace=True)
    
    # Garante existência do Indexador_x
    if 'Indexador_x' not in df_final.columns:
        st.error("Coluna 'Indexador_x' não pôde ser criada.")
        return df_final
    
    # Converte flags booleanas
    bool_flags = ['bitPepCitado', 'bitPessoaObrigadaCitado', 'intServidorCitado']
    for flag in bool_flags:
        if flag in df_final.columns:
            df_final[flag] = (
                df_final[flag]
                .apply(lambda x: True if str(x).strip().lower() == 'sim' else False)
                .fillna(False)
                .astype(bool)
            )
        else:
            df_final[flag] = False
    
    # Normaliza nomes e preenche NaNs
    df_final['nomeEnvolvido'] = (
        df_final['nomeEnvolvido']
        .fillna('DESCONHECIDO')
        .apply(normalize_string)
    )
    df_final['cpfCnpjEnvolvido'] = (
        df_final['cpfCnpjEnvolvido']
        .fillna('DESCONHECIDO')
        .astype(str)
        .str.strip()
    )
    
    # Extrai Ano e Mês
    df_final = _extract_year_month(df_final)
    
    # Adiciona descrição dos segmentos
    df_final = _add_segment_descriptions(df_final)
    
    # Reconverte colunas de data
    if 'Data_da_operacao' in df_final.columns:
        df_final['Data_da_operacao'] = pd.to_datetime(
            df_final['Data_da_operacao'], errors='coerce'
        )
    if 'DataAberturaConta' in df_final.columns:
        df_final['DataAberturaConta'] = pd.to_datetime(
            df_final['DataAberturaConta'], errors='coerce'
        )
    
    # Adiciona coluna de tipo de envolvido normalizado
    if 'tipoEnvolvido' in df_final.columns:
        df_final['tipoEnvolvido_Norm'] = (
            df_final['tipoEnvolvido']
            .apply(normalize_string)
        )
    else:
        df_final['tipoEnvolvido_Norm'] = "DESCONHECIDO"
    
    return df_final


def _extract_year_month(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extrai colunas de Ano e Mês da data da operação.
    """
    df_result = df.copy()
    
    if 'Data_da_operacao' in df_result.columns:
        if pd.api.types.is_datetime64_any_dtype(df_result['Data_da_operacao']):
            mask_notna = df_result['Data_da_operacao'].notna()
            
            df_result.loc[mask_notna, 'Ano'] = (
                df_result.loc[mask_notna, 'Data_da_operacao'].dt.year
            )
            df_result.loc[mask_notna, 'Mes'] = (
                df_result.loc[mask_notna, 'Data_da_operacao'].dt.month
            )
            
            df_result['Ano'] = df_result['Ano'].fillna(0).astype(int)
            df_result['Mes'] = df_result['Mes'].fillna(0).astype(int)
        else:
            df_result['Ano'] = 0
            df_result['Mes'] = 0
    else:
        df_result['Ano'] = 0
        df_result['Mes'] = 0
    
    return df_result


def _add_segment_descriptions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adiciona descrições dos campos por segmento.
    """
    df_result = df.copy()
    
    # Cria DataFrame de descrições
    df_segmento_desc = pd.DataFrame(
        list(SEGMENTO_MAP.items()),
        columns=['CodigoSegmento', 'DescricaoCampos']
    )
    df_segmento_desc['CodigoSegmento'] = df_segmento_desc['CodigoSegmento'].astype(str)
    
    if 'CodigoSegmento' in df_result.columns:
        df_result['CodigoSegmento'] = df_result['CodigoSegmento'].astype(str).str.strip()
        df_result = pd.merge(
            df_result, df_segmento_desc,
            on='CodigoSegmento', how='left'
        )
        df_result['DescricaoCampos'] = df_result['DescricaoCampos'].fillna(
            'Segmento não mapeado'
        )
    else:
        df_result['DescricaoCampos'] = 'Segmento não disponível'
    
    return df_result


def filter_dataframe(
    df: pd.DataFrame,
    date_range: tuple = None,
    year: int = None,
    month: int = None,
    ocorrencia: str = None
) -> pd.DataFrame:
    """
    Aplica filtros ao DataFrame.
    
    Args:
        df: DataFrame a filtrar
        date_range: Tupla com (data_inicio, data_fim)
        year: Ano para filtro
        month: Mês para filtro
        ocorrencia: Tipo de ocorrência para filtro
        
    Returns:
        DataFrame filtrado
    """
    df_filtered = df.copy()
    
    # Filtro de data
    if date_range and len(date_range) == 2:
        start_date, end_date = date_range
        if 'Data_da_operacao' in df_filtered.columns:
            df_filtered = df_filtered[
                df_filtered['Data_da_operacao'].notna() &
                (df_filtered['Data_da_operacao'].dt.date >= start_date) &
                (df_filtered['Data_da_operacao'].dt.date <= end_date)
            ]
    
    # Filtro de ano
    if year and year != "Todos":
        if 'Ano' in df_filtered.columns:
            df_filtered = df_filtered[df_filtered['Ano'] == year]
    
    # Filtro de mês
    if month and month != "Todos":
        if 'Mes' in df_filtered.columns:
            df_filtered = df_filtered[df_filtered['Mes'] == month]
    
    # Filtro de ocorrência
    if ocorrencia and ocorrencia != 'Todas':
        if 'Ocorrencia' in df_filtered.columns:
            if ocorrencia == 'N/A':
                df_filtered = df_filtered[df_filtered['Ocorrencia'].isna()]
            else:
                df_filtered = df_filtered[df_filtered['Ocorrencia'] == ocorrencia]
    
    return df_filtered
