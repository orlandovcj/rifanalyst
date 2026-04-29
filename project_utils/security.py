# utils/security.py - Funções de Segurança
"""
Funções relacionadas à segurança e gerenciamento de sessão.
"""
from __future__ import annotations
import os
import glob
import tempfile
import time
import streamlit as st
import pandas as pd


def realizar_limpeza_seguranca() -> None:
    """
    Limpa cache, arquivos temporários e força reset dos widgets de upload.
    Deve ser chamado ao encerrar sessão ou após timeout.
    """
    # Limpa cache do Streamlit
    st.cache_data.clear()
    
    # Deleta arquivos temporários de rede
    temp_dir = tempfile.gettempdir()
    temp_files = (
        glob.glob(os.path.join(temp_dir, "*_net_*.html")) +
        glob.glob(os.path.join(temp_dir, "*_comm_*.html"))
    )
    for f in temp_files:
        try:
            os.remove(f)
        except Exception:
            pass
    
    # Limpa sessão e incrementa ID do widget
    new_id = st.session_state.get('uploader_id', 0) + 1
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    
    # Reinicia com novo ID de widget
    st.session_state.uploader_id = new_id
    st.session_state.last_activity = time.time()


def check_session_timeout(timeout_seconds: int = 1800) -> bool:
    """
    Verifica se a sessão expirou por inatividade.
    
    Args:
        timeout_seconds: Tempo limite em segundos (padrão: 30 min)
        
    Returns:
        True se a sessão expirou, False caso contrário
    """
    current_time = time.time()
    
    if 'last_activity' not in st.session_state:
        st.session_state.last_activity = current_time
        return False
    
    elapsed_time = current_time - st.session_state.last_activity
    return elapsed_time > timeout_seconds


def update_activity_timestamp() -> None:
    """
    Atualiza o timestamp de última atividade na sessão.
    """
    st.session_state.last_activity = time.time()


def init_session_state() -> None:
    """
    Inicializa variáveis de estado da sessão se não existirem.
    """
    if 'uploader_id' not in st.session_state:
        st.session_state.uploader_id = 0
    
    if 'last_activity' not in st.session_state:
        st.session_state.last_activity = time.time()
    
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False
    
    if 'df_final' not in st.session_state:
        st.session_state.df_final = None
    
    if 'df_ocorrencias' not in st.session_state:
        st.session_state.df_ocorrencias = None
    
    if 'df_envolvidos' not in st.session_state:
        st.session_state.df_envolvidos = None
    
    if 'df_comunicacoes' not in st.session_state:
        st.session_state.df_comunicacoes = None
    
    if 'cpfs_com_alerta_publico' not in st.session_state:
        st.session_state.cpfs_com_alerta_publico = set()
    
    if 'alerts_processed' not in st.session_state:
        st.session_state.alerts_processed = False

    if "excel_file_uploaded" not in st.session_state:
        st.session_state["excel_file_uploaded"] = False
    if "excel_datasets" not in st.session_state:
        st.session_state["excel_datasets"] = {}
    if "excel_tabela_documentos" not in st.session_state:
        st.session_state["excel_tabela_documentos"] = pd.DataFrame(columns=["cpf_cnpj", "nome_razao_social"])

def get_secret(key: str, default: str = None) -> str:
    """
    Obtém valor de segredo de forma segura.
    Tenta primeiro st.secrets, depois variáveis de ambiente.
    
    Args:
        key: Nome da chave do segredo
        default: Valor padrão se não encontrado
        
    Returns:
        Valor do segredo ou default
    """
    # Tenta Streamlit secrets
    try:
        return st.secrets[key]
    except Exception:
        pass
    
    # Tenta variável de ambiente
    value = os.environ.get(key)
    if value:
        return value
    
    return default


def sanitize_for_log(text: str) -> str:
    """
    Remove dados sensíveis de texto para logs.
    
    Args:
        text: Texto a ser sanitizado
        
    Returns:
        Texto sanitizado
    """
    import re
    
    # Remove CPFs
    text = re.sub(r'\d{3}\.?\d{3}\.?\d{3}-?\d{2}', '[CPF]', str(text))
    
    # Remove CNPJs
    text = re.sub(r'\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}', '[CNPJ]', text)
    
    # Remove valores monetários altos
    text = re.sub(r'R\$\s*[\d.,]+', 'R$ [VALOR]', text)
    
    return text
