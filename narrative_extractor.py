#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Narrative Extractor - Extrator de Informações de Narrativas RIF
================================================================================
Script standalone para extração automática de dados estruturados do campo
"Informações Adicionais" de relatórios de inteligência financeira.

Versão 3.1.0 - Melhorias:
- Pré-processamento de texto com limpeza de caracteres especiais
- Normalização de CPF/CNPJ
- Validação de valores monetários (padrão brasileiro)
- Remoção de stopwords e ruído
- Extração completa de contrapartes

Processa 100% localmente, sem envio de dados para serviços externos.
Desenvolvido para contexto de sigilo e compliance com LGPD.

Autor: RIFAnalyst Team
"""

import re
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
#import json
import unicodedata


# =============================================================================
# CONFIGURAÇÕES E CONSTANTES
# =============================================================================

# Stopwords para limpeza de texto
STOPWORDS = {
    'de', 'da', 'do', 'das', 'dos', 'em', 'na', 'no', 'nas', 'nos',
    'a', 'o', 'e', 'ou', 'para', 'por', 'com', 'sem', 'entre',
    'que', 'como', 'foi', 'sendo', 'são', 'está', 'estão', 'ser',
    'tem', 'têm', 'seu', 'sua', 'seus', 'suas', 'este', 'esta',
    'estes', 'estas', 'esse', 'essa', 'esses', 'essas', 'aquele',
    'aquela', 'aqueles', 'aquelas', 'isto', 'isso', 'aquilo',
}

# Padrões de documentos
PADRAO_CPF = re.compile(r'(\d{3})\.?(\d{3})\.?(\d{3})-?(\d{2})')
PADRAO_CNPJ = re.compile(r'(\d{2})\.?(\d{3})\.?(\d{3})/?(\d{4})-?(\d{2})')

# Padrão de valor monetário brasileiro
PADRAO_VALOR_BR = re.compile(
    r'R?\$?\s*'                           # R$ opcional
    r'(\d{1,3}(?:\.\d{3})*,\d{2})'        # Formato: 9.999.999,99
)


# =============================================================================
# ESTRUTURAS DE DADOS
# =============================================================================

@dataclass
class DadosCadastrais:
    """Dados cadastrais da pessoa analisada."""
    nome: Optional[str] = None
    cpf: Optional[str] = None
    cnpj: Optional[str] = None
    idade: Optional[int] = None
    estado_civil: Optional[str] = None
    email: Optional[str] = None
    nacionalidade: Optional[str] = None
    endereco: Optional[str] = None
    cep: Optional[str] = None
    profissao: Optional[str] = None
    categoria_cliente: Optional[str] = None
    cliente_desde: Optional[str] = None
    conjuge_nome: Optional[str] = None
    conjuge_cpf: Optional[str] = None
    empresas_socio: List[Dict] = field(default_factory=list)


@dataclass
class DadosFinanceiros:
    """Dados financeiros declarados."""
    renda: Optional[float] = None
    patrimonio: Optional[str] = None
    patrimonio_min: Optional[float] = None
    patrimonio_max: Optional[float] = None
    faturamento: Optional[float] = None


@dataclass
class PEPRelacionado:
    """Pessoa Exposta Politicamente relacionada."""
    nome: Optional[str] = None
    cargo: Optional[str] = None
    orgao: Optional[str] = None
    carencia: Optional[str] = None
    tipo_relacionamento: Optional[str] = None
    possui_midia: bool = False
    resumo_midia: Optional[str] = None


@dataclass
class Contraparte:
    """Contraparte em transações."""
    documento: Optional[str] = None
    tipo_documento: Optional[str] = None
    nome: Optional[str] = None
    razao_social: Optional[str] = None
    valor: Optional[float] = None
    percentual: Optional[float] = None
    qtd_transacoes: Optional[int] = None
    banco: Optional[str] = None
    agencia: Optional[str] = None
    conta: Optional[str] = None
    endereco: Optional[str] = None
    atividade: Optional[str] = None
    data_abertura: Optional[str] = None
    porte: Optional[str] = None
    faturamento_presumido: Optional[float] = None
    renda_presumida: Optional[float] = None
    possui_midia: bool = False
    pep_relacionado: bool = False
    reportado_pld: bool = False
    regiao_fronteira: bool = False
    amazonia_legal: bool = False
    comunicados: List[str] = field(default_factory=list)


@dataclass
class Alerta:
    """Alerta identificado na narrativa."""
    tipo: str
    descricao: str
    severidade: str


@dataclass
class TransacaoSuspeita:
    """Transação com características suspeitas."""
    data: Optional[str] = None
    tipo: Optional[str] = None
    direcao: Optional[str] = None  # 'credito' ou 'debito'
    contraparte: Optional[str] = None
    documento: Optional[str] = None
    valor: Optional[float] = None
    observacao: Optional[str] = None


@dataclass
class NarrativaProcessada:
    """Resultado completo do processamento da narrativa."""
    dados_cadastrais: DadosCadastrais = field(default_factory=DadosCadastrais)
    dados_financeiros: DadosFinanceiros = field(default_factory=DadosFinanceiros)
    historico_pld: List[str] = field(default_factory=list)
    historico_fraude: Optional[str] = None
    peps_relacionados: List[PEPRelacionado] = field(default_factory=list)
    contrapartes_credito: List[Contraparte] = field(default_factory=list)
    contrapartes_debito: List[Contraparte] = field(default_factory=list)
    transacoes_suspeitas: List[TransacaoSuspeita] = field(default_factory=list)
    total_creditos: Optional[float] = None
    total_debitos: Optional[float] = None
    periodo_analisado: Optional[str] = None
    alertas: List[Alerta] = field(default_factory=list)
    parecer: Optional[str] = None
    notas: List[str] = field(default_factory=list)
    texto_limpo: Optional[str] = None


# =============================================================================
# FUNÇÕES DE PRÉ-PROCESSAMENTO
# =============================================================================

def limpar_caracteres_especiais(texto: str) -> str:
    """
    Remove caracteres especiais e normaliza o texto.
    Resolve problemas de escape sequences.
    """
    if not texto:
        return ""
    
    # Converter para string se necessário
    texto = str(texto)
    
    # Remover caracteres de controle (exceto quebra de linha)
    texto = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', texto)
    
    # Normalizar barras invertidas duplicadas
    texto = texto.replace('\\\\', '\\')
    
    # Remover caracteres nulos
    texto = texto.replace('\x00', '')
    
    # Normalizar espaços múltiplos
    texto = re.sub(r'\s+', ' ', texto)
    
    # Remover espaços no início e fim
    texto = texto.strip()
    
    return texto


def normalizar_texto(texto: str) -> str:
    """
    Normaliza o texto mantendo acentos mas removendo caracteres problemáticos.
    """
    if not texto:
        return ""
    
    # Normalização Unicode (NFD -> NFC)
    texto = unicodedata.normalize('NFC', texto)
    
    # Substituir caracteres problemáticos
    replacements = {
        '\u2013': '-',  # en-dash
        '\u2014': '-',  # em-dash
        '\u2018': "'",  # left single quote
        '\u2019': "'",  # right single quote
        '\u201c': '"',  # left double quote
        '\u201d': '"',  # right double quote
        '\u2026': '...',  # ellipsis
        '\u00a0': ' ',  # non-breaking space
    }
    
    for old, new in replacements.items():
        texto = texto.replace(old, new)
    
    return texto


def formatar_cpf(cpf: str) -> str:
    """Formata CPF no padrão XXX.XXX.XXX-XX."""
    cpf = re.sub(r'[^\d]', '', str(cpf))
    if len(cpf) == 11:
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    return cpf


def formatar_cnpj(cnpj: str) -> str:
    """Formata CNPJ no padrão XX.XXX.XXX/XXXX-XX."""
    cnpj = re.sub(r'[^\d]', '', str(cnpj))
    if len(cnpj) == 14:
        return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    return cnpj


def limpar_documento(doc: str) -> str:
    """Remove formatação do documento, retorna apenas números."""
    return re.sub(r'[^\d]', '', str(doc)) if doc else ""


def detectar_tipo_documento(doc: str) -> str:
    """Detecta se é CPF ou CNPJ baseado no tamanho."""
    doc_limpo = limpar_documento(doc)
    return 'CNPJ' if len(doc_limpo) == 14 else 'CPF'


def validar_valor_monetario(valor_str: str) -> Optional[float]:
    """
    Valida e converte valor monetário no padrão brasileiro.
    Formato esperado: R$ 9.999.999,99 ou 9.999.999,99
    """
    if not valor_str:
        return None
    
    try:
        # Remover R$ e espaços
        limpo = valor_str.replace('R$', '').strip()
        
        # Verificar se está no formato brasileiro (ponto como separador de milhares)
        # Padrão: dígitos, opcionalmente pontos como separadores, vírgula como decimal
        match = PADRAO_VALOR_BR.search(limpo)
        
        if match:
            valor_formatado = match.group(1)
            # Remover pontos (separador de milhares) e trocar vírgula por ponto
            valor_numerico = valor_formatado.replace('.', '').replace(',', '.')
            return float(valor_numerico)
        
        # Fallback: tentar conversão direta
        limpo = limpo.replace('.', '').replace(',', '.').strip()
        return float(limpo)
        
    except (ValueError, AttributeError):
        return None


def formatar_valor(valor: float) -> str:
    """Formata valor monetário para exibição no padrão brasileiro."""
    if valor is None:
        return "N/A"
    return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def validar_cpf(cpf: str) -> bool:
    """Valida CPF verificando dígitos verificadores."""
    cpf = limpar_documento(cpf)
    if len(cpf) != 11:
        return False
    
    # Verificar se todos os dígitos são iguais
    if cpf == cpf[0] * 11:
        return False
    
    # Calcular primeiro dígito verificador
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    digito1 = (soma * 10 % 11) % 10
    
    # Calcular segundo dígito verificador
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    digito2 = (soma * 10 % 11) % 10
    
    return digito1 == int(cpf[9]) and digito2 == int(cpf[10])


def validar_cnpj(cnpj: str) -> bool:
    """Valida CNPJ verificando dígitos verificadores."""
    cnpj = limpar_documento(cnpj)
    if len(cnpj) != 14:
        return False
    
    # Verificar se todos os dígitos são iguais
    if cnpj == cnpj[0] * 14:
        return False
    
    # Pesos para cálculo
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    
    # Calcular primeiro dígito verificador
    soma = sum(int(cnpj[i]) * pesos1[i] for i in range(12))
    digito1 = soma % 11
    digito1 = 0 if digito1 < 2 else 11 - digito1
    
    # Calcular segundo dígito verificador
    soma = sum(int(cnpj[i]) * pesos2[i] for i in range(13))
    digito2 = soma % 11
    digito2 = 0 if digito2 < 2 else 11 - digito2
    
    return digito1 == int(cnpj[12]) and digito2 == int(cnpj[13])


# =============================================================================
# EXTRATOR PRINCIPAL
# =============================================================================

class NarrativeExtractor:
    """Extrator de informações estruturadas de narrativas RIF."""
    
    def __init__(self):
        """Inicializa o extrator com padrões regex compilados."""
        # Compilar padrões para melhor performance
        self._compilar_padroes()
    
    def _compilar_padroes(self):
        """Compila todos os padrões regex usados na extração."""
        # Dados cadastrais
        self.padrao_profissao = re.compile(
            r'Consta atuar como ([^,]+)',
            re.IGNORECASE
        )
        self.padrao_renda_mensal = re.compile(
            r'renda\s+mensal\s+de\s+R?\$?\s*([\d.,]+)',
            re.IGNORECASE
        )
        self.padrao_conjuge = re.compile(
            r'cônjuge[,:\s]+([^,]+),?\s*CPF\s*(\d{3}\.?\d{3}\.?\d{3}-?\d{2})',
            re.IGNORECASE
        )
        self.padrao_socio_empresa = re.compile(
            r's[óo]cio da empresa[:\s]+([^,]+),?\s*CNPJ\s*(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})',
            re.IGNORECASE
        )
        
        # Totais
        self.padrao_total_creditos = re.compile(
            r'(?:os\s+)?cr[eé]ditos?\s+somaram\s+(?:R\$)?\s*([\d.,]+)',
            re.IGNORECASE
        )
        self.padrao_total_debitos = re.compile(
            r'd[eé]bitos?.*?totalizaram\s+(?:R\$)?\s*([\d.,]+)',
            re.IGNORECASE
        )
        
        # Período
        self.padrao_periodo = re.compile(
            r'Entre\s+(\d{2}\.\d{2}\.\d{4})\s+e\s+(\d{2}\.\d{2}\.\d{4})',
            re.IGNORECASE
        )
        
        # Contrapartes - formato tabela compacta
        self.padrao_contraparte = re.compile(
            r'([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})\s+'  # valor
            r'(\d+)\s+'                                    # quantidade
            r'([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\.]+?)\s+'          # nome
            r'(\d{3}\.?\d{3}\.?\d{3}-?\d{2}|\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})',  # doc
            re.IGNORECASE
        )
        
        # Transações suspeitas
        self.padrao_transacao_suspeita = re.compile(
            r'(\d{2}\.\d{2}\.\d{4})\s+'                   # data
            r'(PIX|TED|DOC|Transferência)[^ ]*\s*-\s*'     # tipo
            r'(Cr[eé]dito|D[eé]bito)\s+'                   # direção
            r'([^0-9]+?)\s+'                               # nome
            r'(\d{3}\.?\d{3}\.?\d{3}-?\d{2}|\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})\s+'  # doc
            r'([\d.,]+)',                                  # valor
            re.IGNORECASE
        )
        
        # CPF/CNPJ gerais
        self.padrao_cpf = re.compile(
            r'(\d{3}\.?\d{3}\.?\d{3}-?\d{2})'
        )
        self.padrao_cnpj = re.compile(
            r'(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})'
        )
        
        # Comunicados
        self.padrao_comunicado = re.compile(
            r'Comunicado[^\d]*(\d{2}/\d{4}|\d{2}/\d{2}/\d{4})[^\d]*(\d+)?\s*ocorr',
            re.IGNORECASE
        )
    
    def preprocessar(self, texto: str) -> str:
        """
        Pré-processa o texto da narrativa.
        - Remove caracteres especiais problemáticos
        - Normaliza formatação
        - Mantém dados importantes
        """
        if not texto or (isinstance(texto, float) and pd.isna(texto)):
            return ""
        
        # Converter para string
        texto = str(texto)
        
        # Normalizar caracteres especiais
        texto = normalizar_texto(texto)
        
        # Limpar caracteres de controle
        texto = limpar_caracteres_especiais(texto)
        
        # Normalizar CPFs e CNPJs para formato padrão
        texto = self._normalizar_documentos_texto(texto)
        
        return texto
    
    def _normalizar_documentos_texto(self, texto: str) -> str:
        """Normaliza CPFs e CNPJs no texto para formato padrão."""
        # Normalizar CPFs
        def formatar_cpf_match(match):
            cpf = match.group(0)
            return formatar_cpf(cpf)
        
        # Normalizar CNPJs
        def formatar_cnpj_match(match):
            cnpj = match.group(0)
            return formatar_cnpj(cnpj)
        
        # Aplicar formatação
        texto = self.padrao_cnpj.sub(formatar_cnpj_match, texto)
        texto = self.padrao_cpf.sub(formatar_cpf_match, texto)
        
        return texto
    
    def processar(self, narrativa: str) -> NarrativaProcessada:
        """Processa uma narrativa completa e retorna dados estruturados."""
        resultado = NarrativaProcessada()
        
        # Pré-processar texto
        texto = self.preprocessar(narrativa)
        resultado.texto_limpo = texto
        
        if not texto:
            return resultado
        
        # Detectar formato
        formato = self._detectar_formato(texto)
        
        # Processar cada seção
        resultado.dados_cadastrais = self._extrair_dados_cadastrais(texto, formato)
        resultado.dados_financeiros = self._extrair_dados_financeiros(texto, formato)
        resultado.historico_pld = self._extrair_historico_pld(texto)
        resultado.historico_fraude = self._extrair_historico_fraude(texto)
        resultado.peps_relacionados = self._extrair_peps(texto, formato)
        resultado.contrapartes_credito = self._extrair_contrapartes_credito(texto)
        resultado.contrapartes_debito = self._extrair_contrapartes_debito(texto)
        resultado.transacoes_suspeitas = self._extrair_transacoes_suspeitas(texto)
        resultado.total_creditos = self._extrair_total_creditos(texto)
        resultado.total_debitos = self._extrair_total_debitos(texto)
        resultado.periodo_analisado = self._extrair_periodo(texto)
        resultado.notas = self._extrair_notas(texto)
        resultado.alertas = self._identificar_alertas(texto, resultado)
        resultado.parecer = self._extrair_parecer(texto)
        
        return resultado
    
    def _detectar_formato(self, texto: str) -> str:
        """Detecta o formato da narrativa."""
        if re.search(r'Nome:\s*[A-Z]', texto) and re.search(r'CPF:\s*\d', texto):
            return 'estruturado'
        return 'livre'
    
    def _extrair_dados_cadastrais(self, texto: str, formato: str) -> DadosCadastrais:
        """Extrai dados cadastrais da pessoa."""
        dados = DadosCadastrais()
        
        if formato == 'livre':
            # Profissão/atividade
            match = self.padrao_profissao.search(texto)
            if match:
                dados.profissao = match.group(1).strip()
            
            # Cônjuge
            match = self.padrao_conjuge.search(texto)
            if match:
                dados.conjuge_nome = match.group(1).strip()
                dados.conjuge_cpf = formatar_cpf(match.group(2))
            
            # Empresas como sócio
            for match in self.padrao_socio_empresa.finditer(texto):
                empresa = match.group(1).strip()
                cnpj = formatar_cnpj(match.group(2))
                dados.empresas_socio.append({
                    'nome': empresa,
                    'cnpj': cnpj,
                    'cnpj_valido': validar_cnpj(cnpj)
                })
        
        # Email (qualquer formato)
        email_match = re.search(r'[\w.-]+@[\w.-]+\.\w+', texto)
        if email_match:
            dados.email = email_match.group(0)
        
        # CEP
        cep_match = re.search(r'CEP[:\s]*(\d{5})-?(\d{3})', texto, re.IGNORECASE)
        if cep_match:
            dados.cep = f"{cep_match.group(1)}-{cep_match.group(2)}"
        
        return dados
    
    def _extrair_dados_financeiros(self, texto: str, formato: str) -> DadosFinanceiros:
        """Extrai dados financeiros."""
        dados = DadosFinanceiros()
        
        # Renda mensal
        match = self.padrao_renda_mensal.search(texto)
        if match:
            dados.renda = validar_valor_monetario(match.group(1))
        
        # Patrimônio (formato estruturado)
        pat_match = re.search(r'Patrim[oô]nio:\s*(\d+)\s*[-–]\s*(\d+)', texto, re.IGNORECASE)
        if pat_match:
            dados.patrimonio_min = float(pat_match.group(1))
            dados.patrimonio_max = float(pat_match.group(2))
            dados.patrimonio = f"{pat_match.group(1)} - {pat_match.group(2)}"
        
        return dados
    
    def _extrair_historico_pld(self, texto: str) -> List[str]:
        """Extrai histórico de PLD/FT."""
        historico = []
        
        # Recibos SISCOAF
        recibos = re.findall(r'recibo\s*(\d+)[^\d]*(\d{2}/\d{2}/\d{4})?', texto, re.IGNORECASE)
        for recibo, data in recibos:
            entrada = f"Recibo SISCOAF: {recibo}"
            if data:
                entrada += f" em {data}"
            historico.append(entrada)
        
        # Comunicados
        for match in self.padrao_comunicado.finditer(texto):
            data, qtd = match.groups()
            qtd = qtd or '1'
            historico.append(f"Comunicado em {data} - {qtd} ocorrência(s)")
        
        return list(set(historico))
    
    def _extrair_historico_fraude(self, texto: str) -> Optional[str]:
        """Extrai histórico de fraude."""
        match = re.search(r'Hist[oó]rico\s+de\s+Fraude:\s*(Sem histórico relevante|[^\n]+)', texto, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None
    
    def _extrair_peps(self, texto: str, formato: str) -> List[PEPRelacionado]:
        """Extrai PEPs relacionados."""
        peps = []
        
        pep_blocos = re.split(r'(?=-\s*Nome\s+PEP\s+titular:)', texto)
        
        for bloco in pep_blocos:
            if 'PEP titular' not in bloco:
                continue
            
            pep = PEPRelacionado()
            
            nome_match = re.search(r'Nome\s+PEP\s+titular:\s*([^\n\-–]+)', bloco, re.IGNORECASE)
            if nome_match:
                pep.nome = nome_match.group(1).strip()
            
            cargo_match = re.search(r'Cargo\s+PEP\s+titular:\s*([^\n\-–]+)', bloco, re.IGNORECASE)
            if cargo_match:
                pep.cargo = cargo_match.group(1).strip()
            
            carencia_match = re.search(r'Car[eê]ncia\s+PEP\s+titular:\s*([^\n\-–]+)', bloco, re.IGNORECASE)
            if carencia_match:
                pep.carencia = carencia_match.group(1).strip()
            
            tipo_match = re.search(r'Tipo\s+de\s+relacionamento:\s*([^\n\-–]+)', bloco, re.IGNORECASE)
            if tipo_match:
                pep.tipo_relacionamento = tipo_match.group(1).strip()
            
            midia_match = re.search(r'Pep\s+titular\s+possui\s+m[ií]dia:\s*(Sim|N[aã]o)', bloco, re.IGNORECASE)
            if midia_match:
                pep.possui_midia = midia_match.group(1).lower() == 'sim'
            
            resumo_match = re.search(r'Resumo\s+m[ií]dia\s+PEP\s+titular:\s*(.+?)(?=-\s*Nome\s+PEP|https?://|\n\s*-)', 
                                    bloco, re.IGNORECASE | re.DOTALL)
            if resumo_match:
                pep.resumo_midia = resumo_match.group(1).strip()[:500]
            
            if pep.nome:
                peps.append(pep)
        
        return peps
    
    def _extrair_contrapartes_credito(self, texto: str) -> List[Contraparte]:
        """Extrai contrapartes de crédito."""
        contrapartes = []
        
        # Buscar seção de remetentes (créditos)
        secao_match = re.search(
            r'Demonstramos os principais (?:depositantes e )?remetentes:.*?(?=Os d[eé]bitos|$)',
            texto, re.IGNORECASE | re.DOTALL
        )
        
        if secao_match:
            texto_secao = secao_match.group(0)
            contrapartes = self._extrair_contrapartes_tabela(texto_secao)
        
        # Se não encontrou, tentar formato estruturado
        if not contrapartes:
            contrapartes = self._extrair_contrapartes_estruturado(texto, 'credito')
        
        return contrapartes
    
    def _extrair_contrapartes_debito(self, texto: str) -> List[Contraparte]:
        """Extrai contrapartes de débito."""
        contrapartes = []
        
        # Buscar seção de favorecidos (débitos)
        secao_match = re.search(
            r'Demonstramos os principais favorecidos:.*?(?=Notas:|- Demonstramos por|-Demonstramos|Parecer|$)',
            texto, re.IGNORECASE | re.DOTALL
        )
        
        if secao_match:
            texto_secao = secao_match.group(0)
            contrapartes = self._extrair_contrapartes_tabela(texto_secao)
        
        # Se não encontrou, tentar formato estruturado
        if not contrapartes:
            contrapartes = self._extrair_contrapartes_estruturado(texto, 'debito')
        
        return contrapartes
    
    def _extrair_contrapartes_tabela(self, texto_secao: str) -> List[Contraparte]:
        """Extrai contrapartes de uma tabela no formato compacto."""
        contrapartes = []
        
        for match in self.padrao_contraparte.finditer(texto_secao):
            cp = Contraparte()
            
            # Valor monetário
            valor_str = match.group(1)
            cp.valor = validar_valor_monetario(valor_str)
            
            # Quantidade de transações
            cp.qtd_transacoes = int(match.group(2))
            
            # Nome
            cp.nome = match.group(3).strip()
            
            # Documento
            doc = match.group(4)
            cp.documento = limpar_documento(doc)
            cp.tipo_documento = detectar_tipo_documento(doc)
            
            # Validar documento
            if cp.tipo_documento == 'CPF':
                cp.documento = formatar_cpf(doc)
            else:
                cp.documento = formatar_cnpj(doc)
            
            # Buscar banco e comunicados após o match
            pos = match.end()
            proximo = self.padrao_contraparte.search(texto_secao, pos)
            texto_info = texto_secao[pos:proximo.start() if proximo else len(texto_secao)]
            
            # Extrair banco (texto antes de "Comunicado" ou próximo número)
            banco_match = re.search(r'^([^0-9]+?)(?=Comunicado|[\d]{1,3}[.,][\d]{2}|$)', texto_info.strip())
            if banco_match:
                cp.banco = banco_match.group(1).strip()[:50]
            
            # Extrair comunicados
            for com_match in self.padrao_comunicado.finditer(texto_info):
                cp.comunicados.append(com_match.group(0).strip())
            
            # Adicionar apenas se tiver dados válidos
            if cp.nome and len(cp.nome) > 3 and cp.valor:
                contrapartes.append(cp)
        
        return contrapartes
    
    def _extrair_contrapartes_estruturado(self, texto: str, tipo: str) -> List[Contraparte]:
        """Extrai contrapartes no formato estruturado RIF."""
        contrapartes = []
        
        if tipo == 'credito':
            secao_match = re.search(
                r'Origem\s+dos\s+cr[eé]ditos.*?(?=-\s*Total\s+dos\s+d[eé]bitos|Destino\s+dos\s+d[eé]bitos)',
                texto, re.IGNORECASE | re.DOTALL
            )
        else:
            secao_match = re.search(
                r'Destino\s+dos\s+d[eé]bitos.*?(?=Parecer:|$)',
                texto, re.IGNORECASE | re.DOTALL
            )
        
        if not secao_match:
            return contrapartes
        
        texto_secao = secao_match.group(0)
        
        # Padrão estruturado: "- XX,XX% (R$ valor em N transação(ões)) via CPF/CNPJ DOC (NOME)"
        pattern = re.compile(
            r'-\s*([\d,]+)\s*%\s*\('           # percentual
            r'R?\$?\s*([\d.,]+)'               # valor
            r'.*?(\d+)\s+transa'               # quantidade
            r'.*?\)\s*(?:para\s+)?(?:via\s+)?' # fecha parenteses
            r'(CPF|CNPJ)?\s*(\d+)\s*\('        # tipo e numero doc
            r'([^)]+)\)',                      # nome
            re.IGNORECASE | re.DOTALL
        )
        
        for match in pattern.finditer(texto_secao):
            cp = Contraparte()
            cp.percentual = float(match.group(1).replace(',', '.'))
            cp.valor = validar_valor_monetario(match.group(2))
            cp.qtd_transacoes = int(match.group(3))
            cp.tipo_documento = (match.group(4) or 'DOC').upper()
            cp.documento = match.group(5)
            cp.nome = match.group(6).strip()
            
            contrapartes.append(cp)
        
        return contrapartes
    
    def _extrair_transacoes_suspeitas(self, texto: str) -> List[TransacaoSuspeita]:
        """Extrai transações com características suspeitas."""
        transacoes = []
        
        # Buscar seção de transações suspeitas
        secao_match = re.search(
            r'recebimento\s+de\s+recursos\s+com\s+d[eé]bito\s+imediato.*?(?=-\s*Mediante|Cliente trabalha|$)',
            texto, re.IGNORECASE | re.DOTALL
        )
        
        if secao_match:
            texto_secao = secao_match.group(0)
            
            for match in self.padrao_transacao_suspeita.finditer(texto_secao):
                tx = TransacaoSuspeita()
                tx.data = match.group(1)
                tx.tipo = match.group(2).upper()
                tx.direcao = 'credito' if 'credito' in match.group(3).lower() else 'debito'
                tx.contraparte = match.group(4).strip()
                tx.documento = formatar_cpf(match.group(5)) if len(limpar_documento(match.group(5))) == 11 else formatar_cnpj(match.group(5))
                tx.valor = validar_valor_monetario(match.group(6))
                
                # Buscar comunicado associado
                pos = match.end()
                proximo = self.padrao_transacao_suspeita.search(texto_secao, pos)
                texto_info = texto_secao[pos:proximo.start() if proximo else len(texto_secao)]
                
                com_match = self.padrao_comunicado.search(texto_info)
                if com_match:
                    tx.observacao = com_match.group(0).strip()
                
                transacoes.append(tx)
        
        return transacoes
    
    def _extrair_total_creditos(self, texto: str) -> Optional[float]:
        """Extrai total de créditos."""
        match = self.padrao_total_creditos.search(texto)
        if match:
            return validar_valor_monetario(match.group(1))
        
        # Formato estruturado
        match = re.search(r'Total\s+dos\s+cr[eé]ditos:\s*(?:R\$)?\s*([\d.,]+)', texto, re.IGNORECASE)
        if match:
            return validar_valor_monetario(match.group(1))
        
        return None
    
    def _extrair_total_debitos(self, texto: str) -> Optional[float]:
        """Extrai total de débitos."""
        match = self.padrao_total_debitos.search(texto)
        if match:
            return validar_valor_monetario(match.group(1))
        
        # Formato estruturado
        match = re.search(r'Total\s+dos\s+d[eé]bitos:\s*(?:R\$)?\s*([\d.,]+)', texto, re.IGNORECASE)
        if match:
            return validar_valor_monetario(match.group(1))
        
        return None
    
    def _extrair_periodo(self, texto: str) -> Optional[str]:
        """Extrai período analisado."""
        match = self.padrao_periodo.search(texto)
        if match:
            return f"{match.group(1)} a {match.group(2)}"
        
        # Formato estruturado
        match = re.search(
            r'Per[ií]odo\s+analisado:?\s*[^\d]*(\d{2}/\d{2}/\d{4})\s*a\s*(\d{2}/\d{2}/\d{4})',
            texto, re.IGNORECASE
        )
        if match:
            return f"{match.group(1)} a {match.group(2)}"
        
        return None
    
    def _extrair_notas(self, texto: str) -> List[str]:
        """Extrai notas da narrativa."""
        notas = []
        
        # Buscar seção de notas
        notas_match = re.search(r'Notas:\s*(.+?)(?=Diante do exposto|$)', texto, re.IGNORECASE | re.DOTALL)
        if notas_match:
            secao = notas_match.group(1)
            
            # Dividir por hífen no início
            itens = re.split(r'\s*-\s+', secao)
            for item in itens:
                item = item.strip()
                if item and len(item) > 15 and 'Demonstramos' not in item[:15]:
                    # Limpar e adicionar
                    item = item[:200]  # Limitar tamanho
                    notas.append(item)
        
        return notas
    
    def _identificar_alertas(self, texto: str, resultado: NarrativaProcessada) -> List[Alerta]:
        """Identifica alertas na narrativa."""
        alertas = []
        
        # 1. Movimentação superior à capacidade financeira
        if re.search(r'movimenta[cç][aã]o[^.]*superior[^.]*capacidade\s+financeira', texto, re.IGNORECASE):
            alertas.append(Alerta(
                tipo="Incompatibilidade Financeira",
                descricao="Movimentação superior à capacidade financeira declarada",
                severidade="alta"
            ))
        
        # 2. Movimentações em benefício de terceiros
        if re.search(r'movimenta[cç][õo]es\s+em\s+benef[ií]cio\s+de\s+terceiros', texto, re.IGNORECASE):
            alertas.append(Alerta(
                tipo="Movimentação para Terceiros",
                descricao="Indícios de movimentações em benefício de terceiros, sem aparente causa",
                severidade="alta"
            ))
        
        # 3. Créditos com débito imediato (pass-through)
        if re.search(r'cr[eé]ditos?\s+com\s+(?:o\s+)?imediato\s+d[eé]bito', texto, re.IGNORECASE):
            alertas.append(Alerta(
                tipo="Pass-Through",
                descricao="Recebimento de créditos com débito imediato dos valores",
                severidade="alta"
            ))
        
        # 4. Transações suspeitas identificadas
        if resultado.transacoes_suspeitas:
            alertas.append(Alerta(
                tipo="Transações Suspeitas",
                descricao=f"{len(resultado.transacoes_suspeitas)} transação(ões) com débito imediato sem causa aparente",
                severidade="alta"
            ))
        
        # 5. Mídia negativa titular
        if re.search(r'M[ií]dia\s+(?:Negativa\s+)?[^:]*:\s*Sim', texto, re.IGNORECASE):
            alertas.append(Alerta(
                tipo="Mídia Negativa",
                descricao="Titular possui menções negativas em mídia",
                severidade="alta"
            ))
        
        # 6. PEPs
        if len(resultado.peps_relacionados) >= 5:
            alertas.append(Alerta(
                tipo="Múltiplos PEPs",
                descricao=f"Titular relacionado com {len(resultado.peps_relacionados)} PEPs",
                severidade="alta"
            ))
        elif len(resultado.peps_relacionados) >= 1:
            alertas.append(Alerta(
                tipo="Relacionamento PEP",
                descricao=f"Titular relacionado com {len(resultado.peps_relacionados)} PEP(s)",
                severidade="media"
            ))
        
        # 7. Reincidência PLD
        if resultado.historico_pld:
            alertas.append(Alerta(
                tipo="Reincidência PLD",
                descricao="Cliente já foi reportado anteriormente ao COAF",
                severidade="media"
            ))
        
        # 8. Incompatibilidade financeira (por cálculo)
        if resultado.dados_financeiros.renda and resultado.total_creditos:
            ratio = resultado.total_creditos / resultado.dados_financeiros.renda
            if ratio > 10:
                alertas.append(Alerta(
                    tipo="Incompatibilidade Financeira",
                    descricao=f"Créditos ({formatar_valor(resultado.total_creditos)}) excedem {ratio:.1f}x a renda declarada",
                    severidade="alta"
                ))
        
        # 9. Contrapartes com mídia negativa
        cps_midia = [cp for cp in resultado.contrapartes_credito + resultado.contrapartes_debito if cp.possui_midia]
        if cps_midia:
            alertas.append(Alerta(
                tipo="Contrapartes com Mídia Negativa",
                descricao=f"{len(cps_midia)} contraparte(s) com menções negativas",
                severidade="media"
            ))
        
        # 10. Região de risco
        cps_risco = [cp for cp in resultado.contrapartes_credito + resultado.contrapartes_debito 
                     if cp.regiao_fronteira or cp.amazonia_legal]
        if cps_risco:
            alertas.append(Alerta(
                tipo="Região de Risco",
                descricao=f"{len(cps_risco)} contraparte(s) em região de fronteira/Amazônia Legal",
                severidade="media"
            ))
        
        # 11. Fragmentação
        total_cp = len(resultado.contrapartes_credito) + len(resultado.contrapartes_debito)
        if total_cp > 20:
            alertas.append(Alerta(
                tipo="Fragmentação",
                descricao=f"Alta fragmentação: {total_cp} contrapartes identificadas",
                severidade="media"
            ))
        
        # 12. Licitações (específico)
        if re.search(r'licita[cç][õo]es?\s+para\s+[oó]rg[aã]os?\s+p[uú]blicos?', texto, re.IGNORECASE):
            alertas.append(Alerta(
                tipo="Licitações Públicas",
                descricao="Cliente atua em licitações para órgãos públicos",
                severidade="media"
            ))
        
        # 13. Espécie
        if re.search(r'(?:depositados|sacados|efetuados)\s+em\s+esp[eé]cie', texto, re.IGNORECASE):
            alertas.append(Alerta(
                tipo="Movimentação em Espécie",
                descricao="Movimentações em espécie identificadas",
                severidade="media"
            ))
        
        return alertas
    
    def _extrair_parecer(self, texto: str) -> Optional[str]:
        """Extrai parecer final."""
        match = re.search(r'Diante do exposto,?\s*identificamos\s+que:\s*(.+?)$', texto, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        
        match = re.search(r'Parecer:\s*(.+?)$', texto, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        
        return None


# =============================================================================
# EXIBIÇÃO
# =============================================================================

def exibir_resultado(resultado: NarrativaProcessada):
    """Exibe resultado formatado."""
    
    print("\n" + "="*80)
    print("📋 NARRATIVA PROCESSADA")
    print("="*80)
    
    # Dados cadastrais
    print("\n┌" + "─"*78 + "┐")
    print("│ 📝 DADOS CADASTRAIS                                                         │")
    print("├" + "─"*78 + "┤")
    dc = resultado.dados_cadastrais
    if dc.profissao: print(f"│ Profissão/Atividade: {dc.profissao:<53} │")
    if dc.nome: print(f"│ Nome:            {dc.nome:<58} │")
    if dc.cpf: print(f"│ CPF:             {dc.cpf:<58} │")
    if dc.cnpj: print(f"│ CNPJ:            {dc.cnpj:<58} │")
    if dc.idade: print(f"│ Idade:           {dc.idade} anos{' '*52}│")
    if dc.estado_civil: print(f"│ Estado Civil:    {dc.estado_civil:<58} │")
    if dc.email: print(f"│ Email:           {dc.email:<58} │")
    if dc.endereco: print(f"│ Endereço:        {dc.endereco[:55]+'...' if len(dc.endereco)>58 else dc.endereco:<58} │")
    if dc.conjuge_nome: 
        print(f"│ Cônjuge:         {dc.conjuge_nome:<58} │")
        if dc.conjuge_cpf:
            print(f"│ CPF Cônjuge:     {dc.conjuge_cpf:<58} │")
    if dc.empresas_socio:
        print(f"│ Empresas como Sócio: {len(dc.empresas_socio)} empresa(s){' '*42} │")
        for emp in dc.empresas_socio[:3]:
            status = "✓" if emp.get('cnpj_valido', True) else "⚠"
            print(f"│   {status} {emp['nome'][:48]:<48} │")
    print("└" + "─"*78 + "┘")
    
    # Dados financeiros
    print("\n┌" + "─"*78 + "┐")
    print("│ 💰 DADOS FINANCEIROS                                                        │")
    print("├" + "─"*78 + "┤")
    df = resultado.dados_financeiros
    if df.renda: print(f"│ Renda Declarada: {formatar_valor(df.renda):<55} │")
    if df.patrimonio: print(f"│ Patrimônio:      {df.patrimonio:<45} │")
    if resultado.periodo_analisado: print(f"│ Período:         {resultado.periodo_analisado:<58} │")
    print("└" + "─"*78 + "┘")
    
    # Totais
    print("\n┌" + "─"*78 + "┐")
    print("│ 📊 TOTAIS                                                                   │")
    print("├" + "─"*78 + "┤")
    if resultado.total_creditos: print(f"│ Total Créditos:  {formatar_valor(resultado.total_creditos):<55} │")
    if resultado.total_debitos: print(f"│ Total Débitos:   {formatar_valor(resultado.total_debitos):<55} │")
    print("└" + "─"*78 + "┘")
    
    # Histórico PLD
    if resultado.historico_pld:
        print("\n┌" + "─"*78 + "┐")
        print("│ 📊 HISTÓRICO PLD/FT                                                         │")
        print("├" + "─"*78 + "┤")
        for h in resultado.historico_pld[:5]:
            print(f"│   • {h:<71} │")
        print("└" + "─"*78 + "┘")
    
    # PEPs
    if resultado.peps_relacionados:
        print("\n┌" + "─"*78 + "┐")
        print(f"│ 👥 PEPs RELACIONADOS ({len(resultado.peps_relacionados)})                                                  │")
        print("├" + "─"*78 + "┤")
        for i, pep in enumerate(resultado.peps_relacionados[:10], 1):
            nome = (pep.nome or "N/A")[:40]
            cargo = (pep.cargo or "N/A")[:50]
            print(f"│ {i:2}. {nome:<40} │")
            print(f"│     Cargo: {cargo:<63} │")
            if pep.possui_midia:
                print(f"│     ⚠️  Possui mídia negativa{' '*47} │")
            if i < min(len(resultado.peps_relacionados), 10):
                print("│     " + "─"*72 + " │")
        if len(resultado.peps_relacionados) > 10:
            print(f"│     ... e mais {len(resultado.peps_relacionados)-10} PEP(s){' '*45} │")
        print("└" + "─"*78 + "┘")
    
    # Contrapartes crédito
    if resultado.contrapartes_credito:
        print("\n┌" + "─"*78 + "┐")
        print(f"│ 📥 CONTRAPARTES DE CRÉDITO ({len(resultado.contrapartes_credito)})                                          │")
        print("├" + "─"*78 + "┤")
        for i, cp in enumerate(resultado.contrapartes_credito[:15], 1):
            nome = (cp.nome or "N/A")[:35]
            valor = formatar_valor(cp.valor) if cp.valor else "N/A"
            print(f"│ {i:2}. {nome:<35} {valor:>18} │")
            doc = f"{cp.tipo_documento}: {cp.documento}" if cp.documento else ""
            banco = (cp.banco or "")[:30]
            print(f"│     {doc:<35} {banco:<35} │")
            if cp.comunicados:
                for com in cp.comunicados[:1]:
                    com_display = com[:60] if len(com) > 60 else com
                    print(f"│     📋 {com_display:<60} │")
            if i < min(len(resultado.contrapartes_credito), 15):
                print("│     " + "─"*72 + " │")
        if len(resultado.contrapartes_credito) > 15:
            print(f"│     ... e mais {len(resultado.contrapartes_credito)-15}{' '*47} │")
        print("└" + "─"*78 + "┘")
    
    # Contrapartes débito
    if resultado.contrapartes_debito:
        print("\n┌" + "─"*78 + "┐")
        print(f"│ 📤 CONTRAPARTES DE DÉBITO ({len(resultado.contrapartes_debito)})                                           │")
        print("├" + "─"*78 + "┤")
        for i, cp in enumerate(resultado.contrapartes_debito[:15], 1):
            nome = (cp.nome or "N/A")[:35]
            valor = formatar_valor(cp.valor) if cp.valor else "N/A"
            print(f"│ {i:2}. {nome:<35} {valor:>18} │")
            doc = f"{cp.tipo_documento}: {cp.documento}" if cp.documento else ""
            banco = (cp.banco or "")[:30]
            print(f"│     {doc:<35} {banco:<35} │")
            if cp.comunicados:
                for com in cp.comunicados[:1]:
                    com_display = com[:60] if len(com) > 60 else com
                    print(f"│     📋 {com_display:<60} │")
            if i < min(len(resultado.contrapartes_debito), 15):
                print("│     " + "─"*72 + " │")
        if len(resultado.contrapartes_debito) > 15:
            print(f"│     ... e mais {len(resultado.contrapartes_debito)-15}{' '*47} │")
        print("└" + "─"*78 + "┘")
    
    # Transações suspeitas
    if resultado.transacoes_suspeitas:
        print("\n┌" + "─"*78 + "┐")
        print(f"│ ⚠️  TRANSAÇÕES SUSPEITAS ({len(resultado.transacoes_suspeitas)})                                             │")
        print("├" + "─"*78 + "┤")
        for i, tx in enumerate(resultado.transacoes_suspeitas[:10], 1):
            direcao = "↑ CRÉDITO" if tx.direcao == 'credito' else "↓ DÉBITO "
            valor = formatar_valor(tx.valor) if tx.valor else "N/A"
            print(f"│ {i:2}. {tx.data or 'N/A':<12} {tx.tipo:<6} {direcao:<10} {valor:>18} │")
            contraparte = tx.contraparte[:40] if tx.contraparte else ""
            print(f"│     {contraparte:<40} │")
            if i < min(len(resultado.transacoes_suspeitas), 10):
                print("│     " + "─"*72 + " │")
        if len(resultado.transacoes_suspeitas) > 10:
            print(f"│     ... e mais {len(resultado.transacoes_suspeitas)-10}{' '*47} │")
        print("└" + "─"*78 + "┘")
    
    # Alertas
    if resultado.alertas:
        print("\n┌" + "─"*78 + "┐")
        print(f"│ 🚨 ALERTAS IDENTIFICADOS ({len(resultado.alertas)})                                             │")
        print("├" + "─"*78 + "┤")
        ordem = {'alta': 1, 'media': 2, 'baixa': 3}
        for alerta in sorted(resultado.alertas, key=lambda x: ordem.get(x.severidade, 3)):
            icone = "🔴" if alerta.severidade == "alta" else ("🟡" if alerta.severidade == "media" else "🟢")
            print(f"│ {icone} [{alerta.severidade.upper():<5}] {alerta.tipo:<25}{' '*28} │")
            print(f"│    {alerta.descricao[:71]:<71} │")
        print("└" + "─"*78 + "┘")
    
    # Notas
    if resultado.notas:
        print("\n┌" + "─"*78 + "┐")
        print(f"│ 📝 NOTAS                                                                    │")
        print("├" + "─"*78 + "┤")
        for nota in resultado.notas[:5]:
            nota_display = nota[:70] + "..." if len(nota) > 70 else nota
            print(f"│ • {nota_display:<72} │")
        print("└" + "─"*78 + "┘")
    
    # Parecer
    if resultado.parecer:
        print("\n┌" + "─"*78 + "┐")
        print("│ 📋 PARECER                                                                  │")
        print("├" + "─"*78 + "┤")
        parecer_clean = resultado.parecer.replace('\n', ' ')
        for i in range(0, len(parecer_clean), 75):
            print(f"│ {parecer_clean[i:i+75]:<75} │")
        print("└" + "─"*78 + "┘")
    
    # Resumo
    print("\n┌" + "─"*78 + "┐")
    print("│ 📊 RESUMO                                                                   │")
    print("├" + "─"*78 + "┤")
    print(f"│ PEPs relacionados:     {len(resultado.peps_relacionados):>10}{' '*37} │")
    print(f"│ Contrapartes crédito:  {len(resultado.contrapartes_credito):>10}{' '*37} │")
    print(f"│ Contrapartes débito:   {len(resultado.contrapartes_debito):>10}{' '*37} │")
    print(f"│ Transações suspeitas:  {len(resultado.transacoes_suspeitas):>10}{' '*37} │")
    print(f"│ Alertas:               {len(resultado.alertas):>10}{' '*37} │")
    altos = len([a for a in resultado.alertas if a.severidade == 'alta'])
    medios = len([a for a in resultado.alertas if a.severidade == 'media'])
    print(f"│   - Alta severidade:   {altos:>10}{' '*37} │")
    print(f"│   - Média severidade:  {medios:>10}{' '*37} │")
    print("└" + "─"*78 + "┘")
    print("\n" + "="*80)


def exportar_json(resultado: NarrativaProcessada) -> str:
    """Exporta resultado para JSON."""
    def to_dict(obj):
        if hasattr(obj, '__dataclass_fields__'):
            return {k: to_dict(v) for k, v in obj.__dict__.items()}
        elif isinstance(obj, list):
            return [to_dict(i) for i in obj]
        elif isinstance(obj, dict):
            return {k: to_dict(v) for k, v in obj.items()}
        elif isinstance(obj, (int, float)):
            return obj
        elif obj is None:
            return None
        return str(obj)
    return json.dumps(to_dict(resultado), indent=2, ensure_ascii=False)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Narrativa de teste (formato livre)
    narrativa_teste = """Consta atuar como economistas/administradores, administrador, assalariado na Rldok Distribuidora Materias E Servicos, com renda mensal de R$45.000,00. - Consta como cônjuge, Renata Da Costa Pedro Porto, CPF 086.754.247-01. - Também figura como sócio da empresa: Supry Office Distribuidora De Materiais E Servicos Ltda, CNPJ 018.593.064/0001-09. Entre 27.09.2023 e 19.12.2024 os créditos somaram R$ 4.118.327,40, sendo R$ 2.650,00 por meio de 1 depósito realizado nas praças deRio De Janeiro-RJ (Portuária), destes R$ 2.650,00 constando como efetuados em espécie, 1 transação e R$ 4.115.594,32 provenientes de 279 TEDs, DOCs, PIXs e transferências entre contas. Demonstramos os principais remetentes: VALOR R$ QTDE REMETENTE CPF/CNPJ BANCO 912.196,09 21 Itrio Ricardo Aparecido Dios Porto Junior 091.912.337-63 Caixa Economica Federal / Nu Pagamentos / Orama Dtvm S/a Comunicado entre 04.2021 e 10.2023 sob 2 ocorrências 894.803,47 63 Acm D M Servicos Ltda 049.326.278/0001-42 Banco Do Brasil / Brasil 692.797,49 23 Rldok D M Servicos Eireli 034.164.381/0001-66 Banco Do Brasil 442.729,66 4 S.L. Sales 042.658.139/0001-77 Banco Do Brasil 319.850,00 14 Omega Medical Distribuidora Produtos De Saude E Servicos Ltd 045.499.461/0001-99 Bradesco (3176/203041), (469/21041) Comunicado em 09.2023 sob 1 ocorrência 198.717,86 13 Bio M D I P Medicos Ltda 040.016.257/0001-56 Banco Do Brasil Os débitos, em igual período, totalizaram R$ 4.127.209,78, dos quais R$ 687.399,93 utilizados para pagamentos diversos, 407 transações, R$ 118.228,87 em gastos com cartão(ões) de débito, R$ 46.320,00 constando como sacados em espécie, 26 retiradas, R$ 12.183,28 para operações de crédito, R$ 3.263.038,75 destinados para quitação de 947 TEDs, DOCs, PIXs, transferências e depósitos em contas. Demonstramos os principais favorecidos: VALOR R$ QTDE FAVORECIDOS CPF/CNPJ BANCO 725.058,28 16 Itrio Ricardo Aparecido Dios P. Junior 091.912.337-63 Itaú / Nu Pagamentos / Orama Dtvm S/a Comunicado entre 04.2021 e 10.2023 sob 2 ocorrências 304.720,00 12 Aylton Batista Da Silva 135.050.637-03 Bradesco (3199/319573), (469/19573) Comunicado entre 05.2022 e 02.2024 sob 2 ocorrências 1.150,00 2 Aylton Batista Da Silva 135.050.637-03 Banco Do Brasil / Nu Pagamentos Comunicado entre 05.2022 e 02.2024 sob 2 ocorrências 250.000,00 2 V Motors Comercio De Veiculos Eireli 034.533.720/0001-34 Bradesco (2730/23056) Comunicado entre 06.2024 e 07.2024 sob 2 ocorrências 125.000,00 5 Marcelo Bastos Boffil 068.397.687-75 Nu Pagamentos 54.777,00 1 Marcelo Bastos Boffil 068.397.687-75 Bradesco (1690/3302) 88.595,00 7 Viviane Batista Carvalho Da Silva 117.233.347-58 Bradesco (26/538389), (3002/8181), (7101/539389) 50.000,00 3 Viviane Batista Carvalho Da Silva 117.233.347-58 Itaú 120.050,00 3 Acm Distribuidora De Materiais E Servicos Ltda 049.326.278/0001-42 Banco Do Brasil Notas: - Entre 19.10.2023 e 15.12.2023 realizou aplicações em fundos de investimento totalizando R$ 400.000,00, posteriormente, resgatou R$ 309.900,01. Demonstramos os principais fundos: RESGATE APLICAÇÃO FUNDO 209.900,01 300.000,00 Cred Priv Plus 100.000,00 100.000,00 Max Di - Após a data 24.05.2024 a conta 20285 da agência 3002, não apresentou movimentação. - Demonstramos por amostragem, os pagamentos diversos efetuados pelo cliente: R$ 94.681,72 destinados a pagamentos de tributos, R$ 12.909,84 destinados a pagamentos de contas de consumo, R$ 579.808,37 destinados a pagamentos de boletos de cobrança, dos quais possuem valores entre R$ 16,05 e R$ 40.590,48. Identificamos a realização de pagamentos de boletos de cobrança a terceiros e por amostragem, demonstramos os principais pagadores/sacados registrados na emissão dos boletos: VALOR R$ QTDE PAGADORES/SACADOS CPF/CNPJ R$25.378,09 2 Vinicius Carvalho Da Silva 00010488307724 R$20.461,86 32 Renata Da Costa Pedro Porto 00008675424701 R$10.316,74 7 Rldok Distribuidora De Material E Servic 34164381000166 -Demonstramos abaixo, por amostragem, o recebimento de recursos com débito imediato de valores, sem causa aparente: DATA TRANSAÇÃO REMETENTE/FAVORECIDO CPF/CNPJ VALOR R$ 21.11.2023 PIX - Crédito Itrio Ricardo Aparecido Dios Porto Junior 091.912.337-63 100.000,00 Comunicado entre 04.2021 e 10.2023 sob 2 ocorrências 21.11.2023 PIX - Débito V Motors Comercio De Veiculos Eireli 034.533.720/0001-34 100.000,00 Comunicado entre 06.2024 e 07.2024 sob 2 ocorrências 27.05.2024 PIX - Crédito Bio M D I P Medicos Ltda 040.016.257/0001-56 16.567,86 27.05.2024 PIX - Débito Falcao Antiguidades E Objetos De Arte Ltda me 023.750.083/0001-31 16.567,86 20.06.2024 PIX - Crédito Marcelo Bastos Boffil 068.397.687-75 18.000,00 20.06.2024 PIX - Débito Marcone Pires Falcao Silva 057.451.157-18 18.000,00 06.11.2024 PIX - Crédito Rldok D M Servicos Eireli 034.164.381/0001-66 50.000,00 06.11.2024 PIX - Débito Marcelo Bastos Boffil 068.397.687-75 50.000,00 Cliente trabalha com licitacoes para orgaos publicos e as empresas citadas sao do itrio ou ele possui participacao na mesma. Segundo relato do cliente recebe comissao por participar do processo licitatorio. - Mediante a pesquisas externas, consta participação na empresa 34164381000166, Rldok Distribuidora De Material E Servicos Ltda, Comercio Atacadista De Artigos De Escritorio E De Papelaria. Diante do exposto, identificamos que: - movimentação apresentada é superior a capacidade financeira declarada, - indícios de movimentações em benefício de terceiros, sem aparente causa, e - recebimento de créditos com o imediato débito dos valores, sem aparente justificativa."""
    
    print("="*80)
    print("🔬 NARRATIVE EXTRACTOR v3.1 - Teste de Extração")
    print("="*80)
    
    extrator = NarrativeExtractor()
    resultado = extrator.processar(narrativa_teste)
    
    exibir_resultado(resultado)
    
    # Exportar JSON
#    json_output = exportar_json(resultado)
#    output_path = "/home/z/my-project/download/narrativa_processada.json"
#    with open(output_path, 'w', encoding='utf-8') as f:
#        f.write(json_output)
#    print(f"\n✅ JSON exportado: {output_path}")
