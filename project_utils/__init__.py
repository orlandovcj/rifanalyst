# utils/__init__.py
"""
Módulo de utilitários do RIF Analyst.
Contém funções auxiliares diversas.

IMPORTANTE: Usa imports absolutos para compatibilidade quando main.py está na raiz.
"""
from project_utils.helpers import (
    normalize_string,
    clean_numeric_br,
    safe_div,
    clean_value,
    parse_valor_br,
    format_currency_brl,
    extract_cpf_cnpj,
    validate_cpf,
    validate_cnpj,
    get_document_type,
    mask_cpf,
    mask_cnpj,
    extract_financial_value,
    classify_risk_score,
    extract_keywords_from_text,
    extrair_capital_social,
    extrair_renda_mensal,
    extrair_faturamento,
    limpar_valor_portal
)

__all__ = [
    'normalize_string',
    'clean_numeric_br',
    'safe_div',
    'clean_value',
    'parse_valor_br',
    'format_currency_brl',
    'extract_cpf_cnpj',
    'validate_cpf',
    'validate_cnpj',
    'get_document_type',
    'mask_cpf',
    'mask_cnpj',
    'extract_financial_value',
    'classify_risk_score',
    'extract_keywords_from_text',
    'extrair_capital_social',
    'extrair_renda_mensal',
    'extrair_faturamento',
    'limpar_valor_portal'
]
