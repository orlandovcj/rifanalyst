#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de teste para o Narrative Extractor v3.1
================================================================================
Este script demonstra o uso do extrator de narrativas RIF.
"""

from narrative_extractor import (
    NarrativeExtractor, 
    exibir_resultado, 
    exportar_json,
    formatar_cpf,
    formatar_cnpj,
    validar_cpf,
    validar_cnpj,
    validar_valor_monetario
)

# Narrativa de teste (formato livre)
# Use raw string (r"...") para evitar warnings de escape sequence
# Ou use string normal mas evite backslashes desnecessários
narrativa_texto = ('INFORMACAO DE KYC: Cliente atua como FARMACEUTICO, informou renda mensal de R$ 11.334,11. Não possui participação societária em empresas. O início do relacionamento ocorreu em 04/2011. Nascido em 07/04/1991. Reside em GUARULHOS - SP. PONTO DE ATENÇÃO: A renda informada, não ampara a movimentação, visto que a conta acolheu o montante a crédito incompatível para com o período analisado. SUSPEIÇÃO: Em análise da movimentação, bem como em suas contrapartes, suspeitamos que o cliente utilize sua conta pessoa física para movimentar recursos de sua atividade informal, não declarada, uma vez que as contrapartes não guardam relação com atividade do cliente. Ademais, a renda informada pelo cliente não ampara os recursos ingressados em conta no período analisado. Em que pese a aparente relação entre a atividade exercida e as contrapartes identificadas, esta comunicação é motivada pelo fato de haver suspeita de movimentação de recursos não declarados, não sendo possível descartar, de acordo com as informações reunidas sobre o cliente, a hipótese de movimentação de recursos na informalidade. CARACTERÍSTICAS DA MOVIMENTAÇÃO: Característica da Movimentação: Período Analisado: 10/03/2023 a 22/08/2023. A conta recebeu a crédito o valor de R$ 1.819.984,55, sendo 78,3% transferência(s) via PIX, 21,7% transferência(s) interbancária(s) e 0,0% depósito(s) em espécie. Os débitos totalizaram R$ 1.752.659,10, sendo 98,79% transferência(s) via PIX, 1,17% pagamento(s) de título(s) e 0,03% saque(s). ORIGEM DOS RECURSOS: Origem dos Recursos: Total a crédito: R$ 1.819.984,55 78,3% (R$ 1.425.105,36), referem-se a 17 transferência(s) via PIX, sendo o(s) principal(ais) emitentes(s): STAR PHARMA DISTRIBUIDORA DE MEDICAMENTOS E CORRELATOS LTDA, 41622520000113 [ISPB 16814330-Berlin Finance Meio de Pagamentos Ei] (R$ 1.361.040,36), LAURA PEREIRA NUCCI, 00049496569889 [416968] (R$ 32.385,00), DROGARIA SANTA INEZ JR LTDA, 43170407000170 [Banco 237] (R$ 24.180,00). 21,7% (R$ 394.879,19), referem-se a 2 transferência(s) interbancária(s), sendo o(s) principal(ais) emitentes(s): BF INSTITUICAO DE PAGAMENTO LTDA, 16814330000150 - Banco 1 (R$ 391.000,00), CAIXA ECONOMICA FEDERAL, 00360305000104 - Banco 104 (R$ 3.879,19). Do total a crédito, o montante de R$ 0,00 (0,0%) se refere a 0 depósito(s) em espécie (autoatendimento e terminal de caixa), sendo 0 (R$ 0,00) depósito(s) inferior(es) a R$ 10.000. Autoatendimento: 0,0% (R$ 0,00) dos depósito(s) em dinheiro no autoatendimento, referem-se a 0 depósito(s) inferior(es) a R$ 10 mil, não sendo possível identificar o proprietário dos recursos. 0,0% (R$ 0,00) dos depósito(s) em dinheiro no autoatendimento, referem-se a 0 depósito(s) superior(es) a R$ 10 mil. Terminal de Caixa: 0,0% (R$ 0,00) dos depósito(s) em dinheiro no terminal de caixa da agência, referem-se a 0 depósito(s) inferior(es) a R$ 10 mil, não sendo possível identificar o proprietário dos recursos. 0,0% (R$ 0,00) dos depósito(s) em dinheiro no terminal de caixa da agência, referem-se a 0 depósito(s) superior(es) a R$ 10 mil. DESTINO DOS RECURSOS: Destino dos Recursos: Total a débito: R$ 1.752.659,10 98,79% (R$ 1.731.516,02), referem-se a 13 transferência(s) via PIX, sendo o(s) principal(ais) favorecidos(s): EMANUELA BATISTA DE SOUZA, 00033097620842 [Banco 260] (R$ 1.339.116,02), 49394096000109 [ISPB 17079937-Pinkbank Brasil -Pagamentos Intelige] (R$ 200.000,00), EBS MEDRADES APOIO ADMINISTRATIVO LTDA, 36347999000197 [Banco 237] (R$ 185.000,00). 1,17% (R$ 20.543,08), referem-se a 3 pagamento(s) de título(s) Do total a débito, o montante de R$ 600,00 (0,03%) se refere a 1 saque(s) em espécie (autoatendimento e terminal de caixa), sendo 1 (R$ 600,00) saque(s) inferior(es) a R$ 10.000 e 0 (R$ 0,00) saque(s) superiores(es) a R$ 10.000. Autoatendimento: 100,0% (R$ 600,00) dos saque(s) em dinheiro no autoatendimento, referem-se a 1 saque(s) inferior(es) a R$ 10 mil. 0,0% (R$ 0,00) dos saque(s) em dinheiro no autoatendimento, referem-se a 0 saque(s) superior(es) a R$ 10 mil. Terminal de Caixa: 0,0% (R$ 0,00) dos saque(s) em dinheiro no terminal de caixa, referem-se a 0 saque(s) inferior(es) a R$ 10 mil. 0,0% (R$ 0,00) dos saque(s) em dinheiro no terminal de caixa, referem-se a 0 saque(s) superior(es) a R$ 10 mil. ENQUADRAMENTO DOS RISCOS E SINAIS DE ALERTA: Movimentação de recursos incompatível com o patrimônio, a atividade econômica ou a ocupação profissional e a capacidade financeira do cliente. Banco Central do Brasil - Carta-Circular nº 4.001/2020, art. 1º.')


def main():
    """Função principal de teste."""
    print("="*80)
    print("🔬 NARRATIVE EXTRACTOR v3.1 - Teste de Extração")
    print("="*80)
    
    # Criar extrator
    extrator = NarrativeExtractor()
    
    # Processar narrativa
    resultado = extrator.processar(narrativa_texto)
    
    # Exibir resultado formatado
    exibir_resultado(resultado)
    
    # Acessar dados programaticamente
    print("\n" + "="*80)
    print("📊 ACESSO PROGRAMÁTICO AOS DADOS")
    print("="*80)
    
    dc = resultado.dados_cadastrais
    print(f"\n📝 Dados Cadastrais:")
    print(f"   Profissão: {dc.profissao}")
    print(f"   Cônjuge: {dc.conjuge_nome}")
    print(f"   CPF Cônjuge: {dc.conjuge_cpf}")
    if dc.conjuge_cpf:
        cpf_valido = validar_cpf(dc.conjuge_cpf)
        print(f"   CPF Válido: {'✓ Sim' if cpf_valido else '✗ Não'}")
    
    if dc.empresas_socio:
        print(f"\n   Empresas como sócio:")
        for emp in dc.empresas_socio:
            cnpj_valido = validar_cnpj(emp['cnpj'])
            status = "✓" if cnpj_valido else "✗"
            print(f"   {status} {emp['nome']}: {emp['cnpj']}")
    
    df = resultado.dados_financeiros
    print(f"\n💰 Dados Financeiros:")
    if df.renda:
        print(f"   Renda: R$ {df.renda:,.2f}")
    if resultado.total_creditos:
        print(f"   Total Créditos: R$ {resultado.total_creditos:,.2f}")
    if resultado.total_debitos:
        print(f"   Total Débitos: R$ {resultado.total_debitos:,.2f}")
    print(f"   Período: {resultado.periodo_analisado}")
    
    # Análise de compatibilidade financeira
    if df.renda and resultado.total_creditos:
        ratio = resultado.total_creditos / df.renda
        print(f"   Rácio Créditos/Renda: {ratio:.1f}x")
        if ratio > 10:
            print(f"   ⚠️  ALERTA: Créditos excedem 10x a renda declarada!")
    
    print(f"\n📥 Contrapartes de Crédito: {len(resultado.contrapartes_credito)}")
    total_cp_credito = sum(cp.valor or 0 for cp in resultado.contrapartes_credito)
    print(f"   Total extraído: R$ {total_cp_credito:,.2f}")
    for i, cp in enumerate(resultado.contrapartes_credito[:10], 1):
        doc_valido = validar_cpf(cp.documento) if cp.tipo_documento == 'CPF' else validar_cnpj(cp.documento)
        status = "✓" if doc_valido else "?"
        print(f"   {status} {cp.nome}: R$ {cp.valor:,.2f} ({cp.qtd_transacoes} trans.)")
    if len(resultado.contrapartes_credito) > 10:
        print(f"   ... e mais {len(resultado.contrapartes_credito) - 10} contrapartes")
    
    print(f"\n📤 Contrapartes de Débito: {len(resultado.contrapartes_debito)}")
    total_cp_debito = sum(cp.valor or 0 for cp in resultado.contrapartes_debito)
    print(f"   Total extraído: R$ {total_cp_debito:,.2f}")
    for i, cp in enumerate(resultado.contrapartes_debito[:10], 1):
        doc_valido = validar_cpf(cp.documento) if cp.tipo_documento == 'CPF' else validar_cnpj(cp.documento)
        status = "✓" if doc_valido else "?"
        print(f"   {status} {cp.nome}: R$ {cp.valor:,.2f} ({cp.qtd_transacoes} trans.)")
    if len(resultado.contrapartes_debito) > 10:
        print(f"   ... e mais {len(resultado.contrapartes_debito) - 10} contrapartes")
    
    print(f"\n⚠️  Transações Suspeitas: {len(resultado.transacoes_suspeitas)}")
    for i, tx in enumerate(resultado.transacoes_suspeitas[:5], 1):
        direcao = "↑" if tx.direcao == 'credito' else "↓"
        print(f"   {i}. {tx.data} | {direcao} {tx.tipo} | R$ {tx.valor:,.2f}")
        print(f"      Contraparte: {tx.contraparte}")
    
    print(f"\n🚨 Alertas: {len(resultado.alertas)}")
    for alerta in resultado.alertas:
        icone = "🔴" if alerta.severidade == "alta" else "🟡"
        print(f"   {icone} [{alerta.severidade.upper()}] {alerta.tipo}")
    
#    # Exportar JSON
#    json_str = exportar_json(resultado)
#    print(f"\n✅ JSON gerado com {len(json_str)} caracteres")
    
    # Salvar JSON em arquivo
#    try:
#        with open("narrativa_processada.json", "w", encoding="utf-8") as f:
#            f.write(json_str)
#        print(f"✅ JSON salvo em: narrativa_processada.json")
#    except Exception as e:
#        print(f"⚠️  Não foi possível salvar o JSON: {e}")
#    
#    return resultado


if __name__ == "__main__":
    main()
