# parsers/narrative_analyzer.py
"""
Módulo para extração estruturada de informações de textos de narrativas de RIF.
Utiliza expressões regulares para identificar e extrair dados de KYC,
movimentação financeira, participações societárias e vínculos de risco.
"""
from __future__ import annotations
import re
import pandas as pd
from textwrap import dedent
import string
import io
from typing import Tuple, Optional, Union
import traceback


# -------------------------------------------------------------------
# Funções de Extração (Parsers)
# -------------------------------------------------------------------

def extrair_kyc(texto: str) -> pd.DataFrame:
    """Extrai os dados gerais de KYC em um dataframe linha única."""
    # Cliente e "atua como"
    m_ent = re.search(r"INFORMACAO DE KYC:\s*([^\s,]+)", texto, re.IGNORECASE)
    cliente = m_ent.group(1) if m_ent else None

    m_atua = re.search(r"atua como\s+([^,]+?),", texto, re.IGNORECASE)
    atua_como = m_atua.group(1).strip() if m_atua else None

    # Renda mensal
    m_renda = re.search(r"renda mensal de R\$\s*([\d\.,]+)", texto, re.IGNORECASE)
    renda = m_renda.group(1) if m_renda else None

    # Início relacionamento
    m_ini = re.search(r"início do relacionamento ocorreu em\s*(\d{2}/\d{4})", texto, re.IGNORECASE)
    inicio_rel = m_ini.group(1) if m_ini else None

    # Data de nascimento
    m_nasc = re.search(r"Nascido em\s*(\d{2}/\d{2}/\d{4})", texto, re.IGNORECASE)
    nasc = m_nasc.group(1) if m_nasc else None

    # Cidade/UF
    m_res = re.search(r"Reside em\s+([^.]+?)(?:\.|\s+PONTO DE ATENÇÃO)", texto, re.IGNORECASE)
    residencia = m_res.group(1).strip() if m_res else None

    # Observação KYC (ponto de atenção)
    m_obs = re.search(r"PONTO DE ATENÇÃO:\s*(.+?)(?=\. ENTIDADE_IA_|\. SUSPEIÇÃO:|CARACTERÍSTICAS DA MOVIMENTAÇÃO)", texto, re.IGNORECASE)
    obs = m_obs.group(1).strip() if m_obs else None

    df = pd.DataFrame([{
        "Cliente": cliente,
        "Atua como": atua_como,
        "Renda mensal informada": renda,
        "Início do relacionamento": inicio_rel,
        "Data de nascimento": nasc,
        "Cidade/UF de residência": residencia,
        "Observação KYC": obs
    }])
    return df.dropna(axis=1, how='all')


def extrair_participacoes(texto: str) -> pd.DataFrame:
    """
    Extrai pares (rótulo, percentual) como no bloco:
    ENTIDADE_IA_003190: DOC_TEXTO_003139 (100.0%)
    ou
    ENTIDADE_IA_003190: ENTIDADE_IA_003179 (0.0%)
    """
    participacoes = []
    # Regex captura o identificador após ENTIDADE_IA_003190: e o número dentro de parênteses
    padrao = re.compile(
        r"ENTIDADE_IA_\d+:\s*([A-Z0-9_]+)\s*\(([\d\.]+)%\)",
        re.IGNORECASE
    )
    for rotulo, perc in padrao.findall(texto):
        try:
            perc_float = float(perc.replace(",", "."))
        except ValueError:
            perc_float = None
        participacoes.append({
            "Empresa / Documento (rótulo)": rotulo,
            "Participação declarada (%)": perc_float
        })

    df = pd.DataFrame(participacoes)
    return df


def extrair_movimentacao_resumo(texto: str) -> pd.DataFrame:
    """Extrai totais de créditos, débitos e período."""
    # Período analisado
    m_periodo = re.search(
        r"Período Analisado:\s*(\d{2}/\d{2}/\d{4})\s*a\s*(\d{2}/\d{2}/\d{4})",
        texto, re.IGNORECASE
    )
    dt_ini = m_periodo.group(1) if m_periodo else None
    dt_fim = m_periodo.group(2) if m_periodo else None

    # Total a crédito
    m_credito = re.search(
        r"conta recebeu a crédito o valor de R\$\s*([\d\.,]+)",
        texto, re.IGNORECASE
    )
    tot_credito = m_credito.group(1) if m_credito else None

    # Total a débito
    m_debito = re.search(
        r"débitos totalizaram R\$\s*([\d\.,]+)",
        texto, re.IGNORECASE
    )
    tot_debito = m_debito.group(1) if m_debito else None

    df = pd.DataFrame([{
        "Período inicial": dt_ini,
        "Período final": dt_fim,
        "Total a crédito (R$)": tot_credito,
        "Total a débito (R$)": tot_debito
    }])
    return df.dropna(axis=1, how='all')


def extrair_composicao_creditos(texto: str) -> pd.DataFrame:
    """Extrai composição dos créditos: PIX e interbancárias."""
    registros = []
    
    # Regex para capturar múltiplos tipos de operação de crédito
    padrao = re.compile(
        r"([\d,.]+)%\s*(?:transferência\(s\)|depósito\(s\))?\s*(?:via\s*)?(\w+(?:\s*em\s*\w+)?),?",
        re.IGNORECASE
    )
    
    secao_credito = re.search(r"A conta recebeu a crédito(.*?)Os débitos totalizaram", texto, re.DOTALL)
    if secao_credito:
        for perc, tipo in padrao.findall(secao_credito.group(1)):
            registros.append({
                "Tipo de operação (Crédito)": tipo.strip(),
                "% do Total": perc.replace(',', '.')
            })

    df = pd.DataFrame(registros)
    return df


def extrair_composicao_debitos(texto: str) -> pd.DataFrame:
    """Extrai composição dos débitos: PIX, títulos, cartão."""
    registros = []

    # Regex para capturar múltiplos tipos de operação de débito
    padrao = re.compile(
        r"([\d,.]+)%\s*(?:transferência\(s\)|pagamento\(s\))?\s*(?:via\s*)?([\w\s\(\)]+?)(?=\s*e\s*[\d,.]+%|,|$|\.)",
        re.IGNORECASE
    )
    
    secao_debito = re.search(r"Os débitos totalizaram(.*?)ORIGEM DOS RECURSOS", texto, re.DOTALL)
    if secao_debito:
        for perc, tipo in padrao.findall(secao_debito.group(1)):
            # Limpa o tipo de operação para remover parênteses e espaços extras
            tipo_limpo = re.sub(r'de\s*título\(s\)|de\s*fatura\(s\)\s*de\s*cartão\s*de\s*crédito', lambda m: m.group(0).replace('(s)', ''), tipo, flags=re.IGNORECASE)
            tipo_limpo = re.sub(r'\s*\(\w+\)\s*', ' ', tipo_limpo).strip()
            
            registros.append({
                "Tipo de operação (Débito)": tipo_limpo,
                "% do Total": perc.replace(',', '.')
            })

    df = pd.DataFrame(registros)
    return df


def extrair_principais_transacoes(texto: str, tipo_bloco: str) -> pd.DataFrame:
    """Função genérica para extrair principais transações de crédito ou débito."""
    bloco_texto = ""
    if tipo_bloco == "crédito":
        match = re.search(r"ORIGEM DOS RECURSOS:(.*?)DESTINO DOS RECURSOS:", texto, re.DOTALL)
        if match:
            bloco_texto = match.group(1)
    elif tipo_bloco == "débito":
        match = re.search(r"DESTINO DOS RECURSOS:(.*?)SÍNTESE DOS RISCOS", texto, re.DOTALL)
        if match:
            bloco_texto = match.group(1)

    if not bloco_texto:
        return pd.DataFrame()

    # Padrão para cada transator principal
    padrao = re.compile(
        r"(PESSOA_\d+|ENTIDADE_IA_\d+[^,]*?),\s*(DOC_TEXTO_\d+).*?\(R\$\s*([\d\.,]+)\)\s*Quantidade de transações:\s*(\d+)",
        re.IGNORECASE | re.DOTALL
    )
    dados = []
    for pessoa, doc, valor, qtd in padrao.findall(bloco_texto):
        dados.append({
            "Parte": pessoa.strip(),
            "Documento": doc.strip(),
            "Valor (R$)": valor.strip(),
            "Qtde de transações": int(qtd)
        })
    return pd.DataFrame(dados)


def extrair_vinculos_risco(texto: str) -> pd.DataFrame:
    """Cria um dataframe mais textual com os principais vínculos de risco/suspeição."""
    linhas = []

    if "PONTO DE ATENÇÃO:" in texto:
        match = re.search(r"PONTO DE ATENÇÃO:(.*?)(?=SUSPEIÇÃO:|CARACTERÍSTICAS DA MOVIMENTAÇÃO)", texto, re.DOTALL)
        if match:
            linhas.append({"Tipo": "Ponto de Atenção", "Descrição": match.group(1).strip()})
            
    if "SUSPEIÇÃO:" in texto:
        match = re.search(r"SUSPEIÇÃO:(.*?)(?=CARACTERÍSTICAS DA MOVIMENTAÇÃO)", texto, re.DOTALL)
        if match:
            linhas.append({"Tipo": "Suspeição", "Descrição": match.group(1).strip()})

    if "SÍNTESE DOS RISCOS E SINAIS DE ALERTA:" in texto:
        match = re.search(r"SÍNTESE DOS RISCOS E SINAIS DE ALERTA:(.*)", texto, re.DOTALL)
        if match:
            linhas.append({"Tipo": "Síntese de Risco", "Descrição": match.group(1).strip()})

    return pd.DataFrame(linhas)


# -------------------------------------------------------------------
# Função Orquestradora
# -------------------------------------------------------------------

def analyze_narrative(text: str) -> dict[str, pd.DataFrame]:
    """
    Orquestra a análise da narrativa, chamando todas as funções de extração.
    
    Args:
        text: O texto do campo 'informacoesAdicionais'.
        
    Returns:
        Um dicionário onde as chaves são os nomes das análises e os
        valores são os DataFrames resultantes.
    """
    if not isinstance(text, str) or not text.strip():
        return {}

    # Normaliza múltiplos espaços/quebras de linha para um único espaço
    norm_text = " ".join(text.split())

    results = {
        "kyc": extrair_kyc(norm_text),
        "participacoes": extrair_participacoes(norm_text),
        "resumo_movimentacao": extrair_movimentacao_resumo(norm_text),
        "composicao_creditos": extrair_composicao_creditos(norm_text),
        "composicao_debitos": extrair_composicao_debitos(norm_text),
        "principais_credores": extrair_principais_transacoes(norm_text, "crédito"),
        "principais_devedores": extrair_principais_transacoes(norm_text, "débito"),
        "vinculos_risco": extrair_vinculos_risco(norm_text)
    }

    # Filtra DataFrames que resultaram vazios
    return {key: df for key, df in results.items() if not df.empty}


def generate_word_cloud_and_keywords(text: str, max_words: int = 50, top_n_keywords: int = 10) -> Tuple[Optional[Union[bytes, str]], Optional[pd.DataFrame], Optional[dict]]:
    """
    Gera uma nuvem de palavras, extrai os termos mais frequentes e
    identifica keywords financeiras relevantes, usando uma lista manual de stopwords.

    Args:
        text: Texto da narrativa para análise
        max_words: Número máximo de palavras na nuvem
        top_n_keywords: Quantidade de keywords financeiras a retornar
        
    Returns:
        Tupla com (bytes_image | str_error, df_keywords, context_snippets) ou (None, None, None) se falhar
    """
    try:
        from wordcloud import WordCloud
    except ImportError as e:
        return f"Falha ao importar a biblioteca 'wordcloud'. Detalhe do erro: {e}. Verifique se o ambiente virtual (venv) está ativado e se a aplicação está usando o interpretador Python correto.", None, None

    if pd.isna(text) or not isinstance(text, str) or text.strip() == '':
        return None, None, None

    try:
        text_lower = text.lower()
        text_cleaned = re.sub(r'[\d' + string.punctuation + ']', ' ', text_lower)
        text_cleaned = ' '.join(text_cleaned.split())

        stop_words_pt = [
            'de', 'a', 'o', 'que', 'e', 'do', 'da', 'em', 'um', 'para', 'é', 'com', 'não', 'uma',
            'os', 'no', 'se', 'na', 'por', 'mais', 'as', 'dos', 'como', 'mas', 'foi', 'ao', 'ele',
            'das', 'tem', 'à', 'seu', 'sua', 'ou', 'ser', 'quando', 'muito', 'há', 'nos', 'já',
            'está', 'eu', 'também', 'só', 'pelo', 'pela', 'até', 'isso', 'ela', 'entre', 'era',
            'depois', 'sem', 'mesmo', 'aos', 'ter', 'seus', 'quem', 'nas', 'me', 'esse', 'eles',
            'estão', 'você', 'tinha', 'foram', 'essa', 'num', 'nem', 'suas', 'meu', 'às', 'minha'
        ]
        custom_stopwords = [
            'r', 'via', 'cnpj', 'cpf', 'banco', 'bco', 'agencia', 'conta', 'numero',
            'ltda', 'sa', 'eireli', 'me', 'epp', 'valor', 'reais', 'mes', 'periodo',
            'cliente', 'empresa', 'principal', 'utilizada', 'segundo', 'pesquisa',
            'base', 'dados', 'privada', 'referente', 'etc', 'nome', 'fantasia',
            'data', 'abertura', 'situacao', 'faturamento', 'presumido', 'socios',
            'atividade', 'porte', 'endereco', 'cep', 'nunca', 'antes', 'reportado',
            'pld', 'ft', 'identificado', 'sem', 'informacoes', 'sobre',
            'participacoes', 'societarias', 'midia', 'negativa', 'nao', 'sim',
            'total', 'principais', 'contrapartes', 'outras', 'restantes', 'sao',
            'oes', 'informacao', 'declarada', 'interna', 'atualizacao', 'cadastral',
            'registro', 'profissional', 'vinculo', 'empregaticio', 'desde', 'vez',
            'recibo', 'em', 'relevantes', 'titular', 'proprio', 'ja', 'razao', 'social',
            'idade', 'anos', 'estado', 'civil', 'nacionalidade', 'email', 'adicionais',
            'historico', 'relacionada', 'considerando', 'analisado', 'ag', 'cnt', 'tipo'
        ]
        all_stopwords = set(stop_words_pt).union(custom_stopwords)

        words = [word for word in text_cleaned.split() if word not in all_stopwords and len(word) > 2]

        if not words:
            return None, None, None

        processed_text = ' '.join(words)

        bytes_image_or_error = None
        try:
            wc = WordCloud(width=800, height=300, background_color='white',
                           colormap='viridis', max_words=max_words).generate(processed_text)
            image = wc.to_image()
            img_buffer = io.BytesIO()
            image.save(img_buffer, format='PNG')
            bytes_image_or_error = img_buffer.getvalue()
        except Exception as e:
            error_message = f"Erro interno da biblioteca wordcloud: {e}"
            bytes_image_or_error = error_message

        word_freq = pd.Series(words).value_counts()
        df_freq = word_freq.reset_index()
        df_freq.columns = ['Palavra', 'Frequência']
        
        financial_keywords = [
            'pagamento', 'pago', 'pagamentos', 'fatura', 'compra', 'compras', 'gasto', 'gastos',
            'credito', 'crédito', 'creditos', 'créditos', 'creditado', 'creditada',
            'recebido', 'recebimento', 'aporte', 'aportes',
            'debito', 'débito', 'debitos', 'débitos', 'debitado', 'debitada',
            'enviado', 'transferencia', 'transferência', 'transferencias', 'transferências', 'transf',
            'remessa', 'remessas', 'pix', 'ted', 'doc', 'saque', 'saques', 'retirada', 'retiradas',
            'deposito', 'depósito', 'depositos', 'depósitos', 'recursos', 'entradas',
            'aplicacao', 'aplicação', 'investimento', 'resgate', 'resgates', 'emprestimo', 'empréstimo',
            'financiamento', 'premio', 'prêmio', 'aposta', 'arrecadacao', 'arrecadação', 'especie', 'espécie'
        ]
        df_keywords = df_freq[df_freq['Palavra'].isin(financial_keywords)].head(top_n_keywords)

        context_snippets = {}
        if not df_keywords.empty:
            text_norm_context = text.replace('−', '-').replace('–', '-')
            sentences = re.split(r'[.!?]\s+', text_norm_context)
            for keyword in df_keywords['Palavra']:
                found_snippets = []
                pattern_kw = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
                for sentence in sentences:
                    if pattern_kw.search(sentence):
                        snippet = sentence.strip()
                        if snippet:
                            found_snippets.append(snippet)
                    if len(found_snippets) >= 3:
                        break
                if found_snippets:
                    context_snippets[keyword] = found_snippets

        return bytes_image_or_error, df_keywords, context_snippets

    except Exception as e:
        error_msg = f"Erro em generate_word_cloud_and_keywords: {e}"
        print(error_msg)
        print(traceback.format_exc())
        return error_msg, None, None
