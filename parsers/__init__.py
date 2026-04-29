# parsers/__init__.py
"""
Módulo de parsers para extração de dados de narrativas bancárias.

IMPORTANTE: Usa imports absolutos para compatibilidade quando main.py está na raiz.
"""
from parsers.narrative_parser import (
    extract_all_financial_data,
    clean_value
)

from parsers.narrative_analyzer import analyze_narrative

__all__ = [
    'extract_all_financial_data',
    'clean_value',
    'analyze_narrative'
]
