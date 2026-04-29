# config.py - Configurações e Constantes do RIF Analyst
"""
Módulo de configuração centralizada do RIF Analyst.
Contém todas as constantes, mapeamentos e configurações do sistema.
"""
from __future__ import annotations

# ==============================================
# VERSÃO E METADADOS
# ==============================================
VERSAO = '3.6.0'
DATA_VERSAO = '05/04/2026'
APP_TITLE = "Análise de RIF - NAE/CGU/SC"
APP_ICON = "🔍"

# ==============================================
# LIMITES E CONFIGURAÇÕES DE PROCESSAMENTO
# ==============================================
MAX_CONEXOES_REDE = 600
TIMEOUT_LIMIT = 30 * 60  # 30 minutos em segundos
BENFORD_MIN_SAMPLES = 500  # Mínimo de amostras para análise de Benford

# ==============================================
# MAPEAMENTO DE SEGMENTOS
# ==============================================
SEGMENTO_MAP = {
    '17': "SPA - Loterias: A=Prêmio, B=Aposta(s)/Arrecadação, C=Qtd Premiações, D=Espécie",
    '19': "COAF - Jóias/Pedras/Metais: A=Valor Operação/Proposta, B=Pagamento(s) Espécie",
    '20': "COAF - Bingos: A=Prêmio, B=Aposta(s)/Arrecadação, C=Qtd Premiações",
    '22': "COAF - Bolsas Mercadorias: A=Valor Operação, B=Valor Pagamento(s)",
    '23': "IPHAN - Arte/Antiguidades: A=Valor Operação, B=Pagamento(s) Espécie",
    '24': "COFECI - Imóveis: A=Valor Imóvel, B=Valor Transação/Operação",
    '36': "COAF - Remessas Alternativas: A=Total, B=Transação(ões) Nacional(is), C=Transação(ões) Internacional(is)",
    '21': "COAF - Cartões Crédito: A=Valor Ocorrência(s)",
    '15': "COAF - Factoring: A=Valor Operação/Ativos Vendidos, B=Pago Espécie",
    '37': "SUSEP - Seguros: A=Valor Operação, B=Prêmio/Contribuição/Devolução, C=Quantidade",
    '42': "SFN - Espécie: A=Total, B=Crédito, C=Débito, D=Provisionamento, E=Proposta",
    '41': "SFN - Atípicas: A=Total, B=Crédito, C=Débito, D=Provisionamento, E=Proposta",
    '43': "PREVIC - Previdência Comp.: A=Valor Operação/Contribuição",
    '44': "CVM - Valores Mobiliários: A=Valor",
    '45': "PF - Transporte Valores: A=Valor Transportado, B=Valor Guardado/Custodiado, C=Proposta",
    '46': "Outros Lei 9.613/98: A=Valor total, B=Pago Espécie",
    '47': "Registros Públicos: A=Valor",
    '48': "COAF - Assessoria/Consultoria: A=Valor total, B=Pago Espécie",
    '49': "COAF - Atletas/Artistas: A=Valor total, B=Pago Espécie",
    '50': "Feiras/Exposições: A=Valor",
    '51': "Bens Rurais/Animal Alto Valor: A=Valor total, B=Pago Espécie",
    '52': "COAF - Bens Luxo/Alto Valor: A=Valor total, B=Pago Espécie",
    '53': "DREI - Juntas Comerciais: A=Valor",
    '54': "CFC - Contador: A=Valor",
    '55': "COFECON - Economista: A=Valor",
    '56': "ANS - Planos Saúde: A=Valor",
    '57': "OUTRAS PESSOAS OBRIGADAS: A=Transação(ões) Nacional(is), B=Transação(ões) Internacional(is)",
    '58': "CNJ - Notários/Registradores: A=Valor Operação(ões)",
    '59': "ANM - Mineração: A=Valor Operação(ões)",
    '60': "Lottopar - Aposta Quota Fixa: A=Prêmio(s), B=Aposta(s), C=Outro Tipo",
    '61': "SPA - Aposta Quota Fixa: A=Prêmio(s), B=Aposta(s), C=Outro Tipo",
    '62': "Lottopar - Prognóstico/Passiva: A=Prêmio(s), B=Aposta(s), C=Outro Tipo",
    '63': "Lottopar - Instantânea: A=Prêmio(s), B=Aposta(s), C=Outro Tipo",
    '64': "Lotep - Aposta Quota Fixa: A=Prêmio(s), B=Aposta(s), C=Outro Tipo",
    '65': "Lotep - Loterias: A=Prêmio(s), B=Aposta(s), C=Outro Tipo",
}

# ==============================================
# MAPEAMENTO DE OCORRÊNCIAS
# ==============================================
OCORRENCIA_MAP = {
    '1045': "IV-a) movimentação de recursos incompatível com o patrimônio, a atividade econômica ou a ocupação profissional e a capacidade financeira do cliente. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1047': "IV-c) movimentação de recursos de alto valor, de forma contumaz, em benefício de terceiros. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1074': "IV-ad) recebimento de créditos com o imediato débito dos valores. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1046': "IV-b) transferências de valores arredondados na unidade de milhar ou que estejam um pouco abaixo do limite para notificação de operações. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1049': "IV-e) movimentação de quantia significativa por meio de conta até então pouco movimentada ou de conta que acolha depósito inusitado. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1056': "IV-l) operações que, por sua habitualidade, valor e forma, configurem artifício para burla da identificação da origem, do destino, dos responsáveis ou dos destinatários finais. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1034': "III-d) abertura, movimentação de contas ou realização de operações por detentor de procuração ou de qualquer outro tipo de mandato. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1073': "IV-ac) movimentação de valores incompatíveis com o faturamento mensal das pessoas jurídicas. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1157': "XVII-b) operação atípica em municípios localizados em regiões de extração mineral. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1040': "III-j) incompatibilidade da atividade econômica ou faturamento informados com o padrão apresentado por clientes com o mesmo perfil. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1008': "I-a) depósitos, aportes, saques, pedidos de provisionamento para saque ou qualquer outro instrumento de transferência de recursos em espécie, que apresentem atipicidade em relação à atividade econômica do cliente ou incompatibilidade com a sua capacidade financeira. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1055': "IV-k) recebimento de recursos com imediata compra de instrumentos para a realização de pagamentos ou de transferências a terceiros, sem justificativa. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1012': "I-e) fragmentação de saques em espécie, a fim de burlar limites regulatórios de reportes. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1021': "I-n) depósitos em espécie relevantes em contas de servidores públicos e de qualquer tipo de Pessoas Expostas Politicamente (PEP), conforme elencados no art. 27 da Circular nº 3.978, de 2020, bem como seu representante, familiar ou estreito colaborador. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1053': "IV-i) mudança repentina e injustificada na forma de movimentação de recursos ou nos tipos de transação utilizados. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1059': "IV-o) pagamentos habituais a fornecedores ou beneficiários que não apresentem ligação com a atividade ou ramo de negócio da pessoa jurídica. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1161': "Depósito em espécie de valor igual ou superior a R$50.000,00 (cinquenta mil reais). Banco Central do Brasil - Circular nº 3.978/2020, art. 49-I",
    '971': "Art. 23-II - qualquer operação que envolva o pagamento ou recebimento de valor, por meio de título de crédito emitido ao portador, igual ou superior a R$ 30.000,00 (trinta mil reais), desde que perante o tabelião. CNJ - Provimento 88/2019. Art. 159-II-Provimento 149/2023.",
    '1011': "I-d) fragmentação de depósitos ou outro instrumento de transferência de recurso em espécie, inclusive boleto de pagamento, de forma a dissimular o valor total da movimentação. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1013': "I-f) depósitos ou aportes de grandes valores em espécie, de forma parcelada, principalmente nos mesmos caixas ou terminais de autoatendimento próximos, destinados a uma única conta ou a várias contas em municípios ou agências distintas. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1063': "IV-s) movimentação habitual de recursos financeiros de ou para qualquer tipo de PEP, conforme elencados no art. 27 da Circular nº 3.978, de 2020, bem como seu representante, familiar ou estreito colaborador, não justificada por eventos econômicos. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1042': "III-l) registro de mesmo endereço de e-mail ou Internet Protocol (IP) por pessoas naturais, sem justificativa razoável para tal ocorrência. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1033': "III-c) prestação de informação de difícil ou onerosa verificação. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1020': "I-m) dois ou mais depósitos em terminais de autoatendimento em espécie, no período de cinco dias úteis, com indícios de tentativa de burla para evitar a identificação do depositante. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1079': "V-d) investimentos significativos não proporcionais à capacidade financeira do cliente, ou cuja origem não seja claramente conhecida. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1043': "III-m) informações e documentos apresentados pelo cliente conflitantes com as informações públicas disponíveis. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1158': "XVII-c) operação atípica em municípios localizados em outras regiões de risco. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1044': "III-n) sócios de empresas sem aparente capacidade financeira para o porte da atividade empresarial declarada. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1060': "IV-p) pagamentos ou transferências por pessoa jurídica para fornecedor distante de seu local de atuação, sem fundamentação econômico-financeira. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1032': "III-b) oferecimento de informação falsa. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1115': "X-f) transferências internacionais, inclusive a título de disponibilidade no exterior, nas quais não se justifique a origem dos fundos envolvidos ou que se mostrem incompatíveis com a capacidade financeira ou com o perfil do cliente. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1207': "SUSEP-612-Art.36-VIII) transações cujas características peculiares, principalmente no que se refere às partes envolvidas, valores, forma de realização, instrumentos utilizados, ou pela falta de fundamento econômico ou legal, mesmo que tragam vantagem à sociedade, ao ressegurador ou ao corretor, possam caracterizar indício de lavagem de dinheiro, de financiamento do terrorismo, ou de qualquer outro ilícito. Susep-Circular nº 612, de 18/08/2020.",
    '1114': "X-e) transferências unilaterais que, pela habitualidade, valor ou forma, não se justifiquem ou apresentem atipicidade. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1116': "X-g) exportações ou importações aparentemente fictícias ou com indícios de superfaturamento ou subfaturamento, ou ainda em situações que não seja possível obter informações sobre o desembaraço aduaneiro das mercadorias. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1110': "X-a) operação com pessoas naturais ou jurídicas, inclusive sociedades e instituições financeiras, situadas em países que não apliquem ou apliquem insuficientemente as recomendações do Grupo de Ação contra a Lavagem de Dinheiro e o Financiamento do Terrorismo (Gafi), ou que tenham sede em países ou dependências com tributação favorecida ou regimes fiscais privilegiados, ou em locais onde seja observada a prática contumaz dos crimes previstos na Lei nº 9.613, de 3 de março de 1998, não claramente caracterizadas em sua legalidade e fundamentação econômica. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1058': "IV-n) recebimento de depósitos provenientes de diversas origens, sem fundamentação econômico-financeira, especialmente provenientes de regiões distantes do local de atuação da pessoa jurídica ou distantes do domicílio da pessoa natural. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1064': "IV-t) existência de contas em nome de menores ou incapazes, cujos representantes realizem grande número de operações e/ou operações de valores relevantes. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1163': "Solicitação de provisionamento de saques em espécie de valor igual ou superior a R$50.000,00 (cinquenta mil reais) de que trata o art. 36. Banco Central do Brasil - Circular nº 3.978/2020, art. 49-III",
    '1009': "I-b) movimentações em espécie realizadas por clientes cujas atividades possuam como característica a utilização de outros instrumentos de transferência de recursos, tais como cheques, cartões de débito ou crédito. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1092': "VII-d) movimentações atípicas de recursos por pessoa natural ou jurídica relacionadas a licitações. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1038': "III-h) representação de diferentes pessoas jurídicas ou organizações pelos mesmos procuradores ou representantes legais, sem justificativa razoável para tal ocorrência. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º",
    '1182': "Transferências privadas de recursos e de valores mobiliários sem motivação aparente entre contas de investidores.",
    '1185': "Operações cursadas fora do ambiente de mercado organizado, sem justificativa fundamentada.",
    '1189': "CVM - Operação com jurisdição de alto risco ou deficiências estratégicas de PLD/FTP.",
    '1211': "SUSEP - Variação relevante de importância segurada sem causa aparente.",
    '1215': "Liquidação de prêmios ou aportes por meio de terceiros que não possuam vínculo aparente com o segurado ou participante.",
    '1378': "CNJ - Devedor PJ com valor >= R$ 500k em ato notarial.",
    '1162': "BACEN - Saque em espécie de valor igual ou superior a R$ 100.000,00.",
    '1164': "COAF - Operação vinculada a países ou dependências com tributação favorecida.",
}

# ==============================================
# MAPEAMENTO DE CRITICIDADE (SCORE DE RISCO)
# ==============================================
CRITICIDADE_MAP = {
    # --- CRÍTICO (10 pontos) ---
    # Burla de limites, Fragmentação, PEP, Lavagem explícita e Jurisdições de Risco
    '1011': 'Crítico', '1012': 'Crítico', '1013': 'Crítico', '1020': 'Crítico', 
    '1032': 'Crítico', '1056': 'Crítico', '1063': 'Crítico', '1021': 'Crítico',
    '1110': 'Crítico', '1164': 'Crítico', '1189': 'Crítico', '1207': 'Crítico',
    
    # --- ALTO (5 pontos) ---
    # Incompatibilidade financeira, espécie de alto valor, contas de passagem e licitações
    '971': 'Alto', '1045': 'Alto', '1047': 'Alto', '1055': 'Alto', '1058': 'Alto', 
    '1073': 'Alto', '1074': 'Alto', '1079': 'Alto', '1092': 'Alto', '1115': 'Alto', 
    '1157': 'Alto', '1158': 'Alto', '1161': 'Alto', '1162': 'Alto', '1163': 'Alto', 
    '1182': 'Alto', '1185': 'Alto', '1211': 'Alto', '1215': 'Alto', '1378': 'Alto',
    
    # --- MODERADO (2 pontos) ---
    # Inconsistências cadastrais, comportamentais e uso atípico de terceiros
    '1008': 'Moderado', '1009': 'Moderado', '1033': 'Moderado', '1034': 'Moderado', 
    '1038': 'Moderado', '1040': 'Moderado', '1042': 'Moderado', '1043': 'Moderado', 
    '1044': 'Moderado', '1046': 'Moderado', '1049': 'Moderado', '1053': 'Moderado', 
    '1059': 'Moderado', '1060': 'Moderado', '1064': 'Moderado', '1114': 'Moderado', 
    '1116': 'Moderado',
}

# Pesos para cálculo de score
SCORE_WEIGHTS = {
    'Crítico': 10,
    'Alto': 5,
    'Moderado': 2,
    'Baixo': 1
}

# ==============================================
# CIDADES DE RISCO GEOGRÁFICO
# ==============================================
CIDADES_RISCO = [
    'PONTA PORA', 'CORUMBA', 'FOZ DO IGUACU', 'GUAIRA', 'PACARAIMA', 
    'TABATINGA', 'SANTOS', 'PARANAGUA', 'ITAJAI', 'CACEQUES', 
    'BARRACAO', 'PORTO XAVIER', 'CAPANEMA'
]

# ==============================================
# KEYWORDS SUSPEITAS PARA ANÁLISE DE NARRATIVAS
# ==============================================
KEYWORDS_SUSPEITAS = [
    'LARANJA', 'FACHADA', 'INCOMPATIVEL', 'SEM LASTRO', 'SEM ORIGEM', 
    'RECUSA', 'NERVOSISMO', 'FRACIONAMENTO', 'CORRUPCAO', 'TRAFICO', 
    'ESPECIE VALOR ALTO', 'DOLEIRO', 'TESTA DE FERRO', 'SIMULADA', 'DROGAS'
]

# ==============================================
# CONFIGURAÇÃO DE PARSERS BANCÁRIOS
# ==============================================
BANK_PARSERS = {
    'santander': 'parsers.banks.santander',
    'itau': 'parsers.banks.itau',
    'bradesco': 'parsers.banks.bradesco',
    'caixa': 'parsers.banks.caixa',
    'bb': 'parsers.banks.bb',
    'nubank': 'parsers.banks.nubank',
    'sicoob': 'parsers.banks.sicoob',
    'generic': 'parsers.banks.generic'
}

# ==============================================
# MAPEAMENTO DE CAMPOS DE ESPÉCIE POR SEGMENTO
# ==============================================
ESPECIE_FIELD_MAP = {
    '17': 'ValorCampoD', '19': 'ValorCampoB', '23': 'ValorCampoB', 
    '15': 'ValorCampoB', '46': 'ValorCampoB', '48': 'ValorCampoB', 
    '49': 'ValorCampoB', '51': 'ValorCampoB', '52': 'ValorCampoB'
}

# ==============================================
# LIMIARES E LIMITES DE REPORTE
# ==============================================
LIMIARES_REPORTE = [10000, 50000, 100000, 1000000]
LIMITE_REPORTE_PRINCIPAL = 50000
LIMITE_FRACIONAMENTO = 0.9 * LIMITE_REPORTE_PRINCIPAL

# ==============================================
# COLUNAS ESPERADAS NOS ARQUIVOS CSV
# ==============================================
EXPECTED_COLUMNS = {
    'ocorrencias': ['Indexador', 'idOcorrencia', 'Ocorrencia'],
    'envolvidos': ['Indexador', 'cpfCnpjEnvolvido', 'nomeEnvolvido', 'tipoEnvolvido', 
                   'bitPepCitado', 'bitPessoaObrigadaCitado', 'intServidorCitado'],
    'comunicacoes': ['Indexador', 'idComunicacao', 'Data_da_operacao', 'CodigoSegmento', 'CampoA']
}

# ==============================================
# CONFIGURAÇÃO DE ENCODINGS PARA LEITURA DE CSV
# ==============================================
CSV_ENCODINGS = ['utf-8', 'latin1', 'iso-8859-1', 'cp1252']

# ==============================================
# CONFIGURAÇÃO DA API DO PORTAL DA TRANSPARÊNCIA
# ==============================================
PORTAL_TRANSPARENCIA_URL = "https://api.portaldatransparencia.gov.br/api-de-dados/despesas/documentos-por-favorecido"
# NOTA: O token deve ser configurado via variável de ambiente ou secrets.toml
# NUNCA hardcodar tokens no código fonte!

# ==============================================
# MAPEAMENTO TÉCNICO DAS ABAS
# ==============================================
MAPA_ABAS_REGRAS = {
    'PRINCIPAIS ENVOLVIDOS': 'CPF/CNPJ',
    'TITULARES': 'CPF/CNPJ',
    'OUTROS ENVOLVIDOS': 'CPF/CNPJ',
    'SACADORES': 'CPF/CNPJ',
    'DEPOSITANTES': 'CPF/CNPJ',
    'RECURSOS FEDERAIS': 'CPF/CNPJ',
    'ENVOLV. EMENDAS PARL.': 'CNPJ',
    'ENVOLV. CAND. NAO ELEITOS': 'CPF',
    'ENVOLV. DIRETO DE PEPS': 'CPF',
    'ENVOLV. AGENTES PUBLICOS': 'CPF',
    'ENVOLV. PARENTES AGENTES': 'CPF',
    'ENVOLV. OP. ESPECIAIS': 'ENVOLVIDO (CPF/CNPJ)',
    'ENVOLV. SOCIOS EM OP. ESP': 'CPF/CNPJ',
    'ENVOLV. EM PAR INSTAURADO': 'CNPJ',
    'ENVOLV. DEMANDAS EXT.': 'CPF / CNPJ',
    'ENVOLV. EM OUTROS RIFS CGU': 'CPF / CNPJ',
    'PJ < 5 ANOS DESDE INICIO RIF': 'CNPJ',
    'PF < 21 ANOS DESDE INICIO RIF': 'CPF',
    'PJ SOCIOS RESPONSAVEIS PEPS': 'CNPJ ENVOLVIDO',
    'PJ SOCIOS RESPO. AGENTES': 'CNPJ ENVOLVIDO',
    'PJ BAIX SUSP INATIVAS': 'CNPJ',
    'PJ CLASSIF. SUCESSO': 'CNPJ',
    'PJ COM RISCO ALTO DIKE': 'CNPJ',
    'PJ SOCIO OU RESP DIKE ALTO': 'CNPJ',
    'PJ COM ALERTA ALICE': 'CNPJ',
    'PJ RISCO EXTREMO PRIMUS': 'CNPJ'
}

CHAVES_TEXTO = [
    "INDEXADOR",
    "CPF",
    "CNPJ",
    "ANO",
    "ID COMUNICAÇÃO",
    "IDCOMUNICACAO",
    "IDCOMUNICAÇÃO",
    "idComunicacao",
]

ABAS_REDE = [
    "PRINCIPAIS ENVOLVIDOS",
    "TITULARES",
    "OUTROS ENVOLVIDOS",
    "SACADORES",
    "DEPOSITANTES",
]
