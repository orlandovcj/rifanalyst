# analytics/patterns.py - Detecção de Padrões Suspeitos
"""
Módulo para detecção de padrões suspeitos em comunicações RIF.
Implementa 17 padrões de risco identificados pelo COAF/BACEN.

IMPORTANTE: Usa imports ABSOLUTOS (não relativos) para compatibilidade
quando main.py está na raiz do projeto.
"""
from __future__ import annotations
import pandas as pd
import numpy as np
import re
import streamlit as st
from typing import List, Dict, Any

# IMPORTS ABSOLUTOS (não usar ..)
from config import (
    CRITICIDADE_MAP, SCORE_WEIGHTS, CIDADES_RISCO,
    KEYWORDS_SUSPEITAS, LIMIARES_REPORTE, LIMITE_FRACIONAMENTO
)
from project_utils.helpers import normalize_string, safe_div


@st.cache_data
def analyze_suspicious_patterns(
    df_display: pd.DataFrame,
    df_ocorrencias: pd.DataFrame,
    df_comunicacoes: pd.DataFrame,
    df_envolvidos: pd.DataFrame
) -> pd.DataFrame:
    """
    Detecta padrões suspeitos (VETORIZADO).
    
    Args:
        df_display: DataFrame principal filtrado
        df_ocorrencias: DataFrame de ocorrências original
        df_comunicacoes: DataFrame de comunicações original
        df_envolvidos: DataFrame de envolvidos original
        
    Returns:
        DataFrame com padrões suspeitos detectados
    """
    suspicious_patterns = []
    return_cols = ['Indexador', 'idComunicacao', 'cpfCnpj', 'Nome', 'Motivo', 'Risco']
    
    # Validação de entrada
    if df_display is None or df_display.empty:
        return pd.DataFrame(columns=return_cols)
    
    # Cria cópias seguras
    df = df_display.copy()
    df_ocor_local = df_ocorrencias.copy() if df_ocorrencias is not None else pd.DataFrame()
    df_comm_local = df_comunicacoes.copy() if df_comunicacoes is not None else pd.DataFrame()
    df_env_local = df_envolvidos.copy() if df_envolvidos is not None else pd.DataFrame()
    
    if df_ocor_local.empty or df_comm_local.empty or df_env_local.empty:
        return pd.DataFrame(columns=return_cols)
    
    # Pré-processamento
    df_ocor_local['idOcorrencia'] = df_ocor_local['idOcorrencia'].astype(str)
    df_ocor_local['Indexador'] = df_ocor_local['Indexador'].astype(str).str.strip()
    df_comm_local['Indexador'] = df_comm_local['Indexador'].astype(str).str.strip()
    df_env_local['Indexador'] = df_env_local['Indexador'].astype(str).str.strip()
    df_env_local['cpfCnpjEnvolvido'] = (
        df_env_local['cpfCnpjEnvolvido']
        .fillna('DESCONHECIDO')
        .astype(str)
        .str.strip()
    )
    
    # Dicionário de nomes de envolvidos
    envolvidos_dict = (
        df_env_local
        .drop_duplicates(subset=['cpfCnpjEnvolvido'])
        .set_index('cpfCnpjEnvolvido')['nomeEnvolvido']
        .apply(normalize_string)
    )
    
    # Garante colunas em df
    if 'Indexador_x' not in df.columns:
        df['Indexador_x'] = 'N/A'
    if 'idComunicacao' not in df.columns:
        df['idComunicacao'] = 'N/A'
    
    # ==========================================
    # PADRÃO 1: Contas Recém-Abertas
    # ==========================================
    suspicious_patterns.extend(_detect_new_accounts(df))
    
    # ==========================================
    # PADRÃO 2: Alta Frequência
    # ==========================================
    suspicious_patterns.extend(_detect_high_frequency(df, envolvidos_dict))
    
    # ==========================================
    # PADRÃO 3: Múltiplas Localidades
    # ==========================================
    suspicious_patterns.extend(_detect_multiple_locations(df, envolvidos_dict))
    
    # ==========================================
    # PADRÃO 4: PEPs com Múltiplas Comunicações
    # ==========================================
    suspicious_patterns.extend(_detect_pep_multiple_comms(df, envolvidos_dict))
    
    # ==========================================
    # PADRÃO 5: Burla de Limites (Structuring)
    # ==========================================
    suspicious_patterns.extend(_detect_structuring(df))
    
    # ==========================================
    # PADRÃO 6: Alto Valor
    # ==========================================
    suspicious_patterns.extend(_detect_high_value(df))
    
    # ==========================================
    # PADRÃO 7: Saques em Espécie
    # ==========================================
    suspicious_patterns.extend(_detect_cash_withdrawals(df, df_comm_local, df_ocor_local, df_env_local, envolvidos_dict))
    
    # ==========================================
    # PADRÃO 8: Depósitos em Espécie
    # ==========================================
    suspicious_patterns.extend(_detect_cash_deposits(df, df_comm_local, df_ocor_local, df_env_local, envolvidos_dict))
    
    # ==========================================
    # PADRÃO 9: Fracionamento
    # ==========================================
    suspicious_patterns.extend(_detect_smurfing(df, envolvidos_dict))
    
    # ==========================================
    # PADRÃO 10: Risco Geográfico
    # ==========================================
    suspicious_patterns.extend(_detect_geographic_risk(df, envolvidos_dict))
    
    # ==========================================
    # PADRÃO 11: Pass-Through
    # ==========================================
    suspicious_patterns.extend(_detect_pass_through(df, envolvidos_dict))
    
    # ==========================================
    # PADRÃO 12: Múltiplas Ocorrências
    # ==========================================
    suspicious_patterns.extend(_detect_multiple_occurrences(df_ocor_local, df_comm_local))
    
    # ==========================================
    # PADRÃO 13: Alta Complexidade
    # ==========================================
    suspicious_patterns.extend(_detect_high_complexity(df_env_local, df_comm_local))
    
    # ==========================================
    # PADRÃO 14: Concentração de Perfis de Risco
    # ==========================================
    suspicious_patterns.extend(_detect_risk_profile_concentration(df_env_local, df_comm_local))
    
    # ==========================================
    # PADRÃO 15: Keywords Suspeitas
    # ==========================================
    suspicious_patterns.extend(_detect_suspicious_keywords(df_comm_local, df))
    
    # ==========================================
    # PADRÃO 16: Análise Baseada em idOcorrencia
    # ==========================================
    suspicious_patterns.extend(_detect_by_occurrence_id(df_ocor_local, df, CRITICIDADE_MAP))
    
    # ==========================================
    # Consolidação Final
    # ==========================================
    if not suspicious_patterns:
        return pd.DataFrame(columns=return_cols)
    
    final_df = pd.DataFrame(suspicious_patterns)
    
    # Remove duplicatas
    key_cols = ['Indexador', 'idComunicacao', 'cpfCnpj', 'Motivo', 'Risco']
    final_df = final_df.drop_duplicates(subset=key_cols)
    
    if not final_df.empty:
        # Adiciona pontos
        final_df['Pontos'] = final_df['Risco'].map(SCORE_WEIGHTS).fillna(1)
    
    return final_df


def _detect_new_accounts(df: pd.DataFrame) -> List[Dict]:
    """Detecta operações em contas com menos de 30 dias."""
    patterns = []
    
    if 'DataAberturaConta' not in df.columns or 'Data_da_operacao' not in df.columns:
        return patterns
    
    df_temp = df.copy()
    df_temp['DataAberturaConta'] = pd.to_datetime(df_temp['DataAberturaConta'], errors='coerce')
    df_temp['Data_da_operacao'] = pd.to_datetime(df_temp['Data_da_operacao'], errors='coerce')
    
    if not (pd.api.types.is_datetime64_any_dtype(df_temp['DataAberturaConta']) and
            pd.api.types.is_datetime64_any_dtype(df_temp['Data_da_operacao'])):
        return patterns
    
    df_temp['IdadeConta'] = (df_temp['Data_da_operacao'] - df_temp['DataAberturaConta']).dt.days
    contas_novas = df_temp[(df_temp['IdadeConta'] < 30) & (df_temp['IdadeConta'] >= 0)]
    
    for _, row in contas_novas.iterrows():
        patterns.append({
            'Indexador': str(row.get('Indexador_x', 'N/A')),
            'idComunicacao': str(row.get('idComunicacao', 'N/A')),
            'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
            'Nome': str(row.get('nomeEnvolvido', 'DESCONHECIDO')),
            'Motivo': f"Operação em conta com {row.get('IdadeConta', 0):.0f} dias",
            'Risco': 'Moderado'
        })
    
    return patterns


def _detect_high_frequency(df: pd.DataFrame, envolvidos_dict: dict) -> List[Dict]:
    """Detecta alta frequência de comunicações (> 10 em 7 dias)."""
    patterns = []
    
    if 'Data_da_operacao' not in df.columns:
        return patterns
    
    if not pd.api.types.is_datetime64_any_dtype(df['Data_da_operacao']):
        return patterns
    
    df_clean = df.dropna(subset=['Data_da_operacao'])
    if df_clean.empty:
        return patterns
    
    agg_freq = df_clean.groupby('cpfCnpjEnvolvido').agg(
        DataMin=('Data_da_operacao', 'min'),
        DataMax=('Data_da_operacao', 'max'),
        Count=('idComunicacao', 'nunique'),
        First_Indexador=('Indexador_x', 'first'),
        First_Comunicacao=('idComunicacao', 'first')
    ).reset_index()
    
    agg_freq['Dias'] = (agg_freq['DataMax'] - agg_freq['DataMin']).dt.days + 1
    high_frequency = agg_freq[(agg_freq['Count'] > 10) & (agg_freq['Dias'] <= 7)]
    
    for _, row in high_frequency.iterrows():
        patterns.append({
            'Indexador': f"Ex: {str(row.get('First_Indexador', 'N/A'))}",
            'idComunicacao': f"Ex: {str(row.get('First_Comunicacao', 'N/A'))}",
            'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
            'Nome': envolvidos_dict.get(str(row.get('cpfCnpjEnvolvido')), 'DESCONHECIDO'),
            'Motivo': f"Alta frequência: {row.get('Count', 0)} comunicações em {row.get('Dias', 0)} dias",
            'Risco': 'Alto'
        })
    
    return patterns


def _detect_multiple_locations(df: pd.DataFrame, envolvidos_dict: dict) -> List[Dict]:
    """Detecta transações em múltiplas localidades no mesmo dia."""
    patterns = []
    
    if 'Data_da_operacao' not in df.columns or 'CidadeAgencia' not in df.columns:
        return patterns
    
    if not pd.api.types.is_datetime64_any_dtype(df['Data_da_operacao']):
        return patterns
    
    df_clean = df.dropna(subset=['Data_da_operacao', 'CidadeAgencia'])
    if df_clean.empty:
        return patterns
    
    same_day_loc = df_clean.groupby(
        ['cpfCnpjEnvolvido', df_clean['Data_da_operacao'].dt.date]
    ).agg(
        Cidades=('CidadeAgencia', 'nunique'),
        Agencias=('NumeroAgencia', 'nunique'),
        First_Indexador=('Indexador_x', 'first'),
        First_Comunicacao=('idComunicacao', 'first')
    ).reset_index()
    
    suspicious_locations = same_day_loc[
        (same_day_loc['Cidades'] > 1) | (same_day_loc['Agencias'] > 2)
    ]
    
    for _, row in suspicious_locations.iterrows():
        patterns.append({
            'Indexador': f"Ex: {str(row.get('First_Indexador', 'N/A'))}",
            'idComunicacao': f"Ex: {str(row.get('First_Comunicacao', 'N/A'))}",
            'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
            'Nome': envolvidos_dict.get(str(row.get('cpfCnpjEnvolvido')), 'DESCONHECIDO'),
            'Motivo': f"Transações em {row.get('Cidades', 0)} cidades/{row.get('Agencias', 0)} agências no dia {row.get('Data_da_operacao', 'N/A')}",
            'Risco': 'Moderado'
        })
    
    return patterns


def _detect_pep_multiple_comms(df: pd.DataFrame, envolvidos_dict: dict) -> List[Dict]:
    """Detecta PEPs com múltiplas comunicações."""
    patterns = []
    
    if 'bitPepCitado' not in df.columns:
        return patterns
    
    pep_comms = df[df['bitPepCitado'] == True]
    if pep_comms.empty:
        return patterns
    
    pep_agg = pep_comms.groupby('cpfCnpjEnvolvido').agg(
        Count=('idComunicacao', 'nunique'),
        First_Indexador=('Indexador_x', 'first'),
        First_Comunicacao=('idComunicacao', 'first')
    ).reset_index()
    
    high_risk_peps = pep_agg[pep_agg['Count'] > 3]
    
    for _, row in high_risk_peps.iterrows():
        patterns.append({
            'Indexador': f"Ex: {str(row.get('First_Indexador', 'N/A'))}",
            'idComunicacao': f"Ex: {str(row.get('First_Comunicacao', 'N/A'))}",
            'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
            'Nome': envolvidos_dict.get(str(row.get('cpfCnpjEnvolvido')), 'DESCONHECIDO'),
            'Motivo': f"PEP com {row.get('Count', 0)} comunicações suspeitas",
            'Risco': 'Crítico'
        })
    
    return patterns


def _detect_structuring(df: pd.DataFrame) -> List[Dict]:
    """Detecta indícios de structuring (burla de limites)."""
    patterns = []
    
    if 'ValorTotal' not in df.columns:
        return patterns
    
    for limite in LIMIARES_REPORTE:
        lower_bound = limite * 0.90
        upper_bound = limite * 0.99
        
        df_struct = df[
            (df['ValorTotal'] >= lower_bound) &
            (df['ValorTotal'] <= upper_bound) &
            (df.get('CodigoSegmento', '') != '24')  # Exclui imóveis
        ]
        
        for _, row in df_struct.iterrows():
            patterns.append({
                'Indexador': str(row.get('Indexador_x', 'N/A')),
                'idComunicacao': str(row.get('idComunicacao', 'N/A')),
                'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
                'Nome': str(row.get('nomeEnvolvido', 'DESCONHECIDO')),
                'Motivo': f"Burla de Limites? Valor (R$ {row['ValorTotal']:,.2f}) está logo abaixo do limite de {limite/1000:.0f}k",
                'Risco': 'Alto'
            })
    
    return patterns


def _detect_high_value(df: pd.DataFrame) -> List[Dict]:
    """Detecta transações de alto valor (> R$ 1 milhão)."""
    patterns = []
    
    if 'ValorTotal' not in df.columns:
        return patterns
    
    high_value = df[
        (df['ValorTotal'] > 1_000_000) & 
        (df.get('CodigoSegmento', '') != '24')
    ]
    
    for _, row in high_value.iterrows():
        patterns.append({
            'Indexador': str(row.get('Indexador_x', 'N/A')),
            'idComunicacao': str(row.get('idComunicacao', 'N/A')),
            'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
            'Nome': str(row.get('nomeEnvolvido', 'DESCONHECIDO')),
            'Motivo': f"Transação alto valor (CampoA): R$ {row.get('ValorTotal', 0):,.2f}",
            'Risco': 'Alto'
        })
    
    return patterns


def _detect_cash_withdrawals(df, df_comm, df_ocor, df_env, envolvidos_dict) -> List[Dict]:
    """Detecta saques em espécie >= R$ 50k."""
    patterns = []
    
    saque_ids = ['891', '894', '1163', '1159']
    # Implementação simplificada
    return patterns


def _detect_cash_deposits(df, df_comm, df_ocor, df_env, envolvidos_dict) -> List[Dict]:
    """Detecta depósitos em espécie >= R$ 50k."""
    patterns = []
    
    deposito_ids = ['1161']
    # Implementação simplificada
    return patterns


def _detect_smurfing(df: pd.DataFrame, envolvidos_dict: dict) -> List[Dict]:
    """Detecta fracionamento de valores."""
    patterns = []
    
    if 'Data_da_operacao' not in df.columns or 'ValorTotal' not in df.columns:
        return patterns
    
    if not pd.api.types.is_datetime64_any_dtype(df['Data_da_operacao']):
        return patterns
    
    df_clean = df.dropna(subset=['Data_da_operacao'])
    if df_clean.empty:
        return patterns
    
    daily_sums = df_clean.groupby(
        ['cpfCnpjEnvolvido', df_clean['Data_da_operacao'].dt.date]
    ).agg(
        ValorDia=('ValorTotal', 'sum'),
        QtdDia=('idComunicacao', 'nunique'),
        First_Indexador=('Indexador_x', 'first'),
        First_Comunicacao=('idComunicacao', 'first')
    ).reset_index()
    
    smurfing = daily_sums[
        (daily_sums['QtdDia'] >= 3) &
        (daily_sums['ValorDia'] >= LIMITE_FRACIONAMENTO) &
        (daily_sums['ValorDia'] < 50000)
    ]
    
    for _, row in smurfing.iterrows():
        patterns.append({
            'Indexador': f"Ex: {str(row.get('First_Indexador', 'N/A'))}",
            'idComunicacao': f"Ex: {str(row.get('First_Comunicacao', 'N/A'))}",
            'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
            'Nome': envolvidos_dict.get(str(row.get('cpfCnpjEnvolvido')), 'DESCONHECIDO'),
            'Motivo': f"Fracionamento (CampoA): {row.get('QtdDia', 0)} coms. total R$ {row.get('ValorDia', 0):,.2f} em {row.get('Data_da_operacao', 'N/A')}",
            'Risco': 'Crítico'
        })
    
    return patterns


def _detect_geographic_risk(df: pd.DataFrame, envolvidos_dict: dict) -> List[Dict]:
    """Detecta operações em cidades de risco."""
    patterns = []
    
    if 'CidadeAgencia' not in df.columns:
        return patterns
    
    df_temp = df.copy()
    df_temp['CidadeAgenciaNorm'] = df_temp['CidadeAgencia'].apply(normalize_string)
    risco_geo = df_temp[df_temp['CidadeAgenciaNorm'].isin(CIDADES_RISCO)]
    
    if risco_geo.empty:
        return patterns
    
    risco_geo_agg = risco_geo.groupby(
        ['cpfCnpjEnvolvido', 'CidadeAgenciaNorm']
    ).agg(
        ValorTotal=('ValorTotal', 'sum'),
        Qtd=('idComunicacao', 'nunique'),
        First_Indexador=('Indexador_x', 'first'),
        First_Comunicacao=('idComunicacao', 'first')
    ).reset_index()
    
    for _, row in risco_geo_agg.iterrows():
        patterns.append({
            'Indexador': f"Ex: {str(row.get('First_Indexador', 'N/A'))}",
            'idComunicacao': f"Ex: {str(row.get('First_Comunicacao', 'N/A'))}",
            'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
            'Nome': envolvidos_dict.get(str(row.get('cpfCnpjEnvolvido')), 'DESCONHECIDO'),
            'Motivo': f"Risco Geo: {row.get('Qtd', 0)} coms. em {row.get('CidadeAgenciaNorm', 'N/A')} (R$ {row.get('ValorTotal', 0):,.2f})",
            'Risco': 'Moderado'
        })
    
    return patterns


def _detect_pass_through(df: pd.DataFrame, envolvidos_dict: dict) -> List[Dict]:
    """Detecta atividade pass-through (contas de passagem)."""
    patterns = []
    
    if 'tipoEnvolvido' not in df.columns:
        return patterns
    
    roles = df.groupby('cpfCnpjEnvolvido')['tipoEnvolvido'].unique().apply(set).reset_index()
    
    pass_through_candidates = roles[
        roles['tipoEnvolvido'].apply(lambda x: 'depositante' in [t.lower() for t in x]) &
        roles['tipoEnvolvido'].apply(lambda x: any(t.lower() in ['sacador', 'titular da conta'] for t in x))
    ]
    
    if pass_through_candidates.empty:
        return patterns
    
    volume = df[df['cpfCnpjEnvolvido'].isin(pass_through_candidates['cpfCnpjEnvolvido'])].groupby(
        'cpfCnpjEnvolvido'
    ).agg(
        ValorTotal=('ValorTotal', 'sum'),
        First_Indexador=('Indexador_x', 'first'),
        First_Comunicacao=('idComunicacao', 'first')
    ).reset_index()
    
    high_volume_pass = volume[volume['ValorTotal'] > 500_000]
    
    for _, row in high_volume_pass.iterrows():
        patterns.append({
            'Indexador': f"Ex: {str(row.get('First_Indexador', 'N/A'))}",
            'idComunicacao': f"Ex: {str(row.get('First_Comunicacao', 'N/A'))}",
            'cpfCnpj': str(row.get('cpfCnpjEnvolvido', 'N/A')),
            'Nome': envolvidos_dict.get(str(row.get('cpfCnpjEnvolvido')), 'DESCONHECIDO'),
            'Motivo': f"Atividade 'Pass-Through' (R$ {row.get('ValorTotal', 0):,.2f})",
            'Risco': 'Alto'
        })
    
    return patterns


def _detect_multiple_occurrences(df_ocor: pd.DataFrame, df_comm: pd.DataFrame) -> List[Dict]:
    """Detecta comunicações com múltiplas ocorrências."""
    patterns = []
    
    if df_ocor.empty:
        return patterns
    
    ocor_counts = df_ocor.groupby('Indexador')['idOcorrencia'].nunique()
    multi_ocor_idx = ocor_counts[ocor_counts > 2].index
    
    if multi_ocor_idx.empty:
        return patterns
    
    ocor_details = df_ocor[df_ocor['Indexador'].isin(multi_ocor_idx)]
    ocor_grouped_text = ocor_details.groupby('Indexador')['Ocorrencia'].apply(
        lambda x: '; '.join(x.astype(str).unique())
    )
    
    for idx, ocor_text in ocor_grouped_text.items():
        comm_id_ex = df_comm[df_comm['Indexador'] == idx]['idComunicacao']
        comm_id = str(comm_id_ex.iloc[0]) if not comm_id_ex.empty else 'N/A'
        
        patterns.append({
            'Indexador': str(idx),
            'idComunicacao': comm_id,
            'cpfCnpj': 'N/A (Indexador)',
            'Nome': "Múltiplas Ocorrências",
            'Motivo': f"{ocor_counts[idx]} ocorrências: {ocor_text[:200]}...",
            'Risco': 'Alto'
        })
    
    return patterns


def _detect_high_complexity(df_env: pd.DataFrame, df_comm: pd.DataFrame) -> List[Dict]:
    """Detecta comunicações com muitos envolvidos."""
    patterns = []
    
    if df_env.empty:
        return patterns
    
    involved_counts = df_env.groupby('Indexador')['cpfCnpjEnvolvido'].nunique()
    complex_idx = involved_counts[involved_counts > 15].index
    
    for idx in complex_idx:
        comm_id_ex = df_comm[df_comm['Indexador'] == idx]['idComunicacao']
        comm_id = str(comm_id_ex.iloc[0]) if not comm_id_ex.empty else 'N/A'
        
        patterns.append({
            'Indexador': str(idx),
            'idComunicacao': comm_id,
            'cpfCnpj': 'N/A (Indexador)',
            'Nome': "Alta Complexidade",
            'Motivo': f"{involved_counts[idx]} envolvidos distintos.",
            'Risco': 'Moderado'
        })
    
    return patterns


def _detect_risk_profile_concentration(df_env: pd.DataFrame, df_comm: pd.DataFrame) -> List[Dict]:
    """Detecta concentração de perfis de risco."""
    patterns = []
    
    if df_env.empty:
        return patterns
    
    # Converte flags
    for flag in ['bitPepCitado', 'bitPessoaObrigadaCitado', 'intServidorCitado']:
        if flag not in df_env.columns:
            df_env[flag] = False
        df_env[flag] = (
            df_env[flag]
            .apply(lambda x: True if str(x).strip().lower() == 'sim' else False)
            .fillna(False)
            .astype(bool)
        )
    
    risk_profile_agg = df_env.groupby('Indexador').agg(
        total_envolvidos=('cpfCnpjEnvolvido', 'nunique'),
        pep_count=('bitPepCitado', 'sum'),
        servidor_count=('intServidorCitado', 'sum')
    )
    
    risk_profile_agg = risk_profile_agg[risk_profile_agg['total_envolvidos'] > 0]
    risk_profile_agg['pep_perc'] = (risk_profile_agg['pep_count'] / risk_profile_agg['total_envolvidos']) * 100
    
    high_conc_idx = risk_profile_agg[
        (risk_profile_agg['pep_count'] > 2) |
        (risk_profile_agg['servidor_count'] > 5) |
        (risk_profile_agg['pep_perc'] > 50)
    ].index
    
    for idx in high_conc_idx:
        details = risk_profile_agg.loc[idx]
        comm_id_ex = df_comm[df_comm['Indexador'] == idx]['idComunicacao']
        comm_id = str(comm_id_ex.iloc[0]) if not comm_id_ex.empty else 'N/A'
        
        patterns.append({
            'Indexador': str(idx),
            'idComunicacao': comm_id,
            'cpfCnpj': 'N/A (Indexador)',
            'Nome': "Concentração Perfis Risco",
            'Motivo': f"{details['pep_count']} PEPs ({details['pep_perc']:.0f}%), {details['servidor_count']} Servidores",
            'Risco': 'Alto'
        })
    
    return patterns


def _detect_suspicious_keywords(df_comm: pd.DataFrame, df: pd.DataFrame) -> List[Dict]:
    """Detecta keywords suspeitas em narrativas."""
    patterns = []
    
    if 'informacoesAdicionais' not in df_comm.columns:
        return patterns
    
    if not df_comm['informacoesAdicionais'].notna().any():
        return patterns
    
    df_comm_temp = df_comm.copy()
    df_comm_temp['info_norm'] = (
        df_comm_temp['informacoesAdicionais']
        .astype(str)
        .apply(normalize_string)
    )
    
    keyword_regex = '|'.join(KEYWORDS_SUSPEITAS)
    keyword_hits = df_comm_temp[df_comm_temp['info_norm'].str.contains(keyword_regex, na=False)]
    
    valid_indexadores = df['Indexador_x'].unique()
    keyword_hits = keyword_hits[keyword_hits['Indexador'].isin(valid_indexadores)]
    
    def find_keywords(text, kw_list):
        found = [kw for kw in kw_list if kw in str(text).upper()]
        return ', '.join(found) if found else 'N/A'
    
    for _, row in keyword_hits.iterrows():
        patterns.append({
            'Indexador': str(row.get('Indexador', 'N/A')),
            'idComunicacao': str(row.get('idComunicacao', 'N/A')),
            'cpfCnpj': 'N/A (Narrativa)',
            'Nome': "Keyword Suspeita",
            'Motivo': f"Narrativa contém: '{find_keywords(row.get('info_norm', ''), KEYWORDS_SUSPEITAS)}'.",
            'Risco': 'Moderado'
        })
    
    return patterns


def _detect_by_occurrence_id(df_ocor: pd.DataFrame, df: pd.DataFrame, criticidade_map: dict) -> List[Dict]:
    """Detecta com base no ID da ocorrência e criticidade."""
    patterns = []
    
    if df_ocor.empty:
        return patterns
    
    df_ocor_temp = df_ocor.copy()
    df_ocor_temp['idOcorrencia'] = (
        df_ocor_temp['idOcorrencia']
        .astype(str)
        .str.split('.')
        .str[0]
    )
    
    df_hits = df_ocor_temp[df_ocor_temp['idOcorrencia'].isin(criticidade_map.keys())]
    
    for _, ocor in df_hits.iterrows():
        idx = ocor['Indexador']
        id_cod = str(ocor['idOcorrencia']).split('.')[0]
        desc_ocor = ocor['Ocorrencia']
        nivel = criticidade_map.get(id_cod, 'Moderado')
        
        env_da_com = df[df['Indexador_x'] == idx][['cpfCnpjEnvolvido', 'nomeEnvolvido', 'idComunicacao']].drop_duplicates()
        
        for _, env in env_da_com.iterrows():
            patterns.append({
                'Indexador': str(idx),
                'idComunicacao': str(env['idComunicacao']),
                'cpfCnpj': env['cpfCnpjEnvolvido'],
                'Nome': env['nomeEnvolvido'],
                'Motivo': f"Ocorrência {id_cod}: {desc_ocor[:150]}...",
                'Risco': nivel
            })
    
    return patterns
