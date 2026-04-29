# core/data_loader.py - Carregamento de Dados
"""
Módulo para carregamento e validação de arquivos CSV do RIF.

IMPORTANTE: Usa imports ABSOLUTOS (não relativos) para compatibilidade
quando main.py está na raiz do projeto.
"""
from __future__ import annotations
import pandas as pd
import streamlit as st
from io import StringIO
from typing import Optional, Tuple, List
import traceback

# IMPORTS ABSOLUTOS (não usar ..)
from config import CSV_ENCODINGS, EXPECTED_COLUMNS, OCORRENCIA_MAP, SEGMENTO_MAP
from project_utils.helpers import clean_numeric_br


@st.cache_data
def load_data(uploaded_file) -> Optional[pd.DataFrame]:
    """
    Carrega arquivos CSV interrompendo a leitura na primeira linha em branco.
    
    Args:
        uploaded_file: Arquivo enviado via Streamlit file_uploader
        
    Returns:
        DataFrame com dados carregados ou None se houver erro
    """
    file_name = uploaded_file.name if uploaded_file else "Arquivo Desconhecido"
    
    for encoding in CSV_ENCODINGS:
        try:
            uploaded_file.seek(0)
            raw_text = uploaded_file.read().decode(encoding)
            lines = raw_text.splitlines()
            
            # Filtra linhas até encontrar a primeira linha vazia
            valid_lines = []
            for line in lines:
                # Verifica se a linha está vazia ou contém apenas separadores
                if not line.strip() or line.strip().replace(';', '') == '':
                    break
                valid_lines.append(line)
            
            # Reconstrói conteúdo filtrado
            truncated_content = StringIO('\n'.join(valid_lines))
            
            # Carrega DataFrame
            df = pd.read_csv(
                truncated_content,
                sep=';',
                encoding=encoding,
                low_memory=False,
                na_values=['-', '', '#N/D', 'N/A']
            )
            
            # Tratar colunas de data
            df = _process_date_columns(df, file_name)

            # >>>>> CORREÇÃO: Garantir que colunas de ID sejam string <<<<<
            string_id_cols = ['Indexador', 'idOcorrencia', 'idComunicacao', 'CodigoSegmento', 'NumeroOcorrenciaBC']
            for col in string_id_cols:
                if col in df.columns:
                    # Converte para string, remove ".0" de floats e remove espaços
                    df[col] = df[col].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            
            return df
            
        except UnicodeDecodeError:
            continue
        except Exception as e:
            st.error(f"Erro crítico ao carregar arquivo {file_name}: {str(e)}")
            return None
    
    st.error(f"Não foi possível ler o arquivo {file_name} com as codificações testadas.")
    return None


def _process_date_columns(df: pd.DataFrame, file_name: str) -> pd.DataFrame:
    """
    Processa e converte colunas de data no DataFrame.
    
    Args:
        df: DataFrame a ser processado
        file_name: Nome do arquivo para mensagens de erro
        
    Returns:
        DataFrame com colunas de data convertidas
    """
    date_cols = [col for col in df.columns if 'data' in col.lower()]
    
    for col in date_cols:
        original_type = df[col].dtype
        try:
            # Tenta formato brasileiro primeiro
            converted_date = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
            
            # Tenta formato americano se brasileiro falhar
            if converted_date.isna().all() and original_type == 'object':
                converted_date = pd.to_datetime(df[col], errors='coerce', dayfirst=False)
            
            # Tenta inferir automaticamente
            if converted_date.isna().all() and original_type == 'object':
                converted_date = pd.to_datetime(df[col], errors='coerce', infer_datetime_format=True)
            
            df[col] = converted_date
            
        except Exception:
            st.warning(f"Não foi possível converter a coluna '{col}' em {file_name}.")
    
    return df


def check_columns(df: pd.DataFrame, expected_cols: List[str], file_name: str) -> bool:
    """
    Verifica se todas as colunas esperadas existem no DataFrame.
    
    Args:
        df: DataFrame a verificar
        expected_cols: Lista de colunas esperadas
        file_name: Nome do arquivo para mensagens de erro
        
    Returns:
        True se todas as colunas existem, False caso contrário
    """
    if df is None:
        st.error(f"O DataFrame do arquivo {file_name} não foi carregado.")
        return False
    
    missing_cols = [col for col in expected_cols if col not in df.columns]
    
    if missing_cols:
        st.error(f"Colunas mínimas esperadas ausentes em {file_name}: {missing_cols}")
        return False
    
    return True


def safe_merge(
    left: pd.DataFrame,
    right: pd.DataFrame,
    left_on: str,
    right_on: str,
    **kwargs
) -> Optional[pd.DataFrame]:
    """
    Realiza merge seguro entre dois DataFrames com validações.
    
    Args:
        left: DataFrame da esquerda
        right: DataFrame da direita
        left_on: Coluna de merge no DataFrame da esquerda
        right_on: Coluna de merge no DataFrame da direita
        **kwargs: Argumentos adicionais para pd.merge
        
    Returns:
        DataFrame merged ou None se houver erro
    """
    if left is None or right is None:
        st.error("Erro no merge: um dos DataFrames está vazio.")
        return None
    
    try:
        if left_on not in left.columns:
            st.error(f"A coluna de merge '{left_on}' não foi encontrada no DataFrame da esquerda.")
            return None
        
        if right_on not in right.columns:
            st.error(f"A coluna de merge '{right_on}' não foi encontrada no DataFrame da direita.")
            return None
        
        left_copy = left.copy()
        right_copy = right.copy()
        
        # Garante que colunas de merge sejam string
        left_copy[left_on] = left_copy[left_on].astype(str).str.strip()
        right_copy[right_on] = right_copy[right_on].astype(str).str.strip()
        
        merged_df = pd.merge(left_copy, right_copy, left_on=left_on, right_on=right_on, **kwargs)
        
        # Verifica se merge está vazio
        if merged_df.empty and not left_copy.empty and not right_copy.empty:
            left_ids = set(left_copy[left_on].unique())
            right_ids = set(right_copy[right_on].unique())
            
            if not left_ids.intersection(right_ids):
                st.warning(f"Merge vazio: nenhum valor correspondente entre '{left_on}' e '{right_on}'.")
            else:
                st.warning(f"Merge vazio, mas há IDs correspondentes. Verifique os tipos de dados.")
        
        return merged_df
        
    except Exception as e:
        st.error(f"Erro crítico durante o merge: {str(e)}")
        st.code(traceback.format_exc())
        return None


def load_all_files(
    file_ocorrencias,
    file_envolvidos,
    file_comunicacoes
) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """
    Carrega os três arquivos CSV necessários para análise.
    
    Args:
        file_ocorrencias: Arquivo de ocorrências
        file_envolvidos: Arquivo de envolvidos
        file_comunicacoes: Arquivo de comunicações
        
    Returns:
        Tupla com os três DataFrames (ocorrencias, envolvidos, comunicacoes)
    """
    st.info("Carregando arquivos...")
    
    df_ocorrencias = load_data(file_ocorrencias)
    df_envolvidos = load_data(file_envolvidos)
    df_comunicacoes = load_data(file_comunicacoes)
    
    # Verifica se todos foram carregados
    if df_ocorrencias is None or df_envolvidos is None or df_comunicacoes is None:
        st.error("Erro no carregamento. Verifique os arquivos.")
        return None, None, None

    # Garante que idOcorrencia seja string para consistência nos filtros
    if 'idOcorrencia' in df_ocorrencias.columns:
        # Remove '.0' de números de ponto flutuante antes de converter para string
        df_ocorrencias['idOcorrencia'] = df_ocorrencias['idOcorrencia'].apply(
            lambda x: str(int(x)) if pd.notna(x) and isinstance(x, float) and x.is_integer() else str(x) if pd.notna(x) else ''
        ).str.strip()
    
    # Verifica colunas obrigatórias
    checks = [
        check_columns(df_ocorrencias, EXPECTED_COLUMNS['ocorrencias'], "Ocorrencias.csv"),
        check_columns(df_envolvidos, EXPECTED_COLUMNS['envolvidos'], "Envolvidos.csv"),
        check_columns(df_comunicacoes, EXPECTED_COLUMNS['comunicacoes'], "Comunicacoes.csv")
    ]
    
    if not all(checks):
        return None, None, None
    
    st.success(f"Arquivos carregados: Ocorrências ({len(df_ocorrencias)}), "
               f"Envolvidos ({len(df_envolvidos)}), Comunicações ({len(df_comunicacoes)})")
    
    return df_ocorrencias, df_envolvidos, df_comunicacoes


def prepare_value_columns(df_comunicacoes: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara colunas de valores (Campo A-E) no DataFrame de comunicações,
    com flexibilidade para nomes de colunas alternativos e de forma case-insensitive.
    
    Args:
        df_comunicacoes: DataFrame de comunicações
        
    Returns:
        DataFrame com colunas de valor convertidas
    """
    df = df_comunicacoes.copy()
    
    # Mapeamento de nomes padronizados para possíveis nomes de colunas
    campo_map = {
        'CampoA': ['CampoA', 'valorA', 'Valor A', 'valor a'],
        'CampoB': ['CampoB', 'valorB', 'Valor B', 'valor b'],
        'CampoC': ['CampoC', 'valorC', 'Valor C', 'valor c'],
        'CampoD': ['CampoD', 'valorD', 'Valor D', 'valor d'],
        'CampoE': ['CampoE', 'valorE', 'Valor E', 'valor e'],
    }

    df_cols_lower_map = {c.lower(): c for c in df.columns}

    for campo_std, possiveis_nomes in campo_map.items():
        source_col_name = None
        dest_col_name = f"Valor{campo_std}"

        # 1. Find source column (case-insensitive)
        for nome_possivel in possiveis_nomes:
            if nome_possivel.lower() in df_cols_lower_map:
                source_col_name = df_cols_lower_map[nome_possivel.lower()]
                break
        
        # 2. If source found, create/overwrite dest column
        if source_col_name:
            df[dest_col_name] = clean_numeric_br(df[source_col_name])
        # 3. If no source, check if dest column already exists (case-insensitive)
        else:
            dest_col_original_case = df_cols_lower_map.get(dest_col_name.lower())
            if dest_col_original_case:
                # clean in place, and standardize column name if different
                df[dest_col_name] = clean_numeric_br(df[dest_col_original_case])
                if dest_col_original_case != dest_col_name:
                    df = df.drop(columns=[dest_col_original_case])
            # 4. If neither source nor dest exist, create dest with zeros
            else:
                df[dest_col_name] = 0.0
            
    # 'ValorTotal' é um alias para 'ValorCampoA' para consistência.
    if 'ValorCampoA' not in df.columns:
        df['ValorCampoA'] = 0.0
    
    df['ValorTotal'] = df['ValorCampoA']
    
    return df

def load_anonymized_data(uploaded_file) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """
    Carrega um único arquivo CSV anonimizado e o desmembra nos DataFrames esperados pela aplicação.
    """
    st.info("Carregando arquivo de dados anonimizados...")
    df_anon = load_data(uploaded_file)

    if df_anon is None:
        st.error("Falha ao carregar o arquivo anonimizado.")
        return None, None, None, None

    # === Prepara o df_final (df_anon com colunas renomeadas/criadas) ===
    df_final = df_anon.copy()
    df_final = df_final.rename(columns={
        'Token_Envolvido': 'cpfCnpjEnvolvido',
        'Token_Comunicante': 'nomeComunicante'
    })
    
    # Adiciona colunas que podem estar faltando
    if 'nomeEnvolvido' not in df_final.columns:
        df_final['nomeEnvolvido'] = df_final['cpfCnpjEnvolvido']
    if 'Indexador_x' not in df_final.columns:
        df_final['Indexador_x'] = df_final['Indexador']
    
    # >>>>> CORREÇÃO: Prepara as colunas de valor no DataFrame final <<<<<
    df_final = prepare_value_columns(df_final)

    # >>>>> CORREÇÃO: Converte colunas 'Sim/Não' para Boolean <<<<<
    for col in ['bitPepCitado', 'bitPessoaObrigadaCitado', 'intServidorCitado']:
        if col in df_final.columns:
            df_final[col] = df_final[col].astype(str).str.lower().str.strip() == 'sim'

    # >>>>> CORREÇÃO: Adiciona a descrição dos segmentos <<<<<
    df_segmento_desc = pd.DataFrame(
        list(SEGMENTO_MAP.items()),
        columns=['CodigoSegmento', 'DescricaoCampos']
    )
    df_segmento_desc['CodigoSegmento'] = df_segmento_desc['CodigoSegmento'].astype(str)
    
    if 'CodigoSegmento' in df_final.columns:
        # Garante que a coluna de merge em df_final também seja string
        df_final['CodigoSegmento'] = df_final['CodigoSegmento'].astype(str).str.strip()
        df_final = pd.merge(
            df_final, df_segmento_desc,
            on='CodigoSegmento', how='left'
        )
        df_final['DescricaoCampos'] = df_final['DescricaoCampos'].fillna(
            'Segmento não mapeado'
        )
    else:
        df_final['DescricaoCampos'] = 'Segmento não disponível'


    # === Reconstrói df_comunicacoes ===
    cols_com = ['Indexador', 'idComunicacao', 'Data_da_operacao', 'CodigoSegmento', 
                'nomeComunicante', 'CidadeAgencia', 'UFAgencia', 'NomeAgencia', 
                'NumeroAgencia', 'informacoesAdicionais', 'DescricaoCampos']
    
    # Adiciona colunas de valor (CampoA-E) se existirem
    for c in ['CampoA', 'CampoB', 'CampoC', 'CampoD', 'CampoE', 'ValorTotal'] + [f'ValorCampo{l}' for l in 'ABCDE']:
        if c in df_final.columns and c not in cols_com:
            cols_com.append(c)

    df_comunicacoes = df_final[cols_com].drop_duplicates(subset=['Indexador']).copy()
    # A chamada de prepare_value_columns aqui é uma garantia extra, mas a principal está em df_final
    df_comunicacoes = prepare_value_columns(df_comunicacoes)

    # === Reconstrói df_envolvidos ===
    cols_env = ['Indexador', 'cpfCnpjEnvolvido', 'nomeEnvolvido', 'tipoEnvolvido', 
                'bitPepCitado', 'bitPessoaObrigadaCitado', 'intServidorCitado']
    
    # Adiciona colunas de token se existirem
    for c in ['Token_Agencia', 'Token_Conta']:
        if c in df_final.columns:
            cols_env.append(c)
    
    df_envolvidos = df_final[cols_env].drop_duplicates().copy()
    
    # Renomeia colunas de token para compatibilidade
    df_envolvidos = df_envolvidos.rename(columns={
        'Token_Agencia': 'agenciaEnvolvido',
        'Token_Conta': 'contaEnvolvido'
    })


    # === Reconstrói df_ocorrencias ===
    cols_ocor = ['Indexador', 'idOcorrencia', 'Ocorrencia']
    df_ocorrencias = df_final[cols_ocor].drop_duplicates().copy()
    
    # Validação final e sucesso
    st.success(f"Arquivo anonimizado carregado. Total de {len(df_final)} registros processados.")
    
    # Retorna o df_final preparado e os 3 dataframes reconstruídos
    return df_final, df_ocorrencias, df_envolvidos, df_comunicacoes
