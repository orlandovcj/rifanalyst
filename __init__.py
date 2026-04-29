# rif_analyst/__init__.py
"""
RIF Analyst - Sistema de Análise de Relatórios de Inteligência Financeira

Este pacote fornece ferramentas para análise de comunicações suspeitas
relacionadas à lavagem de dinheiro, conforme padrões COAF/BACEN.

Módulos principais:
- config: Configurações e constantes
- core: Carregamento e processamento de dados
- analytics: Detecção de padrões e análise de redes
- visualizations: Gráficos e visualizações
- integrations: APIs externas
- utils: Funções auxiliares
"""

from .config import (
    VERSAO,
    DATA_VERSAO,
    APP_TITLE,
    APP_ICON,
    SEGMENTO_MAP,
    OCORRENCIA_MAP,
    CRITICIDADE_MAP,
    SCORE_WEIGHTS,
    CIDADES_RISCO,
    KEYWORDS_SUSPEITAS
)

__version__ = VERSAO
__author__ = "NAE/CGU/SC"

__all__ = [
    'VERSAO',
    'DATA_VERSAO',
    'APP_TITLE',
    'APP_ICON',
    'SEGMENTO_MAP',
    'OCORRENCIA_MAP',
    'CRITICIDADE_MAP',
    'SCORE_WEIGHTS',
    'CIDADES_RISCO',
    'KEYWORDS_SUSPEITAS'
]
