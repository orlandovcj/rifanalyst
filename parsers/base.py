# parsers/base.py - Parser Base para Narrativas Bancárias
"""
Classe base abstrata para parsers de narrativas bancárias.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, List, Optional, Tuple


class BaseBankParser(ABC):
    """
    Classe base abstrata para parsers de narrativas de RIF.
    
    Cada banco tem um formato específico de narrativa no campo
    'informacoesAdicionais' dos arquivos de comunicação.
    """
    
    # Nome identificador do banco
    bank_name: str = "Base"
    
    # Padrões de identificação do banco na narrativa
    identification_patterns: List[str] = []
    
    @classmethod
    @abstractmethod
    def can_parse(cls, text: str) -> bool:
        """
        Verifica se este parser pode processar o texto.
        
        Args:
            text: Texto da narrativa
            
        Returns:
            True se o parser consegue processar
        """
        pass
    
    @classmethod
    @abstractmethod
    def parse(cls, text: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Extrai dados financeiros da narrativa.
        
        Args:
            text: Texto da narrativa
            
        Returns:
            Tupla com (df_creditos, df_debitos, df_cartoes)
        """
        pass
    
    @classmethod
    def detect_bank(cls, text: str) -> Optional[str]:
        """
        Tenta identificar qual banco originou a narrativa.
        
        Args:
            text: Texto da narrativa
            
        Returns:
            Nome do banco ou None se não identificado
        """
        from . import BANK_PARSERS
        
        for bank_name, parser_module in BANK_PARSERS.items():
            # Importa dinamicamente
            # Por enquanto retorna None
            pass
        
        return None


def clean_value(value_str: str) -> float:
    """
    Converte string monetária para float.
    
    Args:
        value_str: String representando valor monetário
        
    Returns:
        Valor como float
    """
    import re
    
    if isinstance(value_str, (int, float)):
        return float(value_str)
    if not value_str or not isinstance(value_str, str):
        return 0.0
    
    try:
        # Remove tudo que não é dígito, ponto ou vírgula
        val = re.sub(r'[^\d.,]', '', value_str)
        
        # Caso brasileiro: 1.000,00 -> remove ponto, troca vírgula
        if ',' in val and '.' in val:
            if val.find('.') < val.find(','):
                val = val.replace('.', '').replace(',', '.')
            else:
                val = val.replace(',', '')
        elif ',' in val:
            val = val.replace(',', '.')
        
        return float(val)
    except ValueError:
        return 0.0
