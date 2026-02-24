# indicadores.py - Versão 3.2.1 (Correção de Nomes de Coluna)
from __future__ import annotations
import pandas as pd
import numpy as np
import requests
import streamlit as st


def _safe_div(num, den):
    return float(num) / float(den) if den and den != 0 and not pd.isna(den) else 0.0

def calc_indicadores_envolvido(df: pd.DataFrame, valor_col: str = "ValorTotal", data_col: str = "Data_da_operacao") -> pd.DataFrame:
    if df is None or df.empty: return pd.DataFrame()
    df_local = df.copy()
    
    # Detecção automática: se 'Data_da_operacao' não existir, tenta 'Datadaoperacao'
    if data_col not in df_local.columns and "Datadaoperacao" in df_local.columns:
        data_col = "Datadaoperacao"
    
    if data_col not in df_local.columns:
        # Se nenhuma existir, cria uma coluna vazia para não travar o processo
        df_local[data_col] = pd.NaT

    df_local[valor_col] = pd.to_numeric(df_local[valor_col], errors="coerce").fillna(0.0)
    
    # 1. ACHATAMENTO: Garante 1 linha por Envolvido + Comunicação
    # Nota: Removemos o data_col do .agg() e pegamos via 'first' apenas se a coluna existir
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

    df_unique = df_local.groupby(["cpfCnpjEnvolvido", "Indexador_x"], dropna=False).agg(agg_dict).reset_index()

    # 2. AGREGAÇÃO POR ENVOLVIDO
    base_agg = df_unique.groupby("cpfCnpjEnvolvido", dropna=False).agg(
        nomeEnvolvido=("nomeEnvolvido", "first"),
        n_comunicacoes=("Indexador_x", "nunique"),
        valor_total=(valor_col, "sum"),
        flag_pep=("bitPepCitado", "max"),
        flag_servidor=("intServidorCitado", "max"),
        flag_pessoa_obrigada=("bitPessoaObrigadaCitado", "max")
    ).reset_index()

    # 3. FRACIONAMENTO (Baseado em dias distintos)
    if data_col in df_local.columns and not df_local[data_col].isna().all():
        df_local['dia'] = pd.to_datetime(df_local[data_col], errors='coerce').dt.date
        daily = df_local.dropna(subset=['dia']).groupby(['cpfCnpjEnvolvido', 'dia']).agg(n_ops=('Indexador_x', 'nunique')).reset_index()
        frac = daily[daily['n_ops'] >= 3].groupby('cpfCnpjEnvolvido').size().reset_index(name='fracionamento_dias_com_3+_ops')
    else:
        frac = pd.DataFrame(columns=['cpfCnpjEnvolvido', 'fracionamento_dias_com_3+_ops'])
    
    # 4. HHI (Concentração de Contrapartes)
    df_contra = df_unique.merge(df_unique[['Indexador_x', 'cpfCnpjEnvolvido', valor_col]], on='Indexador_x', suffixes=('', '_c'))
    df_contra = df_contra[df_contra['cpfCnpjEnvolvido'] != df_contra['cpfCnpjEnvolvido_c']]
    
    if not df_contra.empty:
        pares = df_contra.groupby(['cpfCnpjEnvolvido', 'cpfCnpjEnvolvido_c'])[valor_col + '_c'].sum().reset_index(name='v_par')
        totais = pares.groupby('cpfCnpjEnvolvido')['v_par'].sum().reset_index(name='v_tot')
        pares = pares.merge(totais, on='cpfCnpjEnvolvido')
        pares['share'] = pares.apply(lambda r: _safe_div(r['v_par'], r['v_tot']), axis=1)
        hhi = pares.groupby('cpfCnpjEnvolvido')['share'].apply(lambda x: float(np.sum(x**2))).reset_index(name='hhi_contrapartes')
    else:
        hhi = pd.DataFrame(columns=['cpfCnpjEnvolvido', 'hhi_contrapartes'])

    return base_agg.merge(frac, on='cpfCnpjEnvolvido', how='left').merge(hhi, on='cpfCnpjEnvolvido', how='left').fillna(0)

def calc_indicadores_comunicacao(df: pd.DataFrame, valor_col: str = "ValorTotal") -> pd.DataFrame:
    if df is None or df.empty: return pd.DataFrame()
    return df.groupby("Indexador_x").agg(
        n_envolvidos=("cpfCnpjEnvolvido", "nunique"),
        valor_total=(valor_col, "max"),
        flag_pep_na_com=("bitPepCitado", "max")
    ).reset_index().sort_values("valor_total", ascending=False)

def calc_indicadores_pares(df: pd.DataFrame, valor_col: str = "ValorTotal") -> pd.DataFrame:
    if df is None or df.empty: return pd.DataFrame()
    df_base = df.groupby(["Indexador_x", "cpfCnpjEnvolvido"])[valor_col].max().reset_index()
    df_p = df_base.merge(df_base, on="Indexador_x", suffixes=("_orig", "_contra"))
    df_p = df_p[df_p["cpfCnpjEnvolvido_orig"] != df_p["cpfCnpjEnvolvido_contra"]]
    return df_p.groupby(["cpfCnpjEnvolvido_orig", "cpfCnpjEnvolvido_contra"]).agg(
        valor_total_par=(valor_col + "_contra", "sum"),
        n_comunicacoes_compartilhadas=("Indexador_x", "nunique")
    ).reset_index().rename(columns={"cpfCnpjEnvolvido_orig": "cpf_origem", "cpfCnpjEnvolvido_contra": "cpf_contraparte"})

def fetch_portal_transparencia_data(cpf_cnpj, data_inicio, data_fim):
    """
    Consulta pagamentos no Portal da Transparência para um CPF/CNPJ específico.
    Requer um token de API (Chave) válido.
    """
    # Remover caracteres não numéricos do CPF/CNPJ
    id_limpo = ''.join(filter(str.isdigit, str(cpf_cnpj)))
    
    # A URL do endpoint de despesas por favorecido
    url = "https://api.portaldatransparencia.gov.br/api-de-dados/despesas/por-favorecido"
    
    # Cabeçalhos necessários (O Token deve estar nos secrets do Streamlit)
    headers = {
        "accept": "*/*",
        "chave-api-dados": st.secrets["portal_transparencia_token"]
    }
    
    params = {
        "codigoFavorecido": id_limpo,
        "dataInicial": data_inicio.strftime('%d/%m/%Y'),
        "dataFinal": data_fim.strftime('%d/%m/%Y'),
        "pagina": 1
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            return pd.DataFrame(response.json())
        elif response.status_code == 401:
            st.error("Token da API do Portal da Transparência inválido ou expirado.")
            return pd.DataFrame()
        else:
            st.warning(f"Erro na consulta: {response.status_code}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro de conexão com o Portal: {str(e)}")
        return pd.DataFrame()       