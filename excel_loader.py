# core/excel_loader.py
import streamlit as st
import pandas as pd
import re
from typing import Optional, Tuple, Dict

# IMPORTS ABSOLUTOS
from config import CHAVES_TEXTO
from project_utils.helpers import normalize_string

def load_detalhamento_excel(uploaded_file) -> Tuple[Optional[Dict[str, pd.DataFrame]], Optional[pd.DataFrame]]:
    """
    Loads an Excel file containing RIF detailing sheets.
    Extracts data from each sheet and creates a master identity table.

    Args:
        uploaded_file: Streamlit UploadedFile object for the Excel file.

    Returns:
        A tuple containing:
        - A dictionary of DataFrames, where keys are sheet names and values are the loaded DataFrames.
        - A DataFrame representing the master identity table (cpf_cnpj, nome_razao_social).
        Returns (None, None) if an error occurs.
    """
    datasets = {}
    tabela_documentos = pd.DataFrame(columns=["cpf_cnpj", "nome_razao_social"])

    if not uploaded_file:
        st.error("Nenhum arquivo Excel foi carregado.")
        return None, None

    with st.spinner("Processando abas e vinculando identidades do Excel..."):
        try:
            excel_obj = pd.ExcelFile(uploaded_file)
            
            for nome_real in excel_obj.sheet_names:
                # Read only header to infer dtypes for CHAVES_TEXTO
                df_temp = pd.read_excel(uploaded_file, sheet_name=nome_real, nrows=0)
                dtype_map = {
                    c: str
                    for c in df_temp.columns
                    if any(x in c.upper() for x in CHAVES_TEXTO)
                }
                df = pd.read_excel(uploaded_file, sheet_name=nome_real, dtype=dtype_map)
                datasets[nome_real] = df

            # Criar Tabela Mestra de Identidades (Aba Comunicações)
            # Use normalize_string from helpers
            aba_com = next(
                (
                    n
                    for n in datasets.keys()
                    if "COMUNICA" in normalize_string(n)
                ),
                None,
            )
            if aba_com:
                df_c = datasets[aba_com]
                ident = []
                for _, r in df_c.iterrows():
                    n = str(r.get("NOME DO ENVOLVIDO", "")).strip()
                    c = str(r.get("CPF DO ENVOLVIDO", "")).strip()
                    j = str(r.get("CNPJ DO ENVOLVIDO", "")).strip()
                    d = c if c not in ["nan", ""] else j
                    if d not in ["nan", ""]:
                        ident.append(
                            {
                                "cpf_cnpj": d,
                                "nome_razao_social": n,
                            }
                        )
                tabela_documentos = (
                    pd.DataFrame(ident)
                    .drop_duplicates("cpf_cnpj")
                )
            
            st.success(
                f"Sucesso! {len(datasets)} abas do Excel carregadas."
            )
            return datasets, tabela_documentos

        except Exception as e:
            st.error(f"Erro na importação do Excel: {e}")
            return None, None