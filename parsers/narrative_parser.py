# parsers/narrative_parser.py - Parser Unificado de Narrativas
"""
Parser unificado para extração de dados financeiros de narrativas RIF.
Suporta múltiplos bancos: Santander, Itaú, Bradesco, Caixa, BB, Nubank, Sicoob.
Esta versão foi restaurada da implementação v3.
"""
from __future__ import annotations
import re
import pandas as pd
from typing import Tuple

# Colunas padrão de retorno
CRED_COLS = ['Origem do Crédito', 'Valor (R$)', 'Qtd Transações', 'Detalhe']
DEB_COLS = ['Destino do Débito', 'Valor (R$)', 'Qtd Transações', 'Detalhe']
CARD_COLS = ['Estabelecimento', 'Valor (R$)', 'Qtd Transações']


def clean_value(value_str: str) -> float:
    """Converte string monetária (ex: '1.234,56' ou '1.234.56') para float."""
    if isinstance(value_str, (int, float)): return float(value_str)
    if not value_str or not isinstance(value_str, str): return 0.0
    try:
        # Remove tudo que não é dígito, ponto ou vírgula
        val = re.sub(r'[^\d.,]', '', value_str)
        # Caso brasileiro: 1.000,00 -> remove ponto, troca virgula por ponto
        if ',' in val and '.' in val:
            if val.find('.') < val.find(','): # 1.000,00
                val = val.replace('.', '').replace(',', '.')
            else: # 1,000.00 (formato US raro, mas possivel)
                val = val.replace(',', '')
        elif ',' in val: # 1000,00
            val = val.replace(',', '.')
        # Se só tem ponto (1000.00), o float() resolve
        return float(val)
    except ValueError:
        return 0.0

def extract_all_financial_data(text: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Extrai dados financeiros detectando automaticamente o padrão do relatório.
    Suporta:
    1. Padrão Lista/Tabular (Nubank/Genérico)
    2. Padrão Narrativo Denso (Itaú)
    3. Padrão Narrativo Lista (Sicoob)
    4. Padrão Lista Descritiva (Banco do Brasil)
    5. Padrão Tabular Rígido (Bradesco)
    6. Padrão Lista Detalhada (Santander)
    7. Padrão Tópicos Numerados (Caixa)
    """
    if not text:
        return pd.DataFrame(columns=CRED_COLS), pd.DataFrame(columns=DEB_COLS), pd.DataFrame(columns=CARD_COLS), pd.DataFrame()

    # Normalização básica
    text_norm = text.replace('−', '-').replace('–', '-').replace('—', '-')
    text_norm = text_norm.replace('•', '-')

    # --- PARSER 7: CAIXA ECONÔMICA FEDERAL (v2) ---
    def _parse_caixa_style(txt):
        """
        Parser aprimorado para o padrão da Caixa.
        Extrai tanto transações detalhadas (com CPF/CNPJ) quanto sumários de operações.
        """
        credits, debits = [], []
        txt = txt.replace('?', '-').replace('–', '-') # Normaliza separadores

        # Regex para encontrar um item de transação, que pode ser detalhado ou resumo
        re_entry = re.compile(
            r"R\$\s*(?P<val>[\d.,]+)\s*[-\s:]+\s*"  # Padrão de valor: R$ 123,45
            r"(?:(?P<qtd>\d+)\s+)?\s*"             # Quantidade opcional: (123)
            r"(?P<desc>.*?)"                       # Resto da linha é a descrição
            # Parada da captura (lookahead): encontra o próximo R$ ou uma nova seção
            r"(?=(?:\s*-\s*)?R\$\s|DESTINO DOS RECURSOS:|CARACTERÍSTICAS DA MOVIMENTAÇÃO|INFORMAÇÕES ADICIONAIS|CONCLUSÃO|$)",
            re.IGNORECASE | re.DOTALL
        )

        # Regex para extrair NOME, CPF/CNPJ e detalhes de uma descrição
        re_doc = re.compile(
            r"(?P<name>.*?),\s*(?P<doc_type>CNPJ|CPF)\s*(?P<doc>[\d./-]+)\s*"
            r"(?:-\s*\(\s*(?P<details>.*?)\s*\))?"
        )

        def process_block(block_text, entry_type):
            """Processa um bloco de texto (créditos ou débitos) e extrai os dados."""
            entries = []
            for entry_match in re_entry.finditer(block_text):
                val_str = entry_match.group('val')
                desc = entry_match.group('desc').strip()
                
                # Ignora linhas de cabeçalho que o regex possa capturar
                if desc.lower().startswith(('cujos principais remetentes', 'cujos principais beneficiários')):
                    continue

                doc_match = re_doc.search(desc)
                item = None
                
                if doc_match: # É uma linha com detalhes de contraparte (Nome, Doc)
                    name = doc_match.group('name').strip().upper()
                    details = doc_match.group('details')
                    qtd_from_details = 1
                    if details:
                        qtd_match = re.search(r"(\d+)\s+(?:PIX|TEV|DOC|TED|trans)", details, re.IGNORECASE)
                        if qtd_match:
                            qtd_from_details = int(qtd_match.group(1))
                    
                    item = {
                        ('Origem do Crédito' if entry_type == 'cred' else 'Destino do Débito'): name,
                        'Valor (R$)': clean_value(val_str),
                        'Qtd Transações': qtd_from_details,
                        'Detalhe': f"{doc_match.group('doc_type')}: {doc_match.group('doc')}"
                    }
                
                else: # É uma linha de resumo (ex: "Resgates", "Aplicações")
                    name = re.split(r':', desc, 1)[0].strip().upper()
                    if name and not name.lower().startswith('transferência'):
                        item = {
                            ('Origem do Crédito' if entry_type == 'cred' else 'Destino do Débito'): name,
                            'Valor (R$)': clean_value(val_str),
                            'Qtd Transações': int(entry_match.group('qtd')) if entry_match.group('qtd') else 1,
                            'Detalhe': "Geral"
                        }
                
                if item:
                    entries.append(item)
            return entries

        # Extrai e processa o bloco de CRÉDITOS
        cred_block_match = re.search(r"ORIGEM DOS RECURSOS:.*?(?=\s*-\s*R\$\s|\s*R\$\s)(.*?)(?=DESTINO DOS RECURSOS:|CARACTERÍSTICAS DA MOVIMENTAÇÃO|CONCLUSÃO|$)", txt, re.IGNORECASE | re.DOTALL)
        if cred_block_match:
            credits = process_block(cred_block_match.group(1), 'cred')

        # Extrai e processa o bloco de DÉBITOS
        deb_block_match = re.search(r"DESTINO DOS RECURSOS:.*?(?=\s*-\s*R\$\s|\s*R\$\s)(.*?)(?=CARACTERÍSTICAS DA MOVIMENTAÇÃO|INFORMAÇÕES ADICIONAIS|CONCLUSÃO|$)", txt, re.IGNORECASE | re.DOTALL)
        if deb_block_match:
            debits = process_block(deb_block_match.group(1), 'deb')
            
        extra_info = {}
        
        kyc_match = re.search(r"INFORMAÇÕES ADICIONAIS DO CONHEÇA SEU CLIENTE:(.*?)(?=CONCLUSÃO)", txt, re.IGNORECASE | re.DOTALL)
        if kyc_match:
            kyc_text = kyc_match.group(1).strip()
            if kyc_text:
                extra_info["Informações Adicionais de KYC"] = kyc_text
                
        conclusao_match = re.search(r"CONCLUSÃO:(.*?)$", txt, re.IGNORECASE | re.DOTALL)
        if conclusao_match:
            conclusao_text = conclusao_match.group(1).strip()
            if conclusao_text:
                extra_info["Conclusão"] = conclusao_text
                
        df_extra = pd.DataFrame([extra_info]) if extra_info else pd.DataFrame()
            
        return credits, debits, [], df_extra

    # --- PARSER 1: SANTANDER ---
    def _parse_santander_style(txt):
        credits, debits = [], []
        txt = txt.replace('•', '•').replace('º', 'o')
        re_amostral = re.compile(
            r"-\s*(?P<name>.+?)\s+-\s+(?:CNPJ|CPF):\s*(?P<doc>[\d./-]+)\s*-\s*"
            r"Valor (?:Recebido|Enviado):\s*R\$\s*(?P<val>[\d.,]+)"
            r"(?:\s*,\s*sendo:\s*(?P<details>.*?))?(?=\s*-|$)", re.IGNORECASE | re.DOTALL
        )
        re_hierarquico = re.compile(
            r"R\$\s*(?P<val>[\d.,]+)\s+em\s+(?P<qtd>\d+)\s+.*?"
            r"(?:por|para|emitido por)\s+(?P<name>.*?)\s+"
            r"(?P<doc_type>CNPJ|CPF):\s*(?P<doc>[\d./-]+)",
            re.IGNORECASE
        )
        def extract_qtd_local(details_str, fallback_qtd=1):
            if not details_str: return fallback_qtd
            match_qtd = re.search(r"(\d+)\s+(?:PIX|TEV|DOC|TED|trans|lanç)", str(details_str), re.IGNORECASE)
            return int(match_qtd.group(1)) if match_qtd else fallback_qtd
        match_cred = re.search(
            r"(?:Total Credito:|Principais remetentes|contrapartes.*?credito).*?:(.*?)"
            r"(?=Total Debito:|Resumo de lancamentos a debito|contrapartes.*?debito|$)",
            txt, re.IGNORECASE | re.DOTALL
        )
        if match_cred:
            block = match_cred.group(1)
            for m in re_amostral.finditer(block):
                credits.append({'Origem do Crédito': m.group('name').strip().upper(), 'Valor (R$)': clean_value(m.group('val')), 'Qtd Transações': extract_qtd_local(m.group('details')), 'Detalhe': f"CNPJ/CPF: {m.group('doc')}"})
            for m in re_hierarquico.finditer(block):
                credits.append({'Origem do Crédito': m.group('name').strip().upper(), 'Valor (R$)': clean_value(m.group('val')), 'Qtd Transações': int(m.group('qtd')), 'Detalhe': f"CNPJ/CPF: {m.group('doc')}"})
                
        stop_expressions = (
            r"Ao analisar|Conclu[íi]da a an[áa]lise|"
            r"Caracter[íi]sticas da movimenta[cç][ãa]o financeira informada|Chama aten[cç][ãa]o|"
            r"Destacamos|Ressaltamos|Feita an[áa]lise|Conclus[ãa]o|"
            r"Com base no conhe[cç]a seu cliente|Considerando|Salienta-se|Salientamos"
        )
        
        match_deb = re.search(
            rf"(?:Total Debito:|Principais destinatarios|contrapartes.*?debito).*?:(.*?)"
            rf"(?={stop_expressions}|$)",
            txt, re.IGNORECASE | re.DOTALL
        )
        if match_deb:
            block = match_deb.group(1)
            for m in re_amostral.finditer(block):
                debits.append({'Destino do Débito': m.group('name').strip().upper(), 'Valor (R$)': clean_value(m.group('val')), 'Qtd Transações': extract_qtd_local(m.group('details')), 'Detalhe': f"CNPJ/CPF: {m.group('doc')}"})
            for m in re_hierarquico.finditer(block):
                debits.append({'Destino do Débito': m.group('name').strip().upper(), 'Valor (R$)': clean_value(m.group('val')), 'Qtd Transações': int(m.group('qtd')), 'Detalhe': f"CNPJ/CPF: {m.group('doc')}"})
                
        extra_info = {}
        notas_raw = ""
        if match_deb:
            last_end = match_deb.end(1)
            notas_raw = txt[last_end:].strip()
        elif match_cred:
            last_end = match_cred.end(1)
            notas_raw = txt[last_end:].strip()
            
        if not notas_raw:
            m_conc = re.search(rf"({stop_expressions})\b.*", txt, flags=re.IGNORECASE | re.DOTALL)
            if m_conc:
                notas_raw = m_conc.group(0).strip()

        if notas_raw:
            conclusao_clean = re.sub(
                r"^(?:CONCLUS[ÃA]O|CARACTER[ÍI]STICAS DA MOVIMENTA[CÇ][ÃA]O FINANCEIRA INFORMADA)\s*:\s*", 
                "", notas_raw, flags=re.IGNORECASE
            ).strip()
            if conclusao_clean:
                extra_info["Conclusão"] = conclusao_clean
                
        df_extra = pd.DataFrame([extra_info]) if extra_info else pd.DataFrame()
        return credits, debits, [], df_extra

    # --- PARSER 2: BRADESCO ---
    def _parse_bradesco_style(txt):
        credits, debits = [], []
        txt_linear = ' '.join(txt.split())
        re_bradesco_item = re.compile(
            r"(?P<val>\d{1,3}(?:\.\d{3})*,\d{2})\s+"
            r"(?P<qtd>\d+)\s+"
            r"(?P<name>.+?)\s+"
            r"(?P<doc>\d{11,14}|[\d.\-/]{12,18})"
            r"(?:\s+(?P<banco>.*?))?"
            r"(?=\s+\d{1,3}(?:\.\d{3})*,\d{2}\s+\d+|$)", 
            re.IGNORECASE
        )
        
        header_pattern = r"VALOR\s+R\$?[, ]*QTDE[, ]*(?:DEPOSITANTES?[\s/]*REMETENTES?|REMETENTES?|DEPOSITANTES?|FAVORECIDOS?|BENEFICI[ÁA]RIOS?|NOME)[, ]*(?:CPF[\s/]*CNPJ|CNPJ|CPF)(?:[, e]*BANCO)?"

        cred_start = r"(?:Demonstramos os principais (?:depositantes e remetentes|remetentes|depositantes|origens).*?:|VALOR\s+R\$?[, ]*QTDE[, ]*(?:DEPOSITANTES?[\s/]*REMETENTES?|REMETENTES?|DEPOSITANTES?)[, ]*(?:CPF[\s/]*CNPJ|CNPJ|CPF)(?:[, e]*BANCO)?)"
        cred_end = r"((?:Os d[eé]bitos|Total a d[eé]bito|Demonstramos os principais (?:favorecidos|destinat[áa]rios|destinos|benefici[áa]rios)|VALOR\s+R\$?[, ]*QTDE[, ]*(?:FAVORECIDOS?|BENEFICI[ÁA]RIOS?)|$))"

        match_cred = re.search(f"{cred_start}(.*?){cred_end}", txt_linear, re.IGNORECASE)
        if match_cred:
            content = match_cred.group(1)
            content = re.sub(header_pattern, "", content, flags=re.IGNORECASE).strip()
            for match in re_bradesco_item.finditer(content):
                name = match.group('name').strip().upper()
                if "VALOR" in name or "QTDE" in name: continue
                banco = match.group('banco')
                detalhe = f"Doc: {match.group('doc')}"
                if banco:
                    banco_clean = re.split(r'Comunicado', banco, flags=re.IGNORECASE)[0].strip()
                    if banco_clean:
                        detalhe += f" | Banco: {banco_clean}"
                credits.append({'Origem do Crédito': name, 'Valor (R$)': clean_value(match.group('val')), 'Qtd Transações': int(match.group('qtd')), 'Detalhe': detalhe})
                
        deb_start = r"(?:Demonstramos os principais (?:favorecidos|destinat[áa]rios|destinos|benefici[áa]rios).*?:|VALOR\s+R\$?[, ]*QTDE[, ]*(?:FAVORECIDOS?|BENEFICI[ÁA]RIOS?)[, ]*(?:CPF[\s/]*CNPJ|CNPJ|CPF)(?:[, e]*BANCO)?)"
        deb_end = r"((?:Nota:|Notas:|Considerações:|Demonstramos por amostragem|Diante do exposto|$))"

        match_deb = re.search(f"{deb_start}(.*?){deb_end}", txt_linear, re.IGNORECASE)
        if match_deb:
            content = match_deb.group(1)
            content = re.sub(header_pattern, "", content, flags=re.IGNORECASE).strip()
            for match in re_bradesco_item.finditer(content):
                name = match.group('name').strip().upper()
                if "VALOR" in name or "QTDE" in name: continue
                banco = match.group('banco')
                detalhe = f"Doc: {match.group('doc')}"
                if banco:
                    banco_clean = re.split(r'Comunicado', banco, flags=re.IGNORECASE)[0].strip()
                    if banco_clean:
                        detalhe += f" | Banco: {banco_clean}"
                debits.append({'Destino do Débito': name, 'Valor (R$)': clean_value(match.group('val')), 'Qtd Transações': int(match.group('qtd')), 'Detalhe': detalhe})
        
        extra_info = {}
        
        # Extrair Informações de KYC (para antes das tabelas, notas ou conclusão)
        kyc_match = re.search(r"^(.*?)(?=Demonstramos os principais|(?:Nota|Notas|Considerações):|Diante do exposto|$)", txt_linear, re.IGNORECASE)
        if kyc_match:
            kyc_text = kyc_match.group(1).strip()
            if kyc_text:
                extra_info["Informações de KYC"] = kyc_text
                
        # Extrair Notas (pode estar no início ou no fim do texto)
        notas_match = re.search(r"(?:Nota|Notas|Considerações):\s*(.*?)(?=(?:Demonstramos os principais|Demonstramos por amostragem|Diante do exposto|$))", txt_linear, re.IGNORECASE)
        if notas_match:
            notas_text = notas_match.group(1).strip()
            if notas_text:
                extra_info["Notas"] = notas_text
                
        # Extrair Conclusão
        conclusao_match = re.search(r"Diante do exposto[,\s]*(?:identificamos\s+que|conclu[íi]mos\s+que)?:?\s*(.*)", txt_linear, re.IGNORECASE)
        if conclusao_match:
            conclusao_text = conclusao_match.group(1).strip()
            if conclusao_text:
                extra_info["Conclusão"] = conclusao_text
                
        df_extra = pd.DataFrame([extra_info]) if extra_info else pd.DataFrame()
        
        return credits, debits, [], df_extra

    # --- PARSER 3: BANCO DO BRASIL ---
    def _parse_bb_style(txt):
        credits, debits = [], []
        re_bb = re.compile(r"(?P<name>.*?)\s+-\s+(?P<doc>[\d./-]+)\s*(?:\(.*?\))?\s*-\s*(?P<qtd>\d+)\s+lançamento\(s\).*?:\s*R\$(?P<val>[\d.,]+)", re.IGNORECASE)
        match_cred = re.search(r"Principais remetentes/depositantes identificados:(.*?)(?=Resumo de lançamentos a débito|Principais destinatários|$)", txt, re.IGNORECASE | re.DOTALL)
        if match_cred:
            for match in re_bb.finditer(match_cred.group(1)):
                credits.append({'Origem do Crédito': match.group('name').strip().upper(), 'Valor (R$)': clean_value(match.group('val')), 'Qtd Transações': int(match.group('qtd')), 'Detalhe': f"Doc: {match.group('doc')}"})
                
        match_deb = re.search(r"Principais destinatários de recursos identificados:(.*)", txt, re.IGNORECASE | re.DOTALL)
        notas_raw = ""
        
        if match_deb:
            deb_text = match_deb.group(1)
            last_end = 0
            for match in re_bb.finditer(deb_text):
                debits.append({'Destino do Débito': match.group('name').strip().upper(), 'Valor (R$)': clean_value(match.group('val')), 'Qtd Transações': int(match.group('qtd')), 'Detalhe': f"Doc: {match.group('doc')}"})
                last_end = match.end()
            notas_raw = deb_text[last_end:].strip()
        elif match_cred:
            cred_text = match_cred.group(1)
            last_end = 0
            for match in re_bb.finditer(cred_text):
                last_end = match.end()
            notas_raw = cred_text[last_end:].strip()
            
        extra_info = {}
        
        # Extração de Informações de KYC
        kyc_match = re.search(r"(?:INFORMA[ÇC][ÕO]ES CADASTRAIS|Per[ií]odo analisado):?\s*(.*?)(?=ORIGEM DOS RECURSOS:|Principais remetentes/depositantes identificados:|$)", txt, re.IGNORECASE | re.DOTALL)
        if kyc_match:
            kyc_text = kyc_match.group(1).strip()
            if kyc_text:
                extra_info["Informações de KYC"] = kyc_text
                
        if notas_raw:
            # Limpa as expressões introdutórias se elas existirem
            conclusao_clean = re.sub(r"^(?:INFORMA[ÇC][ÕO]ES\s*(?:ADICIONAIS)?|CONSIDERA[ÇC][ÕO]ES|CARACTER[ÍI]STICAS\s+DA\s+MOVIMENTA[ÇC][ÃA]O\s+FINANCEIRA\s+INFORMADA)\s*:\s*", "", notas_raw, flags=re.IGNORECASE).strip()
            if conclusao_clean:
                extra_info["Conclusão"] = conclusao_clean
                
        df_extra = pd.DataFrame([extra_info]) if extra_info else pd.DataFrame()
        return credits, debits, [], df_extra

    # --- PARSER 4: SICOOB ---
    def _parse_sicoob_style(txt):
        credits, debits = [], []
        re_sicoob = re.compile(r"(?P<date>\d{2}/\d{2}/\d{4})\s*-\s*R\$\s*(?P<val>[\d.,]+)\s*-\s*(?P<type>origem|destino):\s*(?P<name>.*?),\s*(?P<doc>[\d./-]+)(?:\.|\s+Bc\.|\s+Ag\.|$)", re.IGNORECASE)
        match_section = re.search(r"Análise de movimentações.*?((?:Para o movimento|No período).*?)(?=\*\*\*|Diante das informações|$)", txt, re.IGNORECASE | re.DOTALL)
        section_text = match_section.group(1) if match_section else txt
        for match in re_sicoob.finditer(section_text):
            val, tipo, nome, doc = clean_value(match.group('val')), match.group('type').lower(), match.group('name').strip().upper(), match.group('doc').strip()
            item = {'Valor (R$)': val, 'Qtd Transações': 1, 'Detalhe': f"Doc: {doc} ({match.group('date')})"}
            if 'origem' in tipo: credits.append({**item, 'Origem do Crédito': nome})
            elif 'destino' in tipo: debits.append({**item, 'Destino do Débito': nome})
        return credits, debits, []

    # --- PARSER 5: ITAÚ ---
    def _parse_itau_style(txt):
        credits, debits = [], []
        re_itau_item = re.compile(r"(?P<name>[^,:\n]+),\s+(?P<doc>\d{11,14})\s*(?:\[.*?\]|\s*-\s*Banco.*?)?\s*\(R\$\s*(?P<val>[\d.,]+)\)", re.IGNORECASE)
        match_cred = re.search(r"ORIGEM DOS RECURSOS.*?:(.*?)(?=DESTINO DOS RECURSOS|Total a débito|$)", txt, re.IGNORECASE | re.DOTALL)
        if match_cred:
            for match in re_itau_item.finditer(match_cred.group(1)):
                raw_name, clean_name = match.group('name').strip(), re.split(r"emitentes\(s\):|emitentes:", match.group('name').strip(), flags=re.IGNORECASE)[-1].strip()
                if len(clean_name) > 2: credits.append({'Origem do Crédito': clean_name.upper(), 'Valor (R$)': clean_value(match.group('val')), 'Qtd Transações': 1, 'Detalhe': f"Doc: {match.group('doc')}"})
        match_deb = re.search(r"DESTINO DOS RECURSOS.*?:(.*?)(?=ENQUADRAMENTO|SINAIS DE ALERTA|$)", txt, re.IGNORECASE | re.DOTALL)
        if match_deb:
            for match in re_itau_item.finditer(match_deb.group(1)):
                raw_name, clean_name = match.group('name').strip(), re.split(r"favorecidos\(s\):|favorecidos:", match.group('name').strip(), flags=re.IGNORECASE)[-1].strip()
                if len(clean_name) > 2: debits.append({'Destino do Débito': clean_name.upper(), 'Valor (R$)': clean_value(match.group('val')), 'Qtd Transações': 1, 'Detalhe': f"Doc: {match.group('doc')}"})
        return credits, debits, []

    # --- PARSER 6: NUBANK (ESPECÍFICO) ---
    def _parse_nubank_style(txt):
        credits, debits, cards = [], [], []
        nubank_info = {}
        
        def extract_field(regex, text):
            match = re.search(regex, text, re.IGNORECASE)
            return match.group(1).strip() if match else ""

        # Informações básicas
        nubank_info['Nome'] = extract_field(r"-\s*Nome:\s*(.*?)(?:\n|$)", txt)
        nubank_info['CPF'] = extract_field(r"-\s*CPF:\s*(.*?)(?:\n|$)", txt)
        nubank_info['Idade'] = extract_field(r"-\s*Idade:\s*(.*?)(?:\n|$)", txt)
        nubank_info['Estado civil declarado'] = extract_field(r"-\s*Estado civil declarado:\s*(.*?)(?:\n|$)", txt)
        nubank_info['Email'] = extract_field(r"-\s*Email:\s*(.*?)(?:\n|$)", txt)
        nubank_info['Nacionalidade'] = extract_field(r"-\s*Nacionalidade:\s*(.*?)(?:\n|$)", txt)
        nubank_info['Endereço cadastrado'] = extract_field(r"-\s*Endereço cadastrado:\s*(.*?)(?:\n|$)", txt)
        nubank_info['Cliente na categoria conta de pagamentos desde'] = extract_field(r"-\s*Cliente na categoria conta de pagamentos desde:\s*(.*?)(?:\n|$)", txt)
        nubank_info['Cliente na categoria cartão de crédito desde'] = extract_field(r"-\s*Cliente na categoria cartão de crédito desde:\s*(.*?)(?:\n|$)", txt)
        
        # Informações de atualização cadastral
        nubank_info['Renda informada pelo cliente'] = extract_field(r"-\s*Renda informada pelo cliente:\s*(.*?)(?:\n|$)", txt)
        nubank_info['Patrimônio'] = extract_field(r"-\s*Patrimônio:\s*(.*?)(?:\n|$)", txt)
        nubank_info['Profissão'] = extract_field(r"-\s*Profissão:\s*(.*?)(?:\n|$)", txt)
        nubank_info['Última atualização cadastral'] = extract_field(r"-\s*Última atualização cadastral:\s*(.*?)(?:\n|$)", txt)
        
        # Informações de bases de dados
        nubank_info['Renda presumida'] = extract_field(r"-\s*Renda presumida:\s*(.*?)(?:\n|$)", txt)
        nubank_info['Registro profissional'] = extract_field(r"-\s*Registro profissional:\s*(.*?)(?:\n|$)", txt)
        nubank_info['Registro societário'] = extract_field(r"-\s*Registro societário:\s*(.*?)(?:\n|$)", txt)
        
        # Informações Adicionais / Suspeitas
        nubank_info['Histórico de Fraude'] = extract_field(r"-\s*Histórico de Fraude:\s*(.*?)(?:\n|$)", txt)
        nubank_info['Histórico de PLD'] = extract_field(r"-\s*Histórico de PLD:\s*(.*?)(?:\n|$)", txt)
        nubank_info['Exposição política (PEP ou relacionado)'] = extract_field(r"-\s*Exposição política \(PEP ou relacionado\):\s*(.*?)(?:\n|$)", txt)
        nubank_info['Mídia Negativa'] = extract_field(r"-\s*Mídia Negativa:\s*(.*?)(?:\n|$)", txt)

        # Período Analisado
        periodo = extract_field(r"-\s*Período analisado:\s*(.*?)(?=\s*- Total|\n|$)", txt)
        if not periodo:
            m_periodo = re.search(r"Considerando as movimentações de\s*([\d]{2}/[\d]{2}/[\d]{4}\s*a\s*[\d]{2}/[\d]{2}/[\d]{4})", txt, re.IGNORECASE)
            if m_periodo:
                periodo = m_periodo.group(1).strip()
        if periodo:
            # Extrai especificamente as datas e a palavra 'a' no meio, ignorando "Considerando..."
            m_dates = re.search(r"([\d]{2}/[\d]{2}/[\d]{4})\s*a\s*([\d]{2}/[\d]{2}/[\d]{4})", periodo, re.IGNORECASE)
            if m_dates:
                nubank_info['Período Analisado'] = f"{m_dates.group(1)} a {m_dates.group(2)}"
            else:
                periodo = re.sub(r'^[-\s]+|[-\s.]+$', '', periodo)
                nubank_info['Período Analisado'] = periodo
        
        # Suspeitas e Marcações de Risco
        # Busca todas as ocorrências de Suspeitas: ou "Caso haja contrapartes que possuam marcações de risco"
        suspeitas_matches = []
        
        # 1. Padrão "Suspeitas:" clássico
        m_susp_classico = re.search(r"-\s*Suspeitas:\s*(.*?)(?=(?:$|CR[EÉ]DITOS:|D[EÉ]BITOS:|OUTRAS CONTRAPARTES))", txt, re.IGNORECASE | re.DOTALL)
        if m_susp_classico:
            suspeitas_matches.append(m_susp_classico.group(1).strip())
            
        # 2. Padrão de "marcações de risco" espalhadas pelo texto
        # Procura cada bloco que começa com "Caso haja contrapartes que possuam marcações de risco" e termina
        # antes do próximo cabeçalho importante ou final do texto.
        m_riscos = re.finditer(r"Caso haja contrapartes que possuam marcações de risco.*?abaixo:\s*(.*?)(?=(?:- Total dos|___|CR[EÉ]DITOS:|D[EÉ]BITOS:|OUTRAS CONTRAPARTES|$))", txt, re.IGNORECASE | re.DOTALL)
        for m in m_riscos:
            match_str = m.group(1).strip()
            if match_str and match_str not in suspeitas_matches:
                suspeitas_matches.append(match_str)
                
        if suspeitas_matches:
            nubank_info['Suspeitas'] = "\n\n".join(suspeitas_matches)
        else:
            nubank_info['Suspeitas'] = ""

        # Limpeza para cortar valores no primeiro hífen conforme a instrução
        fields_to_split = [
            "Nome", "CPF", "Idade", "Estado civil declarado", "Email", "Nacionalidade",
            "Cliente na categoria conta de pagamentos desde", "Cliente na categoria cartão de crédito desde",
            "Renda informada pelo cliente", "Patrimônio", "Profissão", "Renda presumida", "Registro profissional",
            "Histórico de Fraude", "Histórico de PLD", "Exposição política (PEP ou relacionado)","Mídia Negativa"
        ]
        
        for field in fields_to_split:
            if nubank_info.get(field):
                # Extrai apenas até o primeiro hífen para não trazer outros campos concatenados indevidamente
                nubank_info[field] = nubank_info[field].split('-')[0].strip()
                
        # Limpar campo Patrimônio para manter o texto apenas até antes do terceiro hífen
        if nubank_info.get('Patrimônio'):
            parts = nubank_info['Patrimônio'].split('-')
            nubank_info['Patrimônio'] = '-'.join(parts[:3]).strip()
            
        # Limpar campo Última atualização cadastral para finalizar antes de "Informações de"
        if nubank_info.get('Última atualização cadastral'):
            parts = re.split(r'Informações de', nubank_info['Última atualização cadastral'], flags=re.IGNORECASE)
            nubank_info['Última atualização cadastral'] = parts[0].strip(' -')
            
        # Limpar campo Registro societário para finalizar antes de "Cliente Nubank" ou "Informações Adicionais"
        if nubank_info.get('Registro societário'):
            parts = re.split(r'Cliente Nubank:?|Informações Adicionais:?', nubank_info['Registro societário'], flags=re.IGNORECASE)
            nubank_info['Registro societário'] = parts[0].strip(' -')

        # Limitar Endereço cadastrado a no máximo 200 caracteres
        if nubank_info.get('Endereço cadastrado') and len(nubank_info['Endereço cadastrado']) > 200:
            nubank_info['Endereço cadastrado'] = nubank_info['Endereço cadastrado'][:197] + "..."

        # CRÉDITOS E DÉBITOS
        cred_block = ""
        m_cred1 = re.search(r"(?:CR[EÉ]DITOS:|Origem dos cr[eé]ditos[,:].*?)(?:\n|-)(.*?)(?=D[EÉ]BITOS:|- Total dos d[eé]bitos|Destino dos d[eé]bitos|OUTRAS CONTRAPARTES|Caso haja contrapartes|$)", txt, re.IGNORECASE | re.DOTALL)
        if m_cred1: cred_block += m_cred1.group(1)
        m_cred2 = re.search(r"OUTRAS CONTRAPARTES DE CR[EÉ]DITO:(.*?)(?=OUTRAS CONTRAPARTES DE D[EÉ]BITO:|-\s*Suspeitas:|- Total dos d[eé]bitos|Destino dos d[eé]bitos|Caso haja contrapartes|$)", txt, re.IGNORECASE | re.DOTALL)
        if m_cred2: cred_block += "\n" + m_cred2.group(1)
        
        deb_block = ""
        m_deb1 = re.search(r"(?:D[EÉ]BITOS:|- Total dos d[eé]bitos|Destino dos d[eé]bitos[,:].*?)(?:\n|-)(.*?)(?=OUTRAS CONTRAPARTES|Uso do cart[aã]o|___|Caso haja contrapartes|$)", txt, re.IGNORECASE | re.DOTALL)
        if m_deb1: deb_block += m_deb1.group(1)
        m_deb2 = re.search(r"OUTRAS CONTRAPARTES DE D[EÉ]BITO:(.*?)(?=-\s*Suspeitas:|Uso do cart[aã]o|___|Caso haja contrapartes|$)", txt, re.IGNORECASE | re.DOTALL)
        if m_deb2: deb_block += "\n" + m_deb2.group(1)

        card_block = ""
        m_card1 = re.search(r"(?:Uso do cart[aã]o de cr[eé]dito:.*?)(?:\n|-)(.*?)(?=Caso haja contrapartes|-\s*Suspeitas:|$)", txt, re.IGNORECASE | re.DOTALL)
        if m_card1: card_block += m_card1.group(1)
        
        re_cpf_cnpj = re.compile(r"-\s*[\d,.]+%\s*\(R\$\s*([\d.,]+)\s*em\s*(\d+)\s*transa.*?\)\s*(?:via|para)\s*(CPF|CNPJ)\s*([\d.\-\/]+)\s*\((.*?)\)", re.IGNORECASE)
        re_general = re.compile(r"-\s*[\d,.]+%\s*\(R\$\s*([\d.,]+)\s*em\s*(\d+)\s*transa.*?\)\s*(?:para|em|via)\s*(.*?)(?=\.|\n|$)", re.IGNORECASE)
        re_cedente = re.compile(r"([\d,.]+%\s*\(R\$\s*[\d.,]+\s*em\s*\d+\s*transa.*?\)\s*para\s*.*?(?=\.|\n|$))", re.IGNORECASE)
        re_cedente_item = re.compile(r"[\d,.]+%\s*\(R\$\s*([\d.,]+)\s*em\s*(\d+)\s*transa.*?\)\s*para\s*(.*?)$", re.IGNORECASE)

        def parse_block(block, section):
            res = []
            # Isola cada item (que começa com "- XX,XX% (R$")
            items = re.finditer(r"-\s*([\d,.]+%\s*\(R\$\s*[\d.,]+\s*em\s*\d+\s*transa.*?\).*?)(?=-\s*[\d,.]+%\s*\(R\$|-\s*Os\s*[\d,.]+%\s*restantes|$)", block, re.IGNORECASE | re.DOTALL)
            
            for m_item in items:
                line = m_item.group(1).strip()
                if 'restantes' in line.lower() or 'restante' in line.lower(): continue
                
                # Check for "cedentes" multiple items in same line
                if 'principais cedentes' in line.lower() or 'pagamento de boletos' in line.lower():
                    parts = re.split(r'sendo os principais cedentes.*?:\s*', line, flags=re.IGNORECASE)
                    if len(parts) > 1:
                        main_val_m = re.search(r"^([\d,.]+%\s*\(R\$\s*([\d.,]+)\s*em\s*(\d+)\s*transa.*?\)\s*para\s*(.*?))\s*,", parts[0], re.IGNORECASE)
                        if main_val_m:
                            res.append({
                                'Valor (R$)': clean_value(main_val_m.group(2)), 'Qtd Transações': int(main_val_m.group(3)), 'Detalhe': 'Consolidado',
                                ('Origem do Crédito' if section == 'CREDIT' else 'Destino do Débito' if section == 'DEBIT' else 'Estabelecimento'): main_val_m.group(4).strip().upper()
                            })
                        sub_items = re_cedente.findall(parts[1])
                        for s_item in sub_items:
                            m_sub = re_cedente_item.search(s_item)
                            if m_sub:
                                res.append({
                                    'Valor (R$)': clean_value(m_sub.group(1)), 'Qtd Transações': int(m_sub.group(2)), 'Detalhe': 'Boleto/Cedente',
                                    ('Origem do Crédito' if section == 'CREDIT' else 'Destino do Débito' if section == 'DEBIT' else 'Estabelecimento'): m_sub.group(3).strip().upper()
                                })
                        continue
                
                # Para CPF/CNPJ
                match_doc = re_cpf_cnpj.search("- " + line)
                if match_doc and section != 'CARD':
                    res.append({
                        'Valor (R$)': clean_value(match_doc.group(1)), 'Qtd Transações': int(match_doc.group(2)),
                        'Detalhe': f"{match_doc.group(3)}: {match_doc.group(4)}",
                        ('Origem do Crédito' if section == 'CREDIT' else 'Destino do Débito'): match_doc.group(5).strip().upper()
                    })
                    continue
                
                # Genérico
                match_gen = re_general.search("- " + line)
                if match_gen:
                    name_raw = match_gen.group(3)
                    name = re.split(r'[.,;]\s|Segundo pesquisa|sendo a principal', name_raw, flags=re.IGNORECASE)[0].strip().upper()
                    res.append({
                        'Valor (R$)': clean_value(match_gen.group(1)), 'Qtd Transações': int(match_gen.group(2)), 'Detalhe': '',
                        ('Origem do Crédito' if section == 'CREDIT' else 'Destino do Débito' if section == 'DEBIT' else 'Estabelecimento'): name
                    })
            return res

        credits = parse_block(cred_block, 'CREDIT')
        debits = parse_block(deb_block, 'DEBIT')
        cards = parse_block(card_block, 'CARD')
        
        nubank_info_clean = {k: v for k, v in nubank_info.items() if v}
        df_nubank = pd.DataFrame([nubank_info_clean]) if nubank_info_clean else pd.DataFrame()
        return credits, debits, cards, df_nubank

    # --- PARSER 7: PADRÃO GENÉRICO ---
    def _parse_standard_style(txt):
        credits, debits, cards = [], [], []
        txt_proc = re.sub(r'(\s-\s\d{1,3}[.,]\d{1,2}%)', r'\n\1', txt)
        txt_proc = re.sub(r'(Origem dos creditos|Destino dos debitos|Total dos debitos|Uso do cartao de credito)', r'\n\1', txt_proc, flags=re.IGNORECASE)
        lines = txt_proc.split('\n')
        current_section = None
        re_cpf_cnpj = re.compile(r"-\s*([\d,.]+)%\s*\(R\$\s*([\d.,]+)\s*em\s*(\d+)\s*transa.*?\)\s*(?:via|para)\s*(?:CPF|CNPJ)\s*([\d.\-\/]+)\s*\((.*?)\)", re.IGNORECASE)
        re_general = re.compile(r"-\s*([\d,.]+)%\s*\(R\$\s*([\d.,]+)\s*em\s*(\d+)\s*transa.*?\)\s*(?:para|em)\s*(.*)", re.IGNORECASE)
        for line in lines:
            line = line.strip()
            if len(line) < 5: continue
            line_l = line.lower()
            if 'origem dos creditos' in line_l: current_section = 'CREDIT'; continue
            if 'destino dos debitos' in line_l or 'total dos debitos' in line_l: current_section = 'DEBIT'; continue
            if 'uso do cartao' in line_l or 'principais estabelecimentos' in line_l: current_section = 'CARD'; continue
            if current_section and line.startswith('-'):
                val, qtd, name, det = 0.0, 1, "N/A", ""
                match_doc = re_cpf_cnpj.search(line)
                match_gen = None
                if match_doc:
                    val, qtd, det, name = clean_value(match_doc.group(2)), int(match_doc.group(3)), f"Doc: {match_doc.group(4)}", match_doc.group(5).strip().upper()
                else:
                    match_gen = re_general.search(line)
                    if match_gen:
                        val, qtd, name_raw = clean_value(match_gen.group(2)), int(match_gen.group(3)), match_gen.group(4)
                        name = re.split(r'[.,;]\s|Segundo pesquisa|sendo a principal', name_raw, flags=re.IGNORECASE)[0].strip().upper()
                if val > 0:
                    item = {'Valor (R$)': val, 'Qtd Transações': qtd, 'Detalhe': det}
                    if current_section == 'CREDIT': credits.append({**item, 'Origem do Crédito': name})
                    elif current_section == 'DEBIT': debits.append({**item, 'Destino do Débito': name})
                    elif current_section == 'CARD': cards.append({**item, 'Estabelecimento': name})
        return credits, debits, cards

    # --- ROTEADOR DE PARSERS ---
    is_santander = "Valor Recebido:" in text_norm or "Valor Enviado:" in text_norm
    is_bb = "Principais remetentes/depositantes identificados:" in text_norm and not is_santander
    is_caixa = "INFORMAÇÕES CADASTRAIS:" in text_norm and "ORIGEM DOS RECURSOS:" in text_norm and not is_bb
    is_nubank = bool(re.search(r"Informa[cç][õo]es b[aá]sicas de cadastro PF:|Informa[cç][õo]es de atualiza[cç][aã]o cadastral:", text_norm, re.IGNORECASE))
    is_bradesco = "VALOR R$ QTDE REMETENTE" in text_norm or "VALOR R$ QTDE FAVORECIDOS" in text_norm
    is_sicoob = re.search(r"\d{2}/\d{2}/\d{4}\s*-\s*R\$.*?origem:|destino:", text_norm, re.IGNORECASE)
    is_itau = "principal(ais) emitentes(s)" in text_norm or "principal(ais) favorecidos(s)" in text_norm

    df_extra = pd.DataFrame()
    if is_caixa:
        c_data, d_data, card_data, df_extra = _parse_caixa_style(text_norm)
    elif is_nubank:
        c_data, d_data, card_data, df_extra = _parse_nubank_style(text_norm)
    elif is_santander:
        c_data, d_data, card_data, df_extra = _parse_santander_style(text_norm)
    elif is_bradesco:
        c_data, d_data, card_data, df_extra = _parse_bradesco_style(text_norm)
    elif is_bb:
        c_data, d_data, card_data, df_extra = _parse_bb_style(text_norm)
    elif is_sicoob:
        c_data, d_data, card_data = _parse_sicoob_style(text_norm)
    elif is_itau:
        c_data, d_data, card_data = _parse_itau_style(text_norm)
    else:
        c_data, d_data, card_data = _parse_standard_style(text_norm)

    # --- CONSTRUÇÃO DOS DATAFRAMES FINAIS ---
    def build_df(data_list, col_name, final_cols):
        if not data_list: return pd.DataFrame(columns=final_cols)
        df = pd.DataFrame(data_list)
        df_agg = df.groupby(col_name, as_index=False).agg({'Valor (R$)': 'sum', 'Qtd Transações': 'sum', 'Detalhe': 'first'})
        total = df_agg['Valor (R$)'].sum()
        df_agg['Percentual (%)'] = (df_agg['Valor (R$)'] / total * 100) if total > 0 else 0.0
        # Adiciona a coluna Percentual às colunas finais
        final_cols_with_perc = final_cols + ['Percentual (%)']
        # Garante que a ordem seja mantida e que colunas ausentes não quebrem o código
        ordered_cols = [col for col in final_cols_with_perc if col in df_agg.columns]
        return df_agg.sort_values('Valor (R$)', ascending=False)[ordered_cols]

    df_creditos = build_df(c_data, 'Origem do Crédito', CRED_COLS)
    df_debitos = build_df(d_data, 'Destino do Débito', DEB_COLS)
    df_cartao = build_df(card_data, 'Estabelecimento', CARD_COLS)

    # Adiciona a coluna 'Percentual (%)' se ela não existir (para DFs vazios)
    if 'Percentual (%)' not in df_creditos.columns: df_creditos['Percentual (%)'] = pd.NA
    if 'Percentual (%)' not in df_debitos.columns: df_debitos['Percentual (%)'] = pd.NA
    if 'Percentual (%)' not in df_cartao.columns: df_cartao['Percentual (%)'] = pd.NA

    return df_creditos, df_debitos, df_cartao, df_extra
