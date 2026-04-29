# integrations/portal_transparencia.py - Integração Portal da Transparência
"""
Módulo para integração com a API do Portal da Transparência.

IMPORTANTE: Usa imports ABSOLUTOS (não relativos) para compatibilidade
quando main.py está na raiz do projeto.
"""
from __future__ import annotations
import os
import pandas as pd
import streamlit as st
import requests
from typing import Optional
from datetime import datetime

# IMPORT ABSOLUTO (não usar ..)
from project_utils.security import get_secret


def fetch_portal_transparencia_data(
    cpf_cnpj: str,
    data_inicio: datetime,
    data_fim: datetime = None
) -> pd.DataFrame:
    """
    Consulta pagamentos no Portal da Transparência.
    
    Args:
        cpf_cnpj: CPF ou CNPJ para consulta
        data_inicio: Data inicial (usado para extrair ano)
        data_fim: Data final (não usado atualmente pela API)
        
    Returns:
        DataFrame com resultados ou DataFrame vazio se erro
    """
    # 1. Limpeza rigorosa do ID (apenas números)
    id_limpo = ''.join(filter(str.isdigit, str(cpf_cnpj)))
    
    if not id_limpo:
        return pd.DataFrame()
    
    # 2. URL da API
    url = "https://api.portaldatransparencia.gov.br/api-de-dados/despesas/documentos-por-favorecido"
    
    # 3. Token de autenticação (NUNCA hardcodar!)
    token = get_secret("portal_transparencia_token")
    if not token:
        # Fallback para variável de ambiente
        token = os.environ.get("PORTAL_TRANSPARENCIA_TOKEN", "")
    
    if not token:
        st.warning("Token do Portal da Transparência não configurado.")
        return pd.DataFrame()
    
    headers = {
        "accept": "*/*",
        "chave-api-dados": token.strip()
    }
    
    # 4. Parâmetros da requisição
    params = {
        "codigoPessoa": id_limpo,
        "fase": "3",  # Fase de Pagamento
        "ano": str(data_inicio.year) if data_inicio else str(datetime.now().year),
        "pagina": "1"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        
        if response.status_code == 200:
            dados_brutos = response.json()
            
            # Converte para DataFrame
            if isinstance(dados_brutos, list):
                if not dados_brutos:
                    return pd.DataFrame()
                return pd.DataFrame(dados_brutos)
            return pd.DataFrame([dados_brutos])
        
        elif response.status_code == 403:
            st.error("Erro 403: Acesso negado. Verifique o token da API.")
            return pd.DataFrame()
        elif response.status_code == 404:
            # Nenhum registro encontrado
            return pd.DataFrame()
        else:
            st.error(f"API retornou erro {response.status_code}")
            return pd.DataFrame()
            
    except requests.exceptions.Timeout:
        st.error("Timeout na consulta ao Portal da Transparência.")
        return pd.DataFrame()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro na requisição: {str(e)}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro inesperado: {str(e)}")
        return pd.DataFrame()


def limpar_valor_portal(v) -> float:
    """
    Limpa strings de valores do Portal da Transparência (padrão BR).
    Trata espaços, pontos de milhar e sinais de negativo.
    
    Args:
        v: Valor a ser limpo (string, int ou float)
        
    Returns:
        Valor como float
    """
    if pd.isna(v) or v == "" or v == "N/A":
        return 0.0
    
    # Converte para string e remove espaços
    s = str(v).strip().replace(' ', '')
    
    # Inverte separadores: remove ponto de milhar, troca vírgula por ponto decimal
    s = s.replace('.', '').replace(',', '.')
    
    try:
        return float(s)
    except ValueError:
        return 0.0


def processar_dados_portal(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Processa dados brutos do Portal da Transparência para formato padronizado.
    
    Args:
        df_raw: DataFrame com dados brutos da API
        
    Returns:
        DataFrame processado
    """
    if df_raw.empty:
        return pd.DataFrame()
    
    df = df_raw.copy()
    
    # Colunas esperadas (podem variar)
    colunas_valor = ['valor', 'Valor', 'valorDocumento', 'valorPagamento']
    colunas_data = ['data', 'dataDocumento', 'dataPagamento']
    colunas_favorecido = ['nomeFavorecido', 'nome', 'favorecido']
    colunas_orgao = ['orgao', 'nomeOrgao', 'unidade']
    
    # Identificar colunas disponíveis
    valor_col = next((c for c in colunas_valor if c in df.columns), None)
    data_col = next((c for c in colunas_data if c in df.columns), None)
    favorecido_col = next((c for c in colunas_favorecido if c in df.columns), None)
    orgao_col = next((c for c in colunas_orgao if c in df.columns), None)
    
    # Processar valor
    if valor_col:
        df['valor_limpo'] = df[valor_col].apply(limpar_valor_portal)
    else:
        df['valor_limpo'] = 0.0
    
    # Processar data
    if data_col:
        df['data_documento'] = pd.to_datetime(df[data_col], errors='coerce')
    else:
        df['data_documento'] = pd.NaT
    
    # Renomear colunas
    rename_map = {}
    if favorecido_col:
        rename_map[favorecido_col] = 'nome_favorecido'
    if orgao_col:
        rename_map[orgao_col] = 'nome_orgao'
    
    df = df.rename(columns=rename_map)
    
    return df


def resumir_pagamentos_portal(df: pd.DataFrame) -> dict:
    """
    Gera resumo dos pagamentos encontrados no Portal.
    
    Args:
        df: DataFrame com dados processados
        
    Returns:
        Dicionário com resumo
    """
    if df.empty:
        return {
            'total_pagamentos': 0,
            'valor_total': 0.0,
            'orgaos': [],
            'periodo': None
        }
    
    resumo = {
        'total_pagamentos': len(df),
        'valor_total': df['valor_limpo'].sum() if 'valor_limpo' in df.columns else 0.0,
        'orgaos': df['nome_orgao'].unique().tolist() if 'nome_orgao' in df.columns else [],
    }
    
    if 'data_documento' in df.columns and not df['data_documento'].isna().all():
        resumo['periodo'] = {
            'inicio': df['data_documento'].min(),
            'fim': df['data_documento'].max()
        }
    else:
        resumo['periodo'] = None
    
    return resumo


def verificar_multiplos_anos(
    cpf_cnpj: str,
    anos: list = None,
    ano_atual: int = None
) -> pd.DataFrame:
    """
    Verifica pagamentos em múltiplos anos.
    
    Args:
        cpf_cnpj: CPF/CNPJ para consulta
        anos: Lista de anos a verificar
        ano_atual: Ano atual (para calcular anos anteriores se lista não fornecida)
        
    Returns:
        DataFrame consolidado com todos os anos
    """
    if ano_atual is None:
        ano_atual = datetime.now().year
    
    if anos is None:
        anos = list(range(ano_atual - 4, ano_atual + 1))  # Últimos 5 anos
    
    dfs = []
    
    for ano in anos:
        df_ano = fetch_portal_transparencia_data(
            cpf_cnpj,
            datetime(year=ano, month=1, day=1)
        )
        if not df_ano.empty:
            df_ano['ano_consulta'] = ano
            dfs.append(df_ano)
    
    if dfs:
        return pd.concat(dfs, ignore_index=True)
    
    return pd.DataFrame()
