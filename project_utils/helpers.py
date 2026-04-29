# utils/helpers.py - Funções Auxiliares
"""
Funções auxiliares e helpers utilizados em todo o sistema RIF Analyst.
"""
from __future__ import annotations
import pandas as pd
import numpy as np
import unicodedata
import re
import string
import io
from typing import Union, Optional, Any, Tuple




def normalize_string(text: Optional[str]) -> str:
    """
    Normaliza string removendo acentos e caracteres especiais.
    Usado para normalizar nomes e comparações de texto.
    
    Args:
        text: Texto a ser normalizado
        
    Returns:
        Texto normalizado em maiúsculas sem acentos
    """
    if pd.isna(text):
        return "DESCONHECIDO"
    text = str(text)
    try:
        # Remover caracteres não-ASCII e normalizar
        text = ''.join(c for c in unicodedata.normalize('NFD', text) 
                      if unicodedata.category(c) != 'Mn')
        normalized = text.encode('ASCII', 'ignore').decode('ASCII')
        return normalized.upper().strip() if normalized else "DESCONHECIDO"
    except Exception:
        # Fallback para limpeza mais simples
        try:
            cleaned = ''.join(filter(str.isalnum, text))
            return cleaned.upper() if cleaned else "DESCONHECIDO"
        except:
            return "ERRO_NORMALIZACAO"


def clean_numeric_br(series: pd.Series) -> pd.Series:
    """
    Limpa e converte uma Series para numérico, tratando formatos monetários
    comuns (ex: '1.234,56' e '1,234.56').
    
    Args:
        series: Series com valores numéricos em formato de string.
        
    Returns:
        Series com valores numéricos (float).
    """
    if series is None:
        return pd.Series(dtype=float)
    
    if series.empty or series.isna().all():
        return pd.Series([0.0] * len(series), index=series.index)

    def _clean_single_value(value_str):
        """Função auxiliar para limpar um único valor."""
        if isinstance(value_str, (int, float)):
            return float(value_str)
        if not isinstance(value_str, str) or not value_str:
            return 0.0
        
        try:
            # Remove caracteres não numéricos, exceto ponto e vírgula
            val = re.sub(r'[^\d.,]', '', value_str)
            
            # Lógica para diferenciar formato BR de US
            if ',' in val and '.' in val:
                # Se o último ponto vem antes da última vírgula, é BR (1.000,00)
                if val.rfind('.') < val.rfind(','):
                    val = val.replace('.', '').replace(',', '.')
                # Se a última vírgula vem antes do último ponto, é US (1,000.00)
                else:
                    val = val.replace(',', '')
            # Se só tem vírgula, assume que é decimal
            elif ',' in val:
                val = val.replace(',', '.')
            
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    return series.apply(_clean_single_value).fillna(0.0)


def safe_div(num: Union[float, int], den: Union[float, int]) -> float:
    """
    Divisão segura que retorna 0 se o denominador for 0 ou None.
    
    Args:
        num: Numerador
        den: Denominador
        
    Returns:
        Resultado da divisão ou 0.0 se denominador inválido
    """
    try:
        if den and den != 0 and not pd.isna(den):
            return float(num) / float(den)
    except (TypeError, ValueError):
        pass
    return 0.0


def clean_value(value_str: str) -> float:
    """
    Converte string monetária para float.
    Suporta formatos: 1.234,56 (BR) ou 1,234.56 (US).
    
    Args:
        value_str: String representando valor monetário
        
    Returns:
        Valor como float
    """
    if isinstance(value_str, (int, float)):
        return float(value_str)
    if not value_str or not isinstance(value_str, str):
        return 0.0
    
    try:
        # Remove tudo que não é dígito, ponto ou vírgula
        val = re.sub(r'[^\d.,]', '', value_str)
        
        # Caso brasileiro: 1.000,00 -> remove ponto, troca vírgula por ponto
        if ',' in val and '.' in val:
            if val.find('.') < val.find(','):  # 1.000,00
                val = val.replace('.', '').replace(',', '.')
            else:  # 1,000.00 (formato US)
                val = val.replace(',', '')
        elif ',' in val:  # 1000,00
            val = val.replace(',', '.')
        # Se só tem ponto (1000.00), float() resolve
        
        return float(val)
    except ValueError:
        return 0.0


def parse_valor_br(valor_str: str) -> float:
    """
    Alias para clean_value para compatibilidade.
    """
    return clean_value(valor_str)


def format_currency_brl(value: float) -> str:
    """
    Formata valor numérico para moeda brasileira.
    
    Args:
        value: Valor numérico
        
    Returns:
        String formatada como R$ 1.234,56
    """
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def extract_cpf_cnpj(text: str) -> str:
    """
    Extrai apenas números de um CPF ou CNPJ.
    
    Args:
        text: String contendo CPF ou CNPJ
        
    Returns:
        String contendo apenas dígitos
    """
    if pd.isna(text):
        return ""
    return ''.join(filter(str.isdigit, str(text)))


def validate_cpf(cpf: str) -> bool:
    """
    Valida CPF brasileiro.
    
    Args:
        cpf: String contendo CPF (apenas números)
        
    Returns:
        True se válido, False caso contrário
    """
    cpf = extract_cpf_cnpj(cpf)
    
    if len(cpf) != 11:
        return False
    
    # Verifica se todos os dígitos são iguais
    if cpf == cpf[0] * 11:
        return False
    
    # Validação do primeiro dígito verificador
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = (soma * 10) % 11
    if resto == 10:
        resto = 0
    if resto != int(cpf[9]):
        return False
    
    # Validação do segundo dígito verificador
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = (soma * 10) % 11
    if resto == 10:
        resto = 0
    if resto != int(cpf[10]):
        return False
    
    return True


def validate_cnpj(cnpj: str) -> bool:
    """
    Valida CNPJ brasileiro.
    
    Args:
        cnpj: String contendo CNPJ (apenas números)
        
    Returns:
        True se válido, False caso contrário
    """
    cnpj = extract_cpf_cnpj(cnpj)
    
    if len(cnpj) != 14:
        return False
    
    # Verifica se todos os dígitos são iguais
    if cnpj == cnpj[0] * 14:
        return False
    
    # Validação do primeiro dígito verificador
    pesos = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * pesos[i] for i in range(12))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto
    if digito1 != int(cnpj[12]):
        return False
    
    # Validação do segundo dígito verificador
    pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * pesos[i] for i in range(13))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto
    if digito2 != int(cnpj[13]):
        return False
    
    return True


def get_document_type(doc: str) -> str:
    """
    Identifica se o documento é CPF ou CNPJ baseado no tamanho.
    
    Args:
        doc: Documento (CPF ou CNPJ)
        
    Returns:
        'CPF', 'CNPJ' ou 'INVALIDO'
    """
    doc_clean = extract_cpf_cnpj(doc)
    if len(doc_clean) == 11:
        return 'CPF'
    elif len(doc_clean) == 14:
        return 'CNPJ'
    return 'INVALIDO'


def mask_cpf(cpf: str) -> str:
    """
    Mascara CPF para exibição (ex: 123.456.789-**).
    
    Args:
        cpf: CPF completo
        
    Returns:
        CPF mascarado
    """
    cpf = extract_cpf_cnpj(cpf)
    if len(cpf) != 11:
        return cpf
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-**"


def mask_cnpj(cnpj: str) -> str:
    """
    Mascara CNPJ para exibição (ex: 12.345.678/0001-**).
    
    Args:
        cnpj: CNPJ completo
        
    Returns:
        CNPJ mascarado
    """
    cnpj = extract_cpf_cnpj(cnpj)
    if len(cnpj) != 14:
        return cnpj
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-**"


def extract_financial_value(text: str, pattern: str = None) -> float:
    """
    Extrai valor financeiro de um texto.
    
    Args:
        text: Texto contendo valor financeiro
        pattern: Padrão regex opcional para busca específica
        
    Returns:
        Valor extraído ou 0.0
    """
    if pd.isna(text) or not text:
        return 0.0
    
    # Padrão padrão para valores em reais
    if pattern is None:
        pattern = r'R\$\s*([\d.,]+)'
    
    match = re.search(pattern, str(text), re.IGNORECASE)
    if match:
        return clean_value(match.group(1))
    return 0.0


def classify_risk_score(pontos: int) -> str:
    """
    Classifica o nível de risco baseado na pontuação.
    
    Args:
        pontos: Pontuação total
        
    Returns:
        Classificação de risco
    """
    if pontos >= 20:
        return 'Altíssimo Risco'
    if pontos >= 10:
        return 'Alto Risco'
    return 'Médio Risco'


def extract_keywords_from_text(text: str, keywords: list) -> list:
    """
    Extrai palavras-chave encontradas em um texto.
    
    Args:
        text: Texto para análise
        keywords: Lista de palavras-chave a buscar
        
    Returns:
        Lista de palavras-chave encontradas
    """
    if pd.isna(text) or not text:
        return []
    
    text_upper = str(text).upper()
    found = []
    
    for keyword in keywords:
        if keyword.upper() in text_upper:
            found.append(keyword)
    
    return found


def extrair_capital_social(texto) -> float:
    """
    Extrai o Capital Social declarado em narrativas bancárias.
    
    Args:
        texto: Texto da narrativa
        
    Returns:
        Valor do capital social ou 0.0 se não encontrado
    """
    if pd.isna(texto):
        return 0.0
    
    padrao = r"capital\s+social\s*(?:\(.*?\))?\s*(?:de|:)?\s*R\$\s*(?P<val>[\d.,]+)"
    match = re.search(padrao, str(texto), re.IGNORECASE)
    
    if match:
        val_str = match.group('val')
        val_limpo = val_str.replace('.', '').replace(',', '.')
        try:
            return float(val_limpo)
        except ValueError:
            return 0.0
    return 0.0


def extrair_renda_mensal(texto) -> float:
    """
    Extrai a Renda Mensal declarada em narrativas para Pessoas Físicas.
    
    Args:
        texto: Texto da narrativa
        
    Returns:
        Valor da renda mensal ou 0.0 se não encontrado
    """
    if pd.isna(texto):
        return 0.0
    
    padrao = r"(?:renda|rendimento)\s+mensal\s*(?:\(.*?\))?\s*(?:de|:)?\s*R\$\s*(?P<val>[\d.,]+)"
    match = re.search(padrao, str(texto), re.IGNORECASE)
    
    if match:
        val_str = match.group('val')
        val_limpo = val_str.replace('.', '').replace(',', '.')
        try:
            return float(val_limpo)
        except ValueError:
            return 0.0
    return 0.0


def extrair_faturamento(texto) -> float:
    """
    Extrai o Faturamento (Anual ou Mensal) declarado em narrativas.
    
    Args:
        texto: Texto da narrativa
        
    Returns:
        Valor do faturamento anualizado ou 0.0 se não encontrado
    """
    if pd.isna(texto):
        return 0.0
    
    padrao = r"faturamento\s+(?:anual|mensal)?\s*(?:\(.*?\))?\s*(?:de|:)?\s*R\$\s*(?P<val>[\d.,]+)"
    match = re.search(padrao, str(texto), re.IGNORECASE)
    
    if match:
        val_str = match.group('val')
        val_limpo = val_str.replace('.', '').replace(',', '.')
        try:
            valor = float(val_limpo)
            # Se a narrativa explicitamente disser "mensal", anualizamos
            if "mensal" in match.group(0).lower():
                return valor * 12
            return valor
        except ValueError:
            return 0.0
    return 0.0


def limpar_valor_portal(v) -> float:
    """
    Limpa strings de valores do Portal da Transparência (padrão BR).
    Trata espaços, pontos de milhar e sinais de negativo.
    
    Args:
        v: Valor a ser limpo (string ou número)
        
    Returns:
        Valor como float
    """
    if pd.isna(v) or v == "" or v == "N/A":
        return 0.0
    
    # Converte para string e remove espaços
    s = str(v).strip().replace(' ', '')
    
    # Inverte separadores: remove ponto de milhar e troca vírgula por ponto decimal
    s = s.replace('.', '').replace(',', '.')
    
    try:
        return float(s)
    except ValueError:
        return 0.0

