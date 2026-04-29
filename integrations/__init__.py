# integrations/__init__.py
"""
Módulo de integrações do RIF Analyst.
Contém clientes para APIs externas.

IMPORTANTE: Usa imports absolutos para compatibilidade quando main.py está na raiz.
"""
from integrations.portal_transparencia import (
    fetch_portal_transparencia_data,
    limpar_valor_portal,
    processar_dados_portal,
    resumir_pagamentos_portal,
    verificar_multiplos_anos
)

__all__ = [
    'fetch_portal_transparencia_data',
    'limpar_valor_portal',
    'processar_dados_portal',
    'resumir_pagamentos_portal',
    'verificar_multiplos_anos'
]
