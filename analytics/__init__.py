# analytics/__init__.py
"""
Módulo de análise do RIF Analyst.
Contém detecção de padrões, cálculo de indicadores e análise de redes.

IMPORTANTE: Usa imports absolutos para compatibilidade quando main.py está na raiz.
"""
from analytics.patterns import analyze_suspicious_patterns
from analytics.network import (
    analyze_individual_network,
    create_communication_graph,
    simplify_graph,
    calculate_network_metrics,
    get_top_central_nodes
)

__all__ = [
    'analyze_suspicious_patterns',
    'analyze_individual_network',
    'create_communication_graph',
    'simplify_graph',
    'calculate_network_metrics',
    'get_top_central_nodes'
]
