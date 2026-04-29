# visualizations/__init__.py
"""
Módulo de visualizações do RIF Analyst.
Contém gráficos, redes e diagramas.

IMPORTANTE: Usa imports absolutos para compatibilidade quando main.py está na raiz.
"""
from visualizations.charts import (
    plot_temporal_evolution,
    plot_bar_top_items,
    plot_pie_distribution,
    plot_scatter_risk,
    plot_relationship_strength,
    plot_benford_analysis
)
from visualizations.networks import (
    visualize_network,
    visualize_communication_graph,
    generate_network_legend
)
from visualizations.sankey import (
    plot_sankey_fluxo,
    plot_sankey_envolvido_estruturado
)

__all__ = [
    'plot_temporal_evolution',
    'plot_bar_top_items',
    'plot_pie_distribution',
    'plot_scatter_risk',
    'plot_relationship_strength',
    'plot_benford_analysis',
    'visualize_network',
    'visualize_communication_graph',
    'generate_network_legend',
    'plot_sankey_fluxo',
    'plot_sankey_envolvido_estruturado'
]
