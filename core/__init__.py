# core/__init__.py
"""
Módulo core do RIF Analyst.
Contém funcionalidades de carregamento e processamento de dados.

IMPORTANTE: Usa imports absolutos para compatibilidade quando main.py está na raiz.
"""

# Imports absolutos
from core.data_loader import (
    load_data,
    check_columns,
    safe_merge,
    load_all_files,
    prepare_value_columns
)

from core.data_processor import (
    process_raw_data,
    filter_dataframe
)

__all__ = [
    'load_data',
    'check_columns',
    'safe_merge',
    'load_all_files',
    'prepare_value_columns',
    'process_raw_data',
    'filter_dataframe'
]
