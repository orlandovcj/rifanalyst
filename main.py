#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RIF Analyst 3.4.0 - Aplicação Principal Modular

Esta é a versão modularizada do RIF Analyst, organizada em:
- config: Configurações centralizadas
- core: Carregamento e processamento de dados
- analytics: Detecção de padrões e análise de redes
- visualizations: Gráficos e diagramas
- integrations: APIs externas
- utils: Funções auxiliares
"""
from __future__ import annotations
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import time
import re
import textwrap
from datetime import datetime

# ==============================================
# IMPORTAÇÕES DOS MÓDULOS
# ==============================================
from config import (
    VERSAO, DATA_VERSAO, APP_TITLE, APP_ICON,
    TIMEOUT_LIMIT, SEGMENTO_MAP, OCORRENCIA_MAP, CRITICIDADE_MAP
)

from project_utils.security import (
    init_session_state,
    realizar_limpeza_seguranca,
    check_session_timeout,
    update_activity_timestamp
)

from project_utils.helpers import (
    normalize_string,
    clean_numeric_br,
    format_currency_brl,
    classify_risk_score,
    limpar_valor_portal
)

from core.data_loader import (
    load_data,
    check_columns,
    safe_merge,
    load_all_files,
    prepare_value_columns
)

from core.data_processor import (
    process_raw_data,
    filter_dataframe
)

from analytics.patterns import analyze_suspicious_patterns
from analytics.network import (
    analyze_individual_network,
    create_communication_graph,
    simplify_graph,
    analyze_global_network_actors
)

from visualizations.charts import (
    plot_temporal_evolution,
    plot_bar_top_items,
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

from integrations.portal_transparencia import (
    fetch_portal_transparencia_data,
    verificar_multiplos_anos
)

from excel_loader import load_detalhamento_excel
from integrations.local_ai import (
    extrair_inteligencia_local,
    verificar_conexao_ollama
)

from parsers.narrative_parser import extract_all_financial_data, clean_value
from parsers.narrative_parser import extract_all_financial_data
from parsers.narrative_analyzer import (
    analyze_narrative,
    generate_word_cloud_and_keywords
)

from trilhas_die_tab import render_trilhas_die_tab

import analytics.indicators as rif_ind


# ==============================================
# FUNÇÃO DE RENDERIZAÇÃO REUTILIZÁVEL
# ==============================================
def render_communication_details(selected_indexador: str, df_base: pd.DataFrame, df_display: pd.DataFrame, df_envolvidos_raw_total: pd.DataFrame, key_prefix: str):
    """
    Renderiza a análise detalhada completa para um 'selected_indexador' específico.
    Esta função é reutilizada pela aba 'Ranking de Comunicações'.
    """
    comunicacao_detalhe = df_base[df_base['Indexador_x'].astype(str) == str(selected_indexador)].copy()
    envolvidos_raw = df_envolvidos_raw_total[df_envolvidos_raw_total['Indexador'].astype(str).str.strip() == str(selected_indexador).strip()]
    
    if comunicacao_detalhe.empty:
        st.warning(f"Indexador {selected_indexador} não encontrado.")
        return

    comunicacao_info = comunicacao_detalhe.iloc[0]
    st.subheader(f"🔍 Detalhes da Comunicação: {selected_indexador}")

    # Layout de Cabeçalho (3 Colunas)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("ID Comunicação", comunicacao_info.get('idComunicacao', 'N/A'))
        data_fmt = comunicacao_info.get('Data_da_operacao', pd.NaT)
        if pd.notna(data_fmt):
            st.metric("Data Operação", data_fmt.strftime('%d/%m/%Y'))
        else:
            st.metric("Data Operação", 'N/A')
    with c2:
        st.metric("Comunicante", comunicacao_info.get('nomeComunicante', 'N/A'))
        cidade = comunicacao_info.get('CidadeAgencia', 'N/A')
        uf = comunicacao_info.get('UFAgencia', 'N/A')
        st.metric("Cidade/UF", f"{cidade} / {uf}")
    with c3:
        st.metric("Segmento", comunicacao_info.get('CodigoSegmento', 'N/A'))
        if 'DescricaoCampos' in comunicacao_info:
            st.info(f"**Significado dos campos:** {comunicacao_info['DescricaoCampos']}")
    
    st.divider()
    
    # Seção de Titulares com tags PEP/Servidor
    st.subheader("👤 Titular(es) da Comunicação")
    titulares_df = comunicacao_detalhe[
        comunicacao_detalhe['tipoEnvolvido'].astype(str).str.lower().str.strip().str.contains('titular', na=False)
    ].drop_duplicates(subset=['cpfCnpjEnvolvido'])
    
    if not titulares_df.empty:
        for _, tit in titulares_df.iterrows():
            pep_tag = ' <span style="background-color: #FF6B6B; color: #FFF; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; font-weight: bold;">PEP</span>' if tit.get('bitPepCitado') == True else ""
            srv_tag = ' <span style="background-color: #FFD700; color: #333; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; font-weight: bold;">SERVIDOR</span>' if tit.get('intServidorCitado') == True else ""
            
            st.markdown(f"""
            <div style="background-color: #222226; border: 1px solid #4C4E54; border-radius: 7px; padding: 15px; margin-bottom: 10px;">
                <div style="font-size: 1.2em; font-weight: bold; color: #FAFAFA;">{tit['nomeEnvolvido']} {pep_tag} {srv_tag}</div>
                <div style="color: #ADADAD; font-family: monospace;">{tit['cpfCnpjEnvolvido']}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Nenhum titular identificado.")
    
    # Valores Reportados (5 Colunas)
    st.subheader("💰 Valores Reportados")
    v_cols = st.columns(5)
    for i, c in enumerate(['A', 'B', 'C', 'D', 'E']):
        val = comunicacao_info.get(f'ValorCampo{c}', 0.0)
        v_cols[i].metric(f"Campo {c}", f"R$ {val:,.2f}" if pd.notna(val) else "R$ 0,00")
        
    # Alerta de Renda (Nubank)
    nome_com_str = str(comunicacao_info.get('nomeComunicante', '')).lower()
    if 'nubank' in nome_com_str or 'nu pagamentos' in nome_com_str:
        narrativa_txt = str(comunicacao_info.get('informacoesAdicionais', ''))
        
        # Helper interno para converter valores BRL (com pontos, virgulas ou formatos US acidentais)
        def _parse_brl_value(val):
            if pd.isna(val): return 0.0
            if isinstance(val, (int, float)): return float(val)
            import re
            val_str = str(val).strip()
            # Remove qualquer caracter que não seja dígito, vírgula ou ponto
            val_str = re.sub(r'[^\d.,]', '', val_str)
            # Remove pontos ou vírgulas no final (ex: "20.000,00.")
            val_str = re.sub(r'[.,]+$', '', val_str)
            if not val_str: return 0.0
            # Se tem ambos, checa qual é o decimal (o que aparece por último)
            if ',' in val_str and '.' in val_str:
                if val_str.rfind(',') > val_str.rfind('.'):
                    val_str = val_str.replace('.', '').replace(',', '.')
                else:
                    val_str = val_str.replace(',', '')
            elif ',' in val_str:
                val_str = val_str.replace(',', '.')
            try:
                return float(val_str)
            except ValueError:
                return 0.0

        def _extract_renda_nu(padrao, txt):
            import re
            match = re.search(padrao, txt, re.IGNORECASE)
            if match:
                return _parse_brl_value(match.group(1))
            return 0.0
        
        renda_informada = _extract_renda_nu(r"Renda informada pelo cliente:\s*(?:R\$\s*)?([\d.,]+)", narrativa_txt)
        renda_presumida = _extract_renda_nu(r"Renda presumida:\s*(?:R\$\s*)?([\d.,]+)", narrativa_txt)
        renda_declarada = _extract_renda_nu(r"Renda declarada:\s*(?:R\$\s*)?([\d.,]+)", narrativa_txt)
        
        max_renda = max(renda_informada, renda_presumida, renda_declarada)
        
        import re
        from datetime import datetime
        
        m_periodo = re.search(r"Per[íi]odo analisado:\s*(?:de\s*)?(\d{2}/\d{2}/\d{4})\s*(?:a|at[ée])\s*(\d{2}/\d{2}/\d{4})", narrativa_txt, re.IGNORECASE)
        
        if m_periodo and max_renda > 0:
            dt_inicio_str, dt_fim_str = m_periodo.groups()
            try:
                dt_inicio = datetime.strptime(dt_inicio_str, "%d/%m/%Y")
                dt_fim = datetime.strptime(dt_fim_str, "%d/%m/%Y")
                
                delta_days = (dt_fim - dt_inicio).days
                num_meses = max(1, round(delta_days / 30.4167))
                
                renda_estimada = max_renda * num_meses
                
                # Certifica-se de que o Campo B seja numérico, mesmo que no dataframe venha como string formatada
                valor_receitas = _parse_brl_value(comunicacao_info.get('ValorCampoB', 0.0))
                
                if valor_receitas > renda_estimada:
                    alavancagem = valor_receitas / renda_estimada if renda_estimada > 0 else 0
                    st.error(f"🚩 **INCOMPATIBILIDADE DE RENDA (NUBANK):** Receitas (Campo B) **{alavancagem:.1f}x** superiores à renda estimada no período.")
                    c_renda1, c_renda2, c_renda3 = st.columns(3)
                    c_renda1.metric("Período Analisado", f"{num_meses} meses")
                    c_renda2.metric("Renda Base", f"R$ {max_renda:,.2f}")
                    c_renda3.metric("Renda Est. Período", f"R$ {renda_estimada:,.2f}")
            except Exception:
                pass

    st.divider()
    
    # Ocorrências e Envolvidos
    st.subheader("🚩 Ocorrências")
    ocor_tab = comunicacao_detalhe[['idOcorrencia', 'Ocorrencia']].drop_duplicates()
    st.dataframe(ocor_tab, hide_index=True, width='stretch')
    
    st.subheader("👥 Envolvidos Vinculados")
    if not envolvidos_raw.empty:
        env_disp = envolvidos_raw.copy()
        for col in ['bitPepCitado', 'bitPessoaObrigadaCitado', 'intServidorCitado']:
            if col in env_disp.columns:
                env_disp[col] = env_disp[col].apply(lambda x: "Sim" if str(x).lower() == 'sim' or x == True else "Não")
        
        cols_env = ['cpfCnpjEnvolvido', 'nomeEnvolvido', 'tipoEnvolvido', 'bitPepCitado', 'intServidorCitado']
        if 'agenciaEnvolvido' in env_disp.columns:
            cols_env.append('agenciaEnvolvido')
        if 'contaEnvolvido' in env_disp.columns:
            cols_env.append('contaEnvolvido')
        cols_env = [c for c in cols_env if c in env_disp.columns]
        
        st.dataframe(
            env_disp[cols_env],
            column_config={
                "cpfCnpjEnvolvido": "CPF/CNPJ",
                "nomeEnvolvido": "Nome",
                "tipoEnvolvido": "Papel",
                "bitPepCitado": "PEP",
                "intServidorCitado": "Servidor",
                "agenciaEnvolvido": "Agência",
                "contaEnvolvido": "Conta"
            },
            hide_index=True,
            width='stretch'
        )
    
    # Grafo de Vínculos da Comunicação
    st.subheader("🕸️ Visualização dos Vínculos na Comunicação")
    with st.spinner("Gerando grafo de rede..."):
        G_comm, tits_comm = create_communication_graph(envolvidos_raw)
        if G_comm.number_of_nodes() > 0:
            comm_file = visualize_communication_graph(G_comm, tits_comm)
            if comm_file:
                st.components.v1.html(open(comm_file, 'r', encoding='utf-8').read(), height=500)
                st.html(generate_network_legend())
    
    st.divider()
    
    # NOVO: Diagrama de Fluxo (Sankey Estruturado)
    st.subheader("🌊 Fluxo dos Valores da Comunicação")
    st.info("""
            📊 Diagrama gerado com base nos papeis dos envolvidos na comunicação. O titular aparece ao centro.
            """)
    if not titulares_df.empty:
        titular_cpf = titulares_df['cpfCnpjEnvolvido'].iloc[0]
        titular_nome = titulares_df['nomeEnvolvido'].iloc[0]
        
        col_f1_comm, col_f2_comm = st.columns(2)
        with col_f1_comm:
            v_min_comm = st.number_input("Valor mínimo por vínculo (R$)", min_value=0, value=10000, step=5000, key=f"{key_prefix}_comm_vmin_{selected_indexador}")
        with col_f2_comm:
            n_links_comm = st.slider("Máximo de contrapartes", 5, 30, 10, key=f"{key_prefix}_comm_nlinks_{selected_indexador}")

        with st.spinner("Gerando diagrama de fluxo da comunicação..."):
            fig_sankey_comm = plot_sankey_envolvido_estruturado(comunicacao_detalhe, titular_cpf, titular_nome, min_value=v_min_comm, top_n=n_links_comm)
            if fig_sankey_comm:
                st.plotly_chart(fig_sankey_comm, width='stretch', key=f'{key_prefix}_chart_sankey_comm_{selected_indexador}')
            else:
                st.info("Não há dados de contrapartes suficientes para gerar o diagrama para o titular desta comunicação (considerando filtros aplicados).")
    else:
        st.info("Não foi possível gerar o diagrama de fluxo pois não há um titular identificado na comunicação.")

    # Narrativa e Fluxo Financeiro
    st.subheader("📝 Informações Adicionais")
    st.info("⚠️ IMPORTANTE: Nunca usar LLM abertas para analisar esses dados.")
    
    narrativa = comunicacao_info.get('informacoesAdicionais', '')
    df_cr, df_db, df_card, df_extra = pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    if pd.notna(narrativa) and narrativa.strip() != '':
        df_cr, df_db, df_card, df_extra = extract_all_financial_data(narrativa)
        st.markdown(f'<div style="height: 200px; overflow-y: auto; border: 1px solid #4C4E54; padding: 10px; border-radius: 5px; background-color: #1E1E1E; color: #EEE; margin-bottom: 20px;">{narrativa}</div>', unsafe_allow_html=True)
        
        # Análise de Termos da Narrativa
        st.subheader("📊 Análise de Termos da Narrativa")
        with st.spinner("Analisando narrativa..."):
            wordcloud_result, df_fin_keywords, context_map = generate_word_cloud_and_keywords(narrativa)
            
            # Checa se o resultado é uma imagem (bytes) ou uma string (erro)
            if isinstance(wordcloud_result, bytes):
                st.image(wordcloud_result, caption="Termos mais frequentes na narrativa", width='stretch')
            elif isinstance(wordcloud_result, str):
                st.error(f"Falha na Nuvem de Palavras: {wordcloud_result}")
            elif df_fin_keywords is not None and not df_fin_keywords.empty:
                 st.warning("⚠️ Não foi possível gerar a nuvem de palavras. Verifique a instalação da biblioteca 'wordcloud'.")
            
            if df_fin_keywords is not None and not df_fin_keywords.empty:
                st.markdown("##### Top Termos Financeiros:")
                st.dataframe(df_fin_keywords, hide_index=True, width='stretch')
                
                # Exibir contexto dos termos
                if context_map:
                    with st.expander("📖 Ver contexto dos termos encontrados"):
                        for keyword, snippets in context_map.items():
                            st.markdown(f"**{keyword.upper()}** ({len(snippets)} ocorrências)")
                            for i, snippet in enumerate(snippets):
                                st.markdown(f"_{i+1}._ {snippet}")
                            if keyword != list(context_map.keys())[-1]:
                                st.divider()
            else:
                st.caption("Nenhum termo financeiro relevante identificado na narrativa.")
        
        st.divider()
        st.subheader("🌊 Resumo do Fluxo Financeiro")
        
        # Lógica de Fallback
        if df_cr.empty and df_db.empty:
            st.warning("⚠️ Não foi possível extrair automaticamente um fluxo financeiro das Informações Adicionais. Exibindo fluxo baseado nos papéis registrados.")
            
            df_env_rif = envolvidos_raw.copy()
            df_env_rif['papel_clean'] = df_env_rif['tipoEnvolvido'].astype(str).str.lower().str.strip()
            val_rif = comunicacao_info.get('ValorTotal', 0)
            
            # Sintetizar Origens
            df_cred_sint = df_env_rif[df_env_rif['papel_clean'].isin(['remetente', 'depositante', 'vendedor', 'outorgante'])].copy()
            df_cred_sint = df_cred_sint.rename(columns={'nomeEnvolvido': 'Origem do Crédito'})
            df_cred_sint['Valor (R$)'] = val_rif
            
            # Sintetizar Destinos
            df_deb_sint = df_env_rif[df_env_rif['papel_clean'].isin(['beneficiário', 'beneficiario', 'sacador', 'comprador', 'outorgado'])].copy()
            df_deb_sint = df_deb_sint.rename(columns={'nomeEnvolvido': 'Destino do Débito'})
            df_deb_sint['Valor (R$)'] = val_rif
            
            if not df_cred_sint.empty or not df_deb_sint.empty:
                alvo = titulares_df['nomeEnvolvido'].iloc[0] if not titulares_df.empty else "Titular"
                fig_estruturado = plot_sankey_fluxo(df_cred_sint, df_deb_sint, alvo)
                if fig_estruturado:
                    st.plotly_chart(fig_estruturado, width='stretch', key=f'{key_prefix}_sankey_estrut_{selected_indexador}')
                else:
                    st.caption("O diagrama de fluxo visual não pôde ser gerado (valores nulos ou insuficientes).")
                
                if not df_cred_sint.empty:
                    st.markdown("##### Principais Origens de Crédito (Sintetizado via Papéis)")
                    st.dataframe(df_cred_sint[['Origem do Crédito', 'Valor (R$)']].sort_values('Valor (R$)', ascending=False), hide_index=True, width='stretch')
                
                if not df_deb_sint.empty:
                    st.markdown("##### Principais Destinos de Débito (Sintetizado via Papéis)")
                    st.dataframe(df_deb_sint[['Destino do Débito', 'Valor (R$)']].sort_values('Valor (R$)', ascending=False), hide_index=True, width='stretch')
            else:
                st.info("Não foram encontrados remetentes ou beneficiários cadastrados nos papéis da comunicação para sintetizar o fluxo.")
        else:
            # Caso Normal: Texto extraído com sucesso
            st.info("""
            📊 Fluxo extraído automaticamente das Informações Adicionais.
            
            ⚠️ **IMPORTANTE:** É possível que esses dados estejam incompletos.  
            Os valores aqui informados não substituem a análise mais detida do conteúdo do campo Informações Adicionais.
            """)
            alvo = titulares_df['nomeEnvolvido'].iloc[0] if not titulares_df.empty else "Titular"
            fig_texto = plot_sankey_fluxo(df_cr, df_db, alvo)
            if fig_texto:
                st.plotly_chart(fig_texto, width='stretch', key=f'{key_prefix}_sankey_texto_{selected_indexador}')
            
            if not df_cr.empty:
                st.markdown("##### Principais Origens de Crédito")
                st.dataframe(df_cr.sort_values('Valor (R$)', ascending=False), hide_index=True, width='stretch')
            
            if not df_db.empty:
                st.markdown("##### Principais Destinos de Débito")
                st.dataframe(df_db.sort_values('Valor (R$)', ascending=False), hide_index=True, width='stretch')
            
            if not df_card.empty:
                st.markdown("##### Principais Gastos no Cartão")
                st.dataframe(df_card.sort_values('Valor (R$)', ascending=False), hide_index=True, width='stretch')

        st.divider()
        st.subheader("🔬 Análise Estruturada da Narrativa")

        # Exibir informações adicionais (ex: Nubank) se existirem
        if df_extra is not None and not df_extra.empty:
            st.info("ℹ️ **Extraído de Informações Adicionais**")
            
            suspeitas_text = ""
            if 'Suspeitas' in df_extra.columns:
                suspeitas_text = df_extra['Suspeitas'].iloc[0]
                df_extra = df_extra.drop(columns=['Suspeitas'])

            # Transpor para melhor visualização (Chave -> Valor)
            if not df_extra.empty and not df_extra.columns.empty:
                df_extra_t = df_extra.T.reset_index()
                df_extra_t.columns = ['Campo', 'Valor']
                # st.dataframe(df_extra_t, hide_index=True, width='stretch')
                
                # Renderização via HTML/CSS customizado para permitir quebra de linha
                html_table = df_extra_t.to_html(index=False, escape=True, border=0, classes='wrap-table')
                custom_css = """
                <style>
                .wrap-table {
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 1rem;
                }
                .wrap-table th, .wrap-table td {
                    text-align: left;
                    padding: 8px;
                    border-bottom: 1px solid rgba(128, 128, 128, 0.2);
                    word-wrap: break-word;
                    white-space: normal;
                }
                </style>
                """
                # st.markdown(custom_css + html_table, unsafe_allow_html=True)
                st.html(custom_css + html_table)
                
            if suspeitas_text:
                st.markdown("##### 🚩 Suspeitas e Marcações de Risco")
                st.markdown(f'<div style="border: 1px solid #4C4E54; padding: 15px; border-radius: 5px; background-color: #2E1B1B; color: #EEE; margin-bottom: 20px;">{suspeitas_text}</div>', unsafe_allow_html=True)

        with st.spinner("Extraindo dados estruturados da narrativa..."):
            analysis_results = analyze_narrative(narrativa)
            
            if not analysis_results:
                st.info("""
                    📊 Não foi possível obter mais informações estruturadas da narrativa automaticamente.
                    
                    ⚠️ Considere analisar o conteúdo completo das Informações Adicionais para uma compreensão mais detalhada.
                    """)                
            else:
                # Define titles for each dataframe key
                titles = {
                    "kyc": "📄 Resumo do Perfil (KYC)",
                    "participacoes": "🏢 Participações Societárias Declaradas",
                    "resumo_movimentacao": "📈 Resumo da Movimentação",
                    "composicao_creditos": "➡️ Composição dos Créditos",
                    "composicao_debitos": "⬅️ Composição dos Débitos",
                    "principais_credores": "💳 Principais Remetentes (Crédito)",
                    "principais_devedores": "💸 Principais Favorecidos (Débito)",
                    "vinculos_risco": "🚩 Vínculos de Risco Apontados",
                    "notas_adicionais": "📝 Notas Adicionais"
                }
                
                for key, df in analysis_results.items():
                    if not df.empty:
                        st.markdown(f"##### {titles.get(key, key.replace('_', ' ').title())}")
                        st.dataframe(df, hide_index=True, width='stretch')

        # =================================================
        #  NOVA SEÇÃO: ASSISTENTE DE INTELIGÊNCIA LOCAL (IA)
        # =================================================
        st.divider()
        st.subheader("🤖 Assistente de Inteligência Local (Ollama)")

        # Chave única para o estado de confirmação desta comunicação
        # NOVA CHAVE para armazenar o resultado da IA na sessão
        confirm_key = f"confirm_ai_{key_prefix}_{selected_indexador}"
        result_key = f"result_ai_{key_prefix}_{selected_indexador}"

        # Botão inicial para acionar o fluxo de confirmação
        if st.button("🧠 Gerar Análise Estruturada por IA", key=f"btn_ia_start_{key_prefix}_{selected_indexador}"):
            erro_conexao = verificar_conexao_ollama()
            if erro_conexao:
                st.warning(erro_conexao.replace("ERRO_OLLAMA_OFFLINE: ", ""))
            elif narrativa and len(narrativa) > 50:
                st.session_state[confirm_key] = True
                if result_key in st.session_state:
                    del st.session_state[result_key]
                st.rerun()
            else:
                st.warning("A narrativa é muito curta ou inexistente para ser analisada pela IA.")
                if confirm_key in st.session_state:
                    st.session_state[confirm_key] = False

        # Bloco 1: Exibe a confirmação e executa a IA
        if st.session_state.get(confirm_key, False):
            st.warning(
                "**Atenção:** A análise por IA local pode demorar vários minutos, especialmente em computadores com menor poder de processamento. Deseja continuar?"
            )
            col1_confirm, col2_confirm, _ = st.columns([1, 1, 3])
            with col1_confirm:
                if st.button("✅ Sim, iniciar análise", key=f"btn_ia_confirm_{key_prefix}_{selected_indexador}"):
                    with st.spinner("Analisando narrativa via IA local... Por favor, aguarde."):
                        # SALVA O RESULTADO NA SESSÃO em vez de tentar exibir aqui
                        st.session_state[result_key] = extrair_inteligencia_local(narrativa)

                    st.session_state[confirm_key] = False
                    st.rerun()

            with col2_confirm:
                if st.button("❌ Não, cancelar", key=f"btn_ia_cancel_{key_prefix}_{selected_indexador}"):
                    st.session_state[confirm_key] = False
                    if result_key in st.session_state:
                        del st.session_state[result_key] # Limpa resultado se cancelar
                    st.rerun()

        # Bloco 2: Exibe o resultado que foi salvo na sessão
        if result_key in st.session_state:
            dados_ia = st.session_state[result_key]
            if dados_ia:
                # Sempre exibe a análise textual, se houver
                if dados_ia.get("text_analysis"):
                    with st.expander("Ver análise textual completa da IA", expanded=False):
                        st.write(dados_ia["text_analysis"])

                # Exibe o erro, se houver
                if dados_ia.get("erro"):
                    st.error(f"A IA retornou um erro: {dados_ia['erro']}")

                # Processa e exibe os dados do JSON, se existirem
                json_data = dados_ia.get("json_data")
                if json_data:
                    banco = json_data.get("identificacao_banco", "N/A")
                    st.success(f"📌 Relatório identificado como padrão: **{banco}**")
                    col_ia1, col_ia2 = st.columns(2)
                    with col_ia1:
                        st.info("👤 **Dossiê do Perfil (KYC)**")
                        perfil = json_data.get("perfil_cliente", {}) or {}
                        st.write(f"**Atividade:** {perfil.get('atividade_profissional', 'N/A')}")
                        st.write(f"**Renda/Fat.:** {perfil.get('renda_mensal_informada') or perfil.get('faturamento_anual') or 'N/A'}")
                        st.write(f"**PEP:** {perfil.get('pep', 'N/A')}")
                        st.write(f"**Mídia Negativa:** {perfil.get('midia_negativa', 'N/A')}")
                    with col_ia2:
                        st.warning("🚩 **Matriz de Suspeitas e Riscos**")
                        riscos = json_data.get("analise_risco", {}) or {}
                        suspeitas = riscos.get("suspeitas_pld", [])
                        if isinstance(suspeitas, list):
                            for s in suspeitas: st.write(f"⚠️ {s}")
                        bandeiras = riscos.get("bandeiras_vermelhas", [])
                        if isinstance(bandeiras, list):
                            for b in bandeiras: st.write(f"🚩 {b}")
                        vinculos = riscos.get("vinculos_identificados", [])
                        if isinstance(vinculos, list):
                            for v in vinculos: st.write(f"🔗 {v}")
                    st.markdown("##### 🌊 Principais Contrapartes Detectadas pela IA")
                    contrapartes = json_data.get("principais_contrapartes", [])
                    if contrapartes: st.table(pd.DataFrame(contrapartes))
                    st.markdown("---")
                    st.markdown(f"**📝 Conclusão da IA:** _{json_data.get('conclusao_ia', 'Sem resumo disponível.')}_")
                elif not dados_ia.get("erro"): # caso não haja erro mas também não haja json
                     st.info("A IA retornou uma análise textual, mas não foi possível extrair dados estruturados em JSON.")

            else:
                st.error("Erro ao processar a resposta da IA. A resposta foi nula ou malformada. Tente novamente.")
    else:
        st.info("Sem narrativa disponível para esta comunicação.")


def render_individual_details(selected_cpf_individual: str, df_display: pd.DataFrame, df_final_loaded: pd.DataFrame, df_ocorrencias: pd.DataFrame, df_comunicacoes: pd.DataFrame, df_envolvidos: pd.DataFrame, key_prefix: str):
    """
    Renderiza a análise detalhada completa para um 'selected_cpf_individual' específico.
    Esta função é reutilizada pela aba 'Análise Individual' e 'Ranking de Envolvidos'.
    """
    envolvido_data = df_display[df_display['cpfCnpjEnvolvido'] == selected_cpf_individual].copy()
    
    if not envolvido_data.empty:
        nome = envolvido_data['nomeEnvolvido'].iloc[0] if not envolvido_data['nomeEnvolvido'].empty else "Nome Desconhecido"
        st.subheader(f"Análise de {nome} ({selected_cpf_individual})")
        
        # ===== MÉTRICAS INDIVIDUAIS =====
        col1_ind, col2_ind, col3_ind, col4_ind, col5_ind = st.columns(5)
        col1_ind.metric("Total Comunicações (Filtradas)", envolvido_data['idComunicacao'].nunique())
        
        valid_indexadores_ind = envolvido_data['Indexador_x'].unique()
        valor_total_ind_real = df_comunicacoes[
            df_comunicacoes['Indexador'].isin(valid_indexadores_ind)
        ]['ValorCampoA'].sum()
        col2_ind.metric("Valor Total (R$) (Soma CampoA)", f"R$ {valor_total_ind_real:,.2f}")
        
        pep_flag = envolvido_data['bitPepCitado'].any()
        obr_flag = envolvido_data['bitPessoaObrigadaCitado'].any()
        ser_flag = envolvido_data['intServidorCitado'].any()
        col3_ind.metric("PEP", "✅ Sim" if pep_flag else "Não")
        col4_ind.metric("Pessoa Obrigada", "✅ Sim" if obr_flag else "Não")
        col5_ind.metric("Servidor Público", "✅ Sim" if ser_flag else "Não")
        
        # ===== ANÁLISE DE ALAVANCAGEM =====
        papeis_alvo = envolvido_data['tipoEnvolvido'].astype(str).str.lower().str.strip().unique()
        import unicodedata
        papeis_alvo_clean = [unicodedata.normalize('NFKD', p).encode('ASCII', 'ignore').decode('utf-8') for p in papeis_alvo]
        papeis_protagonistas = ['titular', 'titular da conta', 'socio', 'comunicado', 'comunicado principal', 'investigado', 'cliente', 'procurador', 'representante', 'responsavel', 'administrador']
        is_protagonista = any(p in papeis_protagonistas for p in papeis_alvo_clean)
        
        if is_protagonista:
            st.markdown("---")
            c_det1, c_det2 = st.columns([1, 2])
            
            from project_utils.helpers import extrair_capital_social, extrair_renda_mensal, extrair_faturamento
            
            faturamento_anual = envolvido_data['informacoesAdicionais'].apply(extrair_faturamento).max()
            cap_social = envolvido_data['informacoesAdicionais'].apply(extrair_capital_social).max()
            renda_mensal = envolvido_data['informacoesAdicionais'].apply(extrair_renda_mensal).max()
            
            if faturamento_anual > 0 or cap_social > 0:
                base_comparacao = faturamento_anual if faturamento_anual > 0 else cap_social
                label_base = "Faturamento Anual" if faturamento_anual > 0 else "Capital Social"
                alavancagem_pj = valor_total_ind_real / base_comparacao if base_comparacao > 0 else 0
                
                with c_det1:
                    st.metric(f"{label_base} Identificado", f"R$ {base_comparacao:,.2f}")
                
                with c_det2:
                    threshold = 5 if faturamento_anual > 0 else 100
                    if alavancagem_pj > threshold:
                        st.error(f"🚩 **INCOMPATIBILIDADE OPERACIONAL:** Movimentação **{alavancagem_pj:.1f}x** superior ao {label_base}.")
                    else:
                        st.success(f"✅ Índice de Compatibilidade PJ: {alavancagem_pj:.1f}x")
            elif renda_mensal > 0:
                alavancagem_pf = valor_total_ind_real / (renda_mensal * 12) if renda_mensal > 0 else 0
                
                with c_det1:
                    st.metric("Renda Mensal Declarada", f"R$ {renda_mensal:,.2f}")
                with c_det2:
                    if alavancagem_pf > 10:
                        st.error(f"🚩 **INCOMPATIBILIDADE PATRIMONIAL:** Movimentação **{alavancagem_pf:.1f}x** superior à Renda Anual.")
                    else:
                        st.info(f"✅ Compatibilidade Financeira: {alavancagem_pf:.1f}x a Renda Anual.")

        # ===== COMUNICAÇÕES VINCULADAS =====
        st.markdown("---")
        st.subheader("💬 Comunicações Vinculadas")
        
        df_comms_alvo = df_display[df_display['cpfCnpjEnvolvido'] == selected_cpf_individual].copy()
        
        if not df_comms_alvo.empty:
            id_comms_alvo = df_comms_alvo['Indexador_x'].unique()
            df_counts = df_final_loaded[df_final_loaded['Indexador_x'].isin(id_comms_alvo)]
            counts_map = df_counts.groupby('Indexador_x')['cpfCnpjEnvolvido'].nunique().to_dict()
            df_comms_alvo['Qtd_Envolvidos'] = df_comms_alvo['Indexador_x'].map(counts_map)
            
            cols_financeiras = ['ValorCampoA', 'ValorCampoB', 'ValorCampoC', 'ValorCampoD', 'ValorCampoE']
            cols_show = ['Indexador_x', 'idComunicacao', 'Data_da_operacao', 'nomeComunicante', 'Qtd_Envolvidos'] + cols_financeiras
            if 'DescricaoCampos' in df_comms_alvo.columns:
                cols_show.append('DescricaoCampos')

            cols_show = [c for c in cols_show if c in df_comms_alvo.columns]
            df_comms_final = df_comms_alvo.drop_duplicates(subset=['Indexador_x'])[cols_show]

            # Formatação das colunas de valor
            column_config_dinamica = {
                "Indexador_x": "Indexador",
                "idComunicacao": "ID Comunicação",
                "Data_da_operacao": st.column_config.DateColumn("Data Operação", format="DD/MM/YYYY"),
                "nomeComunicante": "Comunicante",
                "Qtd_Envolvidos": st.column_config.NumberColumn("Envolvidos", format="%d"),
                "DescricaoCampos": st.column_config.TextColumn("Contexto", width="medium")
            }
            for col in cols_financeiras:
                if col in df_comms_final.columns:
                    df_comms_final[f'{col}_fmt'] = df_comms_final[col].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    # Adiciona a coluna formatada ao column_config
                    column_config_dinamica[f'{col}_fmt'] = st.column_config.TextColumn(f"Valor {col[-1]}")

            # Garante que as colunas a serem exibidas no st.dataframe sejam as formatadas
            cols_to_display_final = ['Indexador_x', 'idComunicacao', 'Data_da_operacao', 'nomeComunicante', 'Qtd_Envolvidos']
            for col in cols_financeiras:
                if f'{col}_fmt' in df_comms_final.columns:
                    cols_to_display_final.append(f'{col}_fmt')
            if 'DescricaoCampos' in df_comms_final.columns:
                cols_to_display_final.append('DescricaoCampos')
            
            # Filtra colunas que de fato existem no dataframe final
            cols_to_display_final = [c for c in cols_to_display_final if c in df_comms_final.columns]

            st.dataframe(df_comms_final[cols_to_display_final], width='stretch', hide_index=True, column_config=column_config_dinamica)

        st.markdown("---")
        st.subheader("📋 Comunicações, Ocorrências e Papéis")

        # Filtro de Papel (afeta as seções abaixo)
        envolvido_data_to_display = envolvido_data.copy()
        selected_roles = []
        if 'tipoEnvolvido' in envolvido_data_to_display.columns:
            available_roles = sorted(envolvido_data_to_display['tipoEnvolvido'].unique().tolist())
            if len(available_roles) > 1:
                selected_roles = st.multiselect(
                    "Filtrar por Papel Desempenhado (afeta as seções abaixo):",
                    options=available_roles,
                    key=f"{key_prefix}_role_filter_{selected_cpf_individual}"
                )
                if selected_roles:
                    envolvido_data_to_display = envolvido_data_to_display[
                        envolvido_data_to_display['tipoEnvolvido'].isin(selected_roles)
                    ]

        cols_to_show_base = ['Indexador_x', 'idComunicacao', 'Data_da_operacao', 'Ocorrencia', 'CidadeAgencia', 'NumeroAgencia', 'tipoEnvolvido', 'CodigoSegmento', 'DescricaoCampos']
        cols_to_show_vals = ['ValorTotal']
        cols_to_show_info = ['informacoesAdicionais']
        cols_exist = [col for col in cols_to_show_base + cols_to_show_vals + cols_to_show_info if col in envolvido_data_to_display.columns]
        
        st.dataframe(envolvido_data_to_display[cols_exist], width='stretch', hide_index=True, column_config={k: v for k, v in {
            "Indexador_x": "Indexador", "idComunicacao": st.column_config.TextColumn("ID Com.", width="small"),
            "Data_da_operacao": st.column_config.DatetimeColumn("Data Operação", format="DD/MM/YYYY HH:mm"),
            "Ocorrencia": st.column_config.TextColumn("Ocorrência", width="medium"), "CidadeAgencia": "Cidade", "NumeroAgencia": "Agência",
            "tipoEnvolvido": "Papel", "CodigoSegmento": "Seg.", "DescricaoCampos": st.column_config.TextColumn("Descrição Campos", width="medium"),
            "ValorTotal": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
            "informacoesAdicionais": st.column_config.TextColumn("Info Adicional", width="large")
        }.items() if k in cols_exist})
        
        if 'Data_da_operacao' in envolvido_data_to_display.columns and pd.api.types.is_datetime64_any_dtype(envolvido_data_to_display['Data_da_operacao']):
            envolvido_data_clean = envolvido_data_to_display.dropna(subset=['Data_da_operacao'])
            if not envolvido_data_clean.empty:
                temporal_ind = envolvido_data_clean.groupby(envolvido_data_clean['Data_da_operacao'].dt.date).size().reset_index(name='Comunicações')
                fig_ind = px.line(temporal_ind, x='Data_da_operacao', y='Comunicações', title='Comunicações ao Longo do Tempo (Individual)', markers=True)
                st.plotly_chart(fig_ind, width='stretch', key=f'{key_prefix}_chart_temporal_ind_{selected_cpf_individual}')
        
        st.subheader("⚠️ Padrões Suspeitos Identificados (Filtrados)")
        df_alertas_ind = analyze_suspicious_patterns(df_display, df_ocorrencias, df_comunicacoes, df_envolvidos)
        if not df_alertas_ind.empty:
            detalhes_alvo = df_alertas_ind[df_alertas_ind['cpfCnpj'] == selected_cpf_individual].copy()
            
            # Filtra os alertas com base nos papéis selecionados
            valid_indexadores_filtrados = envolvido_data_to_display['Indexador_x'].unique()
            detalhes_alvo_filtrados = detalhes_alvo[detalhes_alvo['Indexador'].isin(valid_indexadores_filtrados)]

            if not detalhes_alvo_filtrados.empty:
                st.dataframe(detalhes_alvo_filtrados[['Indexador', 'idComunicacao', 'Motivo', 'Risco', 'Pontos']], width='stretch', hide_index=True, column_config={
                    "Indexador": "Indexador", "idComunicacao": "ID Comunicação", "Motivo": st.column_config.TextColumn("Descrição do Alerta", width="large"),
                    "Risco": st.column_config.TextColumn("Nível", width="small"), "Pontos": st.column_config.NumberColumn("Pts", format="%d")
                })
            else:
                st.info("Nenhum padrão suspeito encontrado para os papéis selecionados.")
        else:
            st.info("Nenhum padrão suspeito detectado para este envolvido.")
            
        # ===== DETALHAMENTO DE MOVIMENTAÇÕES EM ESPÉCIE (INDIVIDUAL) =====
        st.subheader("💵 Detalhamento de Movimentações em Espécie")
        st.caption("Comunicações do envolvido com ocorrências que indicam uso de espécie.")

        especie_ocorrencia_ids = sorted(list(set(['1008', '1009', '1011', '1012', '1013', '1020', '1021', '1161', '1162', '1163', '971'])))
        
        # Use a filtered dataframe based on the role filter from above
        df_esp_individual = envolvido_data_to_display[envolvido_data_to_display['idOcorrencia'].isin(especie_ocorrencia_ids)].copy()

        if not df_esp_individual.empty:
            # The data is already per-communication for the individual, so we can display it directly
            df_esp_individual_final = df_esp_individual.groupby(
                ['Indexador_x', 'Ocorrencia', 'DescricaoCampos', 'tipoEnvolvido']
            ).agg({'ValorTotal': 'max'}).reset_index()

            df_esp_individual_final = df_esp_individual_final.sort_values('ValorTotal', ascending=False)
            df_esp_individual_final['Valor_Especie_fmt'] = df_esp_individual_final['ValorTotal'].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            
            st.dataframe(
                df_esp_individual_final[['Indexador_x', 'Valor_Especie_fmt', 'tipoEnvolvido', 'Ocorrencia', 'DescricaoCampos']],
                width='stretch',
                hide_index=True,
                column_config={
                    "Indexador_x": "Indexador",
                    "Valor_Especie_fmt": "Valor da Operação (R$)",
                    "tipoEnvolvido": "Papel",
                    "Ocorrencia": st.column_config.TextColumn("Ocorrência", width="large"),
                    "DescricaoCampos": st.column_config.TextColumn("Descrição do Segmento", width="medium")
                }
            )
        else:
            st.info("Nenhuma comunicação com ocorrência de movimentação em espécie encontrada para este envolvido (considerando filtros aplicados).")

        st.divider()
        st.subheader("📊 Relacionamento com Contrapartes (Força dos Vínculos)")
        fig_rel = plot_relationship_strength(df_display, selected_cpf_individual)
        if fig_rel is not None:
            st.plotly_chart(fig_rel, width='stretch', key=f'{key_prefix}_chart_rel_contrapartes_{selected_cpf_individual}')
        else:
            st.caption("Não foi possível identificar contrapartes suficientes para este envolvido nos dados filtrados.")
            
        st.divider()
        st.subheader("🌊 Diagrama de Fluxo (Sankey Estruturado)")
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            v_min_ind = st.number_input("Valor mínimo por vínculo (R$)", min_value=0, value=10000, step=5000, key=f"{key_prefix}_ind_vmin_{selected_cpf_individual}")
        with col_f2:
            n_links_ind = st.slider("Máximo de contrapartes", 5, 30, 10, key=f"{key_prefix}_ind_nlinks_{selected_cpf_individual}")
        
        with st.spinner("Gerando diagrama de fluxo..."):
            # Filtra os dados de exibição para o Sankey com base nos papéis
            df_sankey = df_display.copy()
            if selected_roles:
                valid_indexadores_sankey = envolvido_data_to_display['Indexador_x'].unique()
                df_sankey = df_display[df_display['Indexador_x'].isin(valid_indexadores_sankey)]

            fig_sankey_ind = plot_sankey_envolvido_estruturado(df_sankey, selected_cpf_individual, nome, min_value=v_min_ind, top_n=n_links_ind)
            if fig_sankey_ind:
                st.plotly_chart(fig_sankey_ind, width='stretch', key=f'{key_prefix}_chart_sankey_ind_{selected_cpf_individual}')
            else:
                st.info("Não há dados de contrapartes registrados como remetentes ou beneficiários para o filtro selecionado.")
        
        st.divider()
        st.subheader("🕸️ Análise de Rede de Relacionamentos")
        with st.spinner("Analisando rede de relacionamentos..."):
            G_completo, partition, _ = analyze_individual_network(df_final_loaded, selected_cpf_individual)
            G_simplificado = simplify_graph(G_completo, selected_cpf_individual)

            state_key = f'show_full_network_{key_prefix}_{selected_cpf_individual}'
            if state_key not in st.session_state:
                st.session_state[state_key] = False

            if st.button("Expandir/Recolher Rede Completa", key=f"toggle_net_{key_prefix}_{selected_cpf_individual}"):
                st.session_state[state_key] = not st.session_state[state_key]

            if st.session_state[state_key]:
                st.caption("Exibindo rede completa.")
                if G_completo.number_of_edges() > 600:
                    st.warning(f"A rede completa é grande ({G_completo.number_of_edges()} conexões) e pode tornar a navegação mais lenta.")
                
                if G_completo.number_of_nodes() > 0:
                    network_file = visualize_network(G_completo, partition, selected_cpf=selected_cpf_individual)
                    if network_file:
                        st.components.v1.html(open(network_file, 'r', encoding='utf-8').read(), height=750)
                else:
                    st.info("Nenhuma conexão encontrada para a rede completa.")
            else:
                st.caption("Exibindo rede simplificada (conexões diretas). Clique no botão para expandir.")
                if G_simplificado.number_of_nodes() > 0:
                    network_file = visualize_network(G_simplificado, partition, selected_cpf=selected_cpf_individual)
                    if network_file:
                        st.components.v1.html(open(network_file, 'r', encoding='utf-8').read(), height=750)
                else:
                    st.info("Nenhuma conexão direta encontrada para este envolvido.")
    else:
        st.warning("Nenhum dado encontrado para este envolvido com os filtros atuais.")

# ==============================================
# CONFIGURAÇÃO DA PÁGINA
# ==============================================
st.set_page_config(
    page_title=APP_TITLE,
    layout="wide",
    page_icon=APP_ICON
)


# ==============================================
# INICIALIZAÇÃO DE SESSÃO
# ==============================================
init_session_state()


# ==============================================
# CONTROLE DE TIMEOUT
# ==============================================
if check_session_timeout(TIMEOUT_LIMIT):
    realizar_limpeza_seguranca()
    st.error("🚨 Sessão expirada por inatividade. Dados removidos por segurança.")
    st.info("Por favor, recarregue a página e faça o upload dos arquivos novamente.")
    st.stop()

update_activity_timestamp()


# ==============================================
# INTERFACE PRINCIPAL
# ==============================================
st.title(f"🔍 RIF Analyst {VERSAO}")
st.caption(f"Análise de RIF - NAE/CGU/SC - Versão {VERSAO} - {DATA_VERSAO}")


# ==============================================
# SIDEBAR: UPLOAD DE ARQUIVOS
# ==============================================
st.sidebar.header("📤 Carregamento de Dados")
v_id = st.session_state.get('uploader_id', 0)

# Seletor da fonte de dados
data_source = st.sidebar.radio(
    "Escolha a fonte dos dados:",
    ("Dados Originais", "Dados Anonimizados"),
    key="data_source_selector"
)

# Inputs de arquivo e botão de processamento
file_ocorrencias = None
file_envolvidos = None
file_comunicacoes = None
file_anonimizado = None
uploaded_files = None

if data_source == "Dados Originais":
    uploaded_files = st.sidebar.file_uploader(
        "Carregar arquivos (Ocorrências, Envolvidos, Comunicações)", 
        type=['csv'], 
        accept_multiple_files=True,
        key=f"up_mult_{v_id}"
    )
    uploaded_excel_file = st.sidebar.file_uploader(
        "Carregar Planilha de Detalhamento RIF (Detalhamento_RIF_*.xlsx)",
        type=['xlsx'],
        key=f"up_excel_{v_id}"
    )
else:
    file_anonimizado = st.sidebar.file_uploader(
        "RIF_Consolidado_Anonimizado.csv", type=['csv'], key=f"up_anon_{v_id}"
    )

process_button = st.sidebar.button("Processar Arquivos Carregados")


# ==============================================
# PROCESSAMENTO DE DADOS
# ==============================================
if process_button:
    # Lógica para Dados Originais
    if data_source == "Dados Originais":
        if 'rif_confirmation_needed' not in st.session_state:
            st.session_state.rif_confirmation_needed = False
        if 'files_for_processing' not in st.session_state:
            st.session_state.files_for_processing = None
        if 'uploaded_excel_file_temp' not in st.session_state: # Temp storage for Excel file
            st.session_state.uploaded_excel_file_temp = None
        if 'main_rif_csv_temp' not in st.session_state: # Temp storage for main CSV RIF
            st.session_state.main_rif_csv_temp = None
        if 'excel_rif_num_temp' not in st.session_state: # Temp storage for Excel RIF
            st.session_state.excel_rif_num_temp = None

        # Cenário 1: Confirmação está pendente
        if st.session_state.rif_confirmation_needed:
            st.warning("⚠️ Os números de RIF nos nomes dos arquivos são diferentes. Deseja continuar mesmo assim?")
            col1, col2 = st.columns(2)
            if col1.button("Sim, continuar o processamento"):
                st.session_state.rif_confirmation_needed = False
                # O processamento ocorrerá no próximo rerun, usando os arquivos salvos
                st.rerun() 
            if col2.button("Não, reiniciar e limpar dados"):
                realizar_limpeza_seguranca()
                st.rerun()

        # Cenário 2: Confirmação foi dada (ou não era necessária), e agora processamos
        elif st.session_state.files_for_processing:
            with st.spinner('🔍 Processando dados originais... Isso pode levar alguns minutos.'):
                try:
                    files_map = st.session_state.files_for_processing
                    df_ocorrencias, df_envolvidos, df_comunicacoes = load_all_files(
                        files_map['ocorrencias'], files_map['envolvidos'], files_map['comunicacoes']
                    )
                    if df_ocorrencias is None: st.stop()
                    df_comunicacoes = prepare_value_columns(df_comunicacoes)
                    for df in [df_ocorrencias, df_envolvidos, df_comunicacoes]:
                        df['Indexador'] = df['Indexador'].astype(str).str.strip()
                    df_final = process_raw_data(df_ocorrencias, df_envolvidos, df_comunicacoes)
                    if df_final is None: st.stop()
                    
                    st.session_state.df_final = df_final
                    st.session_state.df_ocorrencias = df_ocorrencias
                    st.session_state.df_envolvidos = df_envolvidos
                    st.session_state.df_comunicacoes = df_comunicacoes
                    st.session_state.data_loaded = True
                    st.session_state.files_for_processing = None # Limpa o estado
                    st.success("Processamento de dados originais concluído com sucesso!")

                    # Now, process the Excel file if it was uploaded and RIFs match
                    uploaded_excel_file_temp = st.session_state.get("uploaded_excel_file_temp")
                    main_rif_csv_temp = st.session_state.get("main_rif_csv_temp")
                    excel_rif_num_temp = st.session_state.get("excel_rif_num_temp")

                    if uploaded_excel_file_temp:
                        if not excel_rif_num_temp:
                            st.sidebar.error("Não foi possível extrair o número do RIF do nome da planilha Excel. Formato esperado: 'Detalhamento_RIF_XXXX.xlsx'")
                            st.session_state["excel_datasets"] = {}
                            st.session_state["excel_tabela_documentos"] = pd.DataFrame(columns=["cpf_cnpj", "nome_razao_social"])
                            st.session_state["excel_file_uploaded"] = False
                        elif main_rif_csv_temp and excel_rif_num_temp != main_rif_csv_temp:
                            st.sidebar.error(f"O número do RIF da planilha Excel ({excel_rif_num_temp}) não corresponde ao RIF dos arquivos CSV ({main_rif_csv_temp}). A planilha não será carregada.")
                            st.session_state["excel_datasets"] = {}
                            st.session_state["excel_tabela_documentos"] = pd.DataFrame(columns=["cpf_cnpj", "nome_razao_social"])
                            st.session_state["excel_file_uploaded"] = False
                        else:
                            excel_datasets, excel_tabela_documentos = load_detalhamento_excel(uploaded_excel_file_temp)
                            if excel_datasets is not None and excel_tabela_documentos is not None:
                                st.session_state["excel_datasets"] = excel_datasets
                                st.session_state["excel_tabela_documentos"] = excel_tabela_documentos
                                st.session_state["excel_file_uploaded"] = True
                            else:
                                st.session_state["excel_datasets"] = {}
                                st.session_state["excel_tabela_documentos"] = pd.DataFrame(columns=["cpf_cnpj", "nome_razao_social"])
                                st.session_state["excel_file_uploaded"] = False
                    else:
                        st.session_state["excel_datasets"] = {}
                        st.session_state["excel_tabela_documentos"] = pd.DataFrame(columns=["cpf_cnpj", "nome_razao_social"])
                        st.session_state["excel_file_uploaded"] = False

                    st.rerun()
                except Exception as e:
                    st.error(f"Erro fatal durante processamento: {str(e)}")
                    st.session_state.data_loaded = False
                    st.session_state.files_for_processing = None

        # Cenário 3: Botão de processar foi clicado pela primeira vez
        else:
            if uploaded_files and len(uploaded_files) == 3:
                files_map = {'ocorrencias': None, 'envolvidos': None, 'comunicacoes': None}
                rif_numbers_csv = {}
                for file in uploaded_files:
                    filename = file.name.lower()
                    match = re.search(r'\d+', file.name)
                    rif_num = match.group(0) if match else None
                    if 'ocorrencia' in filename:
                        files_map['ocorrencias'] = file
                        if rif_num: rif_numbers_csv['ocorrencias'] = rif_num
                    elif 'envolvido' in filename:
                        files_map['envolvidos'] = file
                        if rif_num: rif_numbers_csv['envolvidos'] = rif_num
                    elif 'comunicacoe' in filename or 'comunicacao' in filename:
                        files_map['comunicacoes'] = file
                        if rif_num: rif_numbers_csv['comunicacoes'] = rif_num
                
                if not all(files_map.values()):
                    missing = [k for k, v in files_map.items() if v is None]
                    st.sidebar.error(f"Arquivo(s) não encontrado(s): {', '.join(missing)}. Verifique os nomes.")
                else:
                    unique_csv_rifs = set(rif_numbers_csv.values())
                    main_rif_csv = list(unique_csv_rifs)[0] if len(unique_csv_rifs) >= 1 else None

                    excel_rif_num = None
                    if uploaded_excel_file:
                        excel_filename = uploaded_excel_file.name.lower()
                        excel_match = re.search(r'detalhamento_rif_(\d+)', excel_filename)
                        excel_rif_num = excel_match.group(1) if excel_match else None

                    st.session_state.files_for_processing = files_map
                    st.session_state.uploaded_excel_file_temp = uploaded_excel_file
                    st.session_state.main_rif_csv_temp = main_rif_csv
                    st.session_state.excel_rif_num_temp = excel_rif_num
                    
                    # Check for RIF mismatch for confirmation
                    csv_mismatch = len(unique_csv_rifs) > 1
                    excel_mismatch = main_rif_csv and excel_rif_num and excel_rif_num != main_rif_csv
                    
                    if csv_mismatch or excel_mismatch:
                        st.session_state.rif_confirmation_needed = True
                    
                    st.rerun()

            elif uploaded_files:
                st.sidebar.error("Por favor, carregue exatamente 3 arquivos (Ocorrências, Envolvidos, Comunicações).")
            else:
                st.sidebar.error("Faltam arquivos! Carregue os 3 arquivos CSV e clique em 'Processar'.")

    # Lógica para Dados Anonimizados (inalterada)
    elif data_source == "Dados Anonimizados":
        if file_anonimizado:
            with st.spinner('🔍 Processando dados anonimizados...'):
                try:
                    from core.data_loader import load_anonymized_data # Importação tardia
                    df_final, df_ocorrencias, df_envolvidos, df_comunicacoes = load_anonymized_data(file_anonimizado)
                    if df_final is None: st.stop()
                    st.session_state.df_final = df_final
                    st.session_state.df_ocorrencias = df_ocorrencias
                    st.session_state.df_envolvidos = df_envolvidos
                    st.session_state.df_comunicacoes = df_comunicacoes
                    st.session_state.data_loaded = True
                    # Clear Excel data if anonimized data is loaded
                    st.session_state["excel_datasets"] = {}
                    st.session_state["excel_tabela_documentos"] = pd.DataFrame(columns=["cpf_cnpj", "nome_razao_social"])
                    st.session_state["excel_file_uploaded"] = False
                    st.success("Processamento de dados anonimizados concluído com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro fatal durante processamento do arquivo anonimizado: {str(e)}")
                    st.session_state.data_loaded = False
        else:
            st.sidebar.error("Carregue o arquivo CSV anonimizado e clique em 'Processar'.")


# ==============================================
# INTERFACE PRINCIPAL (APÓS CARREGAMENTO)
# ==============================================
if st.session_state.get('data_loaded', False):
    
    # Acessar dados do estado da sessão
    df_final_loaded = st.session_state.df_final.copy()
    df_ocorrencias = st.session_state.df_ocorrencias
    df_envolvidos = st.session_state.df_envolvidos
    df_comunicacoes = st.session_state.df_comunicacoes
    
    # Calcular indicadores
    df_env = rif_ind.calc_indicadores_envolvido(df_final_loaded)
    df_com = rif_ind.calc_indicadores_comunicacao(df_final_loaded)
    df_par = rif_ind.calc_indicadores_pares(df_final_loaded)
    
    df_display = df_final_loaded
    st.caption(f"Trabalhando com {len(df_display)} registros após carregamento.")
    
    # ==========================================
    # FILTROS NA SIDEBAR
    # ==========================================
    st.sidebar.header("🔎 Filtros")
    
    # Filtro de Data
    date_range_selected = None
    if 'Data_da_operacao' in df_display.columns and pd.api.types.is_datetime64_any_dtype(df_display['Data_da_operacao']):
        min_date_val = df_display['Data_da_operacao'].min()
        max_date_val = df_display['Data_da_operacao'].max()
        default_min_date = datetime.now().date().replace(day=1)
        default_max_date = datetime.now().date()
        min_date = min_date_val.date() if pd.notna(min_date_val) else default_min_date
        max_date = max_date_val.date() if pd.notna(max_date_val) else default_max_date
        
        try:
            date_range_selected = st.sidebar.date_input(
                "Período da Operação",
                value=[min_date, max_date],
                min_value=min_date if pd.notna(min_date_val) else None,
                max_value=max_date if pd.notna(max_date_val) else None,
                key='date_filter'
            )
            if len(date_range_selected) == 2:
                start_date, end_date = date_range_selected
                df_display_filtered = df_display[
                    df_display['Data_da_operacao'].notna() &
                    (df_display['Data_da_operacao'].dt.date >= start_date) &
                    (df_display['Data_da_operacao'].dt.date <= end_date)
                ]
                if not df_display_filtered.equals(df_display):
                    if df_display_filtered.empty and not df_display.empty:
                        st.sidebar.warning("Nenhum dado encontrado para o período selecionado.")
                    df_display = df_display_filtered
            else:
                st.sidebar.warning("Selecione data inicial e final.")
                date_range_selected = None
        except Exception as e:
            st.sidebar.error(f"Erro no filtro de data: {e}")
            date_range_selected = None
    
    # Filtros de Ano e Mês
    selected_year = "Todos"
    selected_month = "Todos"
    if 'Ano' in df_display.columns and 'Mes' in df_display.columns:
        available_years = ["Todos"] + sorted(df_display['Ano'].unique().tolist(), reverse=True)
        if 0 in available_years: available_years.remove(0)
        
        selected_year = st.sidebar.selectbox(
            "Filtrar por Ano:",
            options=available_years,
            key='year_filter'
        )
        
        if selected_year != "Todos":
            df_display = df_display[df_display['Ano'] == selected_year]
        
        available_months = ["Todos"] + sorted(df_display['Mes'].unique().tolist())
        if 0 in available_months: available_months.remove(0)
        
        month_map = {1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
                     7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"}
        month_options_display = ["Todos"] + [month_map.get(m, m) for m in available_months if m != "Todos"]
        month_display_map = {v: k for k, v in month_map.items()}
        
        selected_month_display = st.sidebar.selectbox(
            "Filtrar por Mês:",
            options=month_options_display,
            key='month_filter'
        )
        
        if selected_month_display != "Todos":
            selected_month_num = month_display_map.get(selected_month_display)
            if selected_month_num:
                df_display = df_display[df_display['Mes'] == selected_month_num]
    
    # Filtro de Granularidade Temporal
    granularity = 'Mensal'
    if 'Data_da_operacao' in df_display.columns and pd.api.types.is_datetime64_any_dtype(df_display['Data_da_operacao']):
        granularity = st.sidebar.selectbox(
            "Granularidade Temporal (Análise Geral)",
            options=['Diária', 'Semanal', 'Mensal', 'Trimestral'],
            index=2,
            key='granularity_filter'
        )
    
    # Filtro de Tipo de Ocorrência
    selected_ocorrencia = 'Todas'
    if 'Ocorrencia' in df_display.columns:
        ocorrencias_options = ['Todas'] + sorted(df_display['Ocorrencia'].astype(str).fillna('N/A').unique().tolist())
        selected_ocorrencia = st.sidebar.selectbox(
            "Tipo de Ocorrência",
            options=ocorrencias_options,
            key='ocorrencia_filter'
        )
        if selected_ocorrencia != 'Todas':
            original_len = len(df_display)
            if selected_ocorrencia == 'N/A':
                df_display = df_display[df_display['Ocorrencia'].isna()]
            else:
                df_display = df_display[df_display['Ocorrencia'] == selected_ocorrencia]
            if df_display.empty and original_len > 0:
                st.sidebar.warning("Nenhum dado encontrado para a ocorrência selecionada.")
    
    st.sidebar.caption(f"Registros após filtros: {len(df_display)}")
    
    # Preparar DataFrame de descrição de segmentos
    df_segmento_desc = pd.DataFrame(
        list(SEGMENTO_MAP.items()),
        columns=['CodigoSegmento', 'DescricaoCampos']
    )
    df_segmento_desc['CodigoSegmento'] = df_segmento_desc['CodigoSegmento'].astype(str)
    
    # Normalizar tipoEnvolvido
    if 'tipoEnvolvido' in df_display.columns:
        df_display['tipoEnvolvido_Norm'] = df_display['tipoEnvolvido'].apply(normalize_string)
    else:
        df_display['tipoEnvolvido_Norm'] = "DESCONHECIDO"
    
    # ==========================================
    # ABAS PRINCIPAIS
    # ==========================================
    tab_geral, tab_ranking, tab_ranking_com, tab_portal, tab_trilhas_die = st.tabs([
        "📊 Análise Geral",
        "🏆 Ranking de Envolvidos",
        "💬 Ranking de Comunicações",
        "🔍 Portal da Transparência",
        "🗺️ Trilhas da DIE"
    ])
    
    # -----------------------------------------
    # ABA 1: ANÁLISE GERAL (COMPLETA)
    # -----------------------------------------
    with tab_geral:
        st.header("📊 Análise Geral")
        st.caption("Agregações baseadas principalmente no ValorTotal (CampoA). O significado exato varia por segmento.")
        
        if not df_display.empty:
            # ===== MÉTRICAS RÁPIDAS =====
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Comunicações (Filtradas)", df_display['idComunicacao'].nunique())
            col2.metric("Envolvidos Únicos (Filtrados)", df_display['cpfCnpjEnvolvido'].nunique())
            col3.metric("Tipos Ocorrências (Filtradas)", df_display['idOcorrencia'].nunique())
            
            # Recalcular soma real para a métrica total
            valid_indexadores = df_display['Indexador_x'].unique()
            valor_total_filtrado = df_comunicacoes[
                df_comunicacoes['Indexador'].isin(valid_indexadores)
            ]['ValorCampoA'].sum()
            col4.metric("Valor Total (R$) (Soma CampoA)", f"R$ {valor_total_filtrado:,.2f}")
            
            st.divider()
            
            # ===== TABELA: TRANSAÇÕES POR TIPO DE OCORRÊNCIA =====
            st.subheader("📋 Transações Comunicadas por Tipo de Ocorrência")
            st.info("⚠️ Os valores totais representam a soma dos valores no CampoA do RIF.")
            
            df_unique_comm_ocor = df_display.groupby(['Indexador_x', 'idOcorrencia', 'Ocorrencia']).agg({
                'ValorTotal': 'max'
            }).reset_index()
            
            transactions_final_agg = df_unique_comm_ocor.groupby(['idOcorrencia', 'Ocorrencia']).agg(
                Quantidade=('Indexador_x', 'count'),
                ValorTotalReal=('ValorTotal', 'sum')
            ).reset_index()
            
            transactions_final_agg = transactions_final_agg.sort_values('Quantidade', ascending=False)
            transactions_final_agg['ValorTotal_fmt'] = transactions_final_agg['ValorTotalReal'].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            
            st.dataframe(
                transactions_final_agg[['idOcorrencia', 'Ocorrencia', 'Quantidade', 'ValorTotal_fmt']],
                width='stretch',
                column_config={
                    "idOcorrencia": "ID Ocorrência", 
                    "Ocorrencia": st.column_config.TextColumn("Ocorrência", width="large"),
                    "Quantidade": "Qtd. Comunicações", 
                    "ValorTotal_fmt": "Valor Total (R$)"
                },
                hide_index=True
            )
            
            # ===== TABELA: COMUNICAÇÕES POR SEGMENTO =====
            st.subheader("📋 Comunicações por Segmento")
            st.info("⚠️ Para cada segmento, os campos de valores (CampoA,...,CampoE) do RIF possuem significados diferentes.")
            
            df_unique_seg = df_display.groupby(['Indexador_x', 'CodigoSegmento']).agg({
                'ValorTotal': 'max'
            }).reset_index()
            
            segment_communications = df_unique_seg.groupby('CodigoSegmento').agg(
                Quantidade=('Indexador_x', 'count'),
                ValorTotalReal=('ValorTotal', 'sum')
            ).reset_index()
            
            segment_communications = pd.merge(segment_communications, df_segmento_desc, on='CodigoSegmento', how='left')
            segment_communications['DescricaoCampos'] = segment_communications['DescricaoCampos'].fillna('Segmento não mapeado')
            segment_communications = segment_communications.sort_values('Quantidade', ascending=False)
            segment_communications['ValorTotal_fmt'] = segment_communications['ValorTotalReal'].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            
            st.dataframe(
                segment_communications[['CodigoSegmento', 'Quantidade', 'ValorTotal_fmt', 'DescricaoCampos']], 
                width='stretch', 
                column_config={
                    "CodigoSegmento": st.column_config.TextColumn("Código", width="small"),
                    "Quantidade": st.column_config.NumberColumn("Qtd. Com.", help="Número de comunicações únicas"),
                    "ValorTotal_fmt": st.column_config.TextColumn("Valor Total (Campo A)", help="Soma do valor principal (Campo A)"),
                    "DescricaoCampos": st.column_config.TextColumn("Significado dos Campos", width="large")
                },
                hide_index=True
            )
            
            # ===== GRÁFICO: EVOLUÇÃO TEMPORAL =====
            st.subheader("📊 Evolução temporal das Comunicações")
            
            if 'Data_da_operacao' in df_display.columns and pd.api.types.is_datetime64_any_dtype(df_display['Data_da_operacao']):
                df_temp = df_display.copy()
                df_temp = df_temp.dropna(subset=['Data_da_operacao'])
                
                if not df_temp.empty:
                    if granularity == 'Diária':
                        df_temp['Período'] = df_temp['Data_da_operacao'].dt.date
                    elif granularity == 'Semanal':
                        df_temp['Período'] = df_temp['Data_da_operacao'].dt.to_period('W').apply(lambda p: p.strftime('%Y-%U'))
                    elif granularity == 'Mensal':
                        df_temp['Período'] = df_temp['Data_da_operacao'].dt.to_period('M').astype(str)
                    elif granularity == 'Trimestral':
                        df_temp['Período'] = df_temp['Data_da_operacao'].dt.to_period('Q').astype(str)
                    
                    temporal = df_temp.groupby('Período').agg(
                        Comunicações=('Indexador_x', 'nunique')
                    ).reset_index()
                    
                    temporal = temporal.sort_values('Período')
                    
                    fig = px.line(
                        temporal, 
                        x='Período', 
                        y='Comunicações', 
                        title=f'Evolução {granularity} das Comunicações (Frequência Real)',
                        text='Comunicações',
                        markers=True
                    )
                    fig.update_traces(textposition='top center')
                    st.plotly_chart(fig, width='stretch', key='chart_temporal_evolution')
                else:
                    st.info("Nenhum dado com data válida para gerar a evolução temporal.")
            
            # ===== TABELA: TOP 50 ENVOLVIDOS =====
            st.subheader("🏆 Top 50 Envolvidos (por Quantidade de Comunicações)")
            
            df_unique_env = df_display.groupby(['Indexador_x', 'cpfCnpjEnvolvido', 'nomeEnvolvido']).agg({
                'ValorTotal': 'max'
            }).reset_index()
            
            top_envolvidos = df_unique_env.groupby(['cpfCnpjEnvolvido', 'nomeEnvolvido']).agg(
                Quantidade=('Indexador_x', 'count'),
                Valor_Total_A=('ValorTotal', 'sum')
            ).reset_index()
            
            top_envolvidos.columns = ['CPF/CNPJ', 'Nome', 'Qtd_Comunicacoes', 'Valor_Total_A']
            top_envolvidos = top_envolvidos[top_envolvidos['CPF/CNPJ'] != 'DESCONHECIDO']
            top_envolvidos = top_envolvidos.sort_values('Qtd_Comunicacoes', ascending=False).head(50)
            top_envolvidos['Valor_Total_A_fmt'] = top_envolvidos['Valor_Total_A'].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            
            st.dataframe(top_envolvidos[['CPF/CNPJ', 'Nome', 'Qtd_Comunicacoes', 'Valor_Total_A_fmt']], 
                        width='stretch', hide_index=True)
            
            # ===== TABELA: TOP 50 TITULARES/SÓCIOS/ETC =====
            st.subheader("🏆 Top 50 Titulares, Sócios, Procuradores e Repres. (por Qtd. Comunicações)")
            
            papeis_centrais_norm = ['TITULAR', 'TITULAR DA CONTA', 'SOCIO', 'PROCURADOR', 
                                   'REPRESENTANTE', 'RESPONSAVEL', 'ADMINISTRADOR', 'PROCURADOR / REPRESENTANTE LEGAL']
            df_centrais = df_display[df_display['tipoEnvolvido_Norm'].isin(papeis_centrais_norm)]
            
            if not df_centrais.empty:
                df_centrais_unique = df_centrais.groupby(['Indexador_x', 'cpfCnpjEnvolvido', 'nomeEnvolvido']).agg({
                    'ValorTotal': 'max'
                }).reset_index()
                
                top_centrais = df_centrais_unique.groupby(['cpfCnpjEnvolvido', 'nomeEnvolvido']).agg(
                    Quantidade=('Indexador_x', 'count'),
                    Valor_Total_A=('ValorTotal', 'sum')
                ).reset_index()
                
                top_centrais.columns = ['CPF/CNPJ', 'Nome', 'Qtd_Comunicacoes', 'Valor_Total_A']
                top_centrais = top_centrais[top_centrais['CPF/CNPJ'] != 'DESCONHECIDO']
                top_centrais = top_centrais.sort_values('Qtd_Comunicacoes', ascending=False).head(50)
                top_centrais['Valor_Total_A_fmt'] = top_centrais['Valor_Total_A'].apply(
                    lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                )
                
                st.dataframe(top_centrais[['CPF/CNPJ', 'Nome', 'Qtd_Comunicacoes', 'Valor_Total_A_fmt']], 
                            width='stretch', hide_index=True)
            else:
                st.info("Nenhum envolvido com papel central encontrado.")
            
            # ===== TABELA: TOP 50 REMETENTES =====
            st.subheader("📤 Top 50 Remetentes (por Valor Total Campo A)")
            st.caption("Baseado em envolvidos com papel 'remetente' e somando ValorTotal (CampoA).")
            
            df_remetentes = df_display[df_display['tipoEnvolvido_Norm'] == 'REMETENTE']
            
            if not df_remetentes.empty:
                df_rem_unique = df_remetentes.groupby(['Indexador_x', 'cpfCnpjEnvolvido', 'nomeEnvolvido']).agg({
                    'ValorTotal': 'max'
                }).reset_index()
                
                top_remetentes = df_rem_unique.groupby(['cpfCnpjEnvolvido', 'nomeEnvolvido']).agg(
                    Valor_Total_A=('ValorTotal', 'sum'),
                    Qtd_Comunicacoes=('Indexador_x', 'count')
                ).reset_index()
                
                top_remetentes.columns = ['CPF/CNPJ', 'Nome', 'Valor_Total_A', 'Qtd_Comunicacoes']
                top_remetentes = top_remetentes[top_remetentes['CPF/CNPJ'] != 'DESCONHECIDO']
                top_remetentes = top_remetentes.sort_values('Valor_Total_A', ascending=False).head(50)
                top_remetentes['Valor_Total_A_fmt'] = top_remetentes['Valor_Total_A'].apply(
                    lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                )
                
                st.dataframe(top_remetentes[['CPF/CNPJ', 'Nome', 'Valor_Total_A_fmt', 'Qtd_Comunicacoes']], 
                            width='stretch', hide_index=True)
            else:
                st.info("Nenhum remetente encontrado nos dados filtrados.")
            
            # ===== TABELA: TOP 50 BENEFICIÁRIOS =====
            st.subheader("📥 Top 50 Beneficiários (por Valor Total Campo A)")
            st.caption("Baseado em envolvidos com papel 'beneficiário' e somando ValorTotal (CampoA).")
            
            df_benef = df_display[df_display['tipoEnvolvido_Norm'] == 'BENEFICIARIO']
            
            if not df_benef.empty:
                df_ben_unique = df_benef.groupby(['Indexador_x', 'cpfCnpjEnvolvido', 'nomeEnvolvido']).agg({
                    'ValorTotal': 'max'
                }).reset_index()
                
                top_benef = df_ben_unique.groupby(['cpfCnpjEnvolvido', 'nomeEnvolvido']).agg(
                    Valor_Total_A=('ValorTotal', 'sum'),
                    Qtd_Comunicacoes=('Indexador_x', 'count')
                ).reset_index()
                
                top_benef.columns = ['CPF/CNPJ', 'Nome', 'Valor_Total_A', 'Qtd_Comunicacoes']
                top_benef = top_benef[top_benef['CPF/CNPJ'] != 'DESCONHECIDO']
                top_benef = top_benef.sort_values('Valor_Total_A', ascending=False).head(50)
                top_benef['Valor_Total_A_fmt'] = top_benef['Valor_Total_A'].apply(
                    lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                )
                
                st.dataframe(top_benef[['CPF/CNPJ', 'Nome', 'Valor_Total_A_fmt', 'Qtd_Comunicacoes']], 
                            width='stretch', hide_index=True)
            else:
                st.info("Nenhum beneficiário encontrado nos dados filtrados.")
            
            # ===== TABELA: COMUNICAÇÕES POR CIDADE =====
            st.subheader("🏙️ Comunicações por Cidade da Agência (Filtrado)")
            
            if 'CidadeAgencia' in df_display.columns:
                df_city_temp = df_display.dropna(subset=['CidadeAgencia', 'UFAgencia']).copy()
                
                if not df_city_temp.empty:
                    df_city_temp['Cidade_Norm'] = df_city_temp['CidadeAgencia'].apply(normalize_string)
                    df_city_temp['UF_Norm'] = df_city_temp['UFAgencia'].apply(normalize_string)
                    
                    df_unique_city = df_city_temp.groupby(['Indexador_x', 'Cidade_Norm', 'UF_Norm']).agg({
                        'ValorTotal': 'max'
                    }).reset_index()
                    
                    city_communications = df_unique_city.groupby(['Cidade_Norm', 'UF_Norm']).agg(
                        Quantidade=('Indexador_x', 'count'),
                        ValorTotalReal=('ValorTotal', 'sum')
                    ).reset_index()
                    
                    city_communications = city_communications.sort_values('ValorTotalReal', ascending=False)
                    city_communications['Valor Total (R$)'] = city_communications['ValorTotalReal'].apply(
                        lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    )
                    
                    st.dataframe(
                        city_communications[['Cidade_Norm', 'UF_Norm', 'Valor Total (R$)', 'Quantidade']].head(20),
                        width='stretch',
                        column_config={
                            "Cidade_Norm": "Cidade",
                            "UF_Norm": "UF",
                            "Quantidade": "Qtd. Com."
                        },
                        hide_index=True
                    )
                else:
                    st.info("Nenhuma comunicação com info de cidade nos dados filtrados.")
            else:
                st.info("Coluna 'CidadeAgencia' ausente ou sem dados no arquivo original.")
            
            st.divider()
            
            # ===== DETALHAMENTO DE MOVIMENTAÇÕES EM ESPÉCIE (REVISED) =====
            st.subheader("💵 Detalhamento de Movimentações em Espécie")
            st.caption("Identificação baseada em ocorrências que indicam uso de espécie (depósitos, saques, etc.).")
            
            especie_ocorrencia_ids = sorted(list(set(['1008', '1009', '1011', '1012', '1013', '1020', '1021', '1161', '1162', '1163', '971'])))
            
            df_esp_base = df_display[df_display['idOcorrencia'].isin(especie_ocorrencia_ids)].copy()
            
            if not df_esp_base.empty:
                df_esp_final = df_esp_base.groupby(
                    ['cpfCnpjEnvolvido', 'nomeEnvolvido', 'Indexador_x', 'Ocorrencia', 'DescricaoCampos']
                ).agg({'ValorTotal': 'max'}).reset_index()
                
                df_esp_final = df_esp_final.sort_values('ValorTotal', ascending=False)
                df_esp_final['Valor_Especie_fmt'] = df_esp_final['ValorTotal'].apply(
                    lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                )
                
                st.dataframe(
                    df_esp_final[['cpfCnpjEnvolvido', 'nomeEnvolvido', 'Indexador_x', 'Valor_Especie_fmt', 'Ocorrencia', 'DescricaoCampos']],
                    width='stretch',
                    hide_index=True,
                    column_config={
                        "cpfCnpjEnvolvido": "CPF/CNPJ",
                        "nomeEnvolvido": "Nome Envolvido",
                        "Indexador_x": "Indexador",
                        "Valor_Especie_fmt": "Valor da Operação (R$)",
                        "Ocorrencia": st.column_config.TextColumn("Ocorrência", width="large"),
                        "DescricaoCampos": st.column_config.TextColumn("Descrição do Segmento", width="medium")
                    }
                )
            else:
                st.info("Nenhuma comunicação com ocorrência de movimentação em espécie encontrada nos dados filtrados.")

            # ===== TOP 10 ENVOLVIDOS EM DEPÓSITOS EM ESPÉCIE (REVISED) =====
            st.subheader("💰 Top 10 Envolvidos em Depósitos em Espécie")
            st.caption("Baseado no somatório de valores de comunicações com ocorrências de depósito em espécie.")

            if 'idOcorrencia' in df_display.columns:
                deposito_especie_ids = ['1008', '1011', '1013', '1020', '1021', '1161']
                df_dep_comms = df_display[df_display['idOcorrencia'].isin(deposito_especie_ids)].copy()

                if not df_dep_comms.empty:
                    comm_values = df_dep_comms[['Indexador_x', 'ValorTotal']].drop_duplicates()
                    target_indexadores = comm_values['Indexador_x'].unique()
                    envolvidos_in_comms = df_display[df_display['Indexador_x'].isin(target_indexadores)][['Indexador_x', 'cpfCnpjEnvolvido', 'nomeEnvolvido']].drop_duplicates()
                    merged_data = pd.merge(envolvidos_in_comms, comm_values, on='Indexador_x')
                    
                    depositantes_agg = merged_data.groupby(['cpfCnpjEnvolvido', 'nomeEnvolvido']).agg(
                        ValorTotal=('ValorTotal', 'sum'),
                        Qtd_Comunicacoes=('Indexador_x', 'nunique')
                    ).reset_index()
                    
                    depositantes_agg.columns = ['CPF/CNPJ', 'Nome', 'Valor Total', 'Qtd. Comunicações']
                    depositantes_agg = depositantes_agg[depositantes_agg['CPF/CNPJ'] != 'DESCONHECIDO'].sort_values('Valor Total', ascending=False).head(10)
                    depositantes_agg['Valor Total (R$)'] = depositantes_agg['Valor Total'].apply(
                        lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    )
                    st.dataframe(depositantes_agg[['CPF/CNPJ', 'Nome', 'Valor Total (R$)', 'Qtd. Comunicações']], width='stretch', hide_index=True)
                else:
                    st.info("Nenhuma ocorrência de depósito em espécie encontrada nos dados filtrados.")
            else:
                st.info("Coluna 'idOcorrencia' ausente para esta análise.")

            # ===== TOP 10 ENVOLVIDOS EM SAQUES EM ESPÉCIE (REVISED) =====
            st.subheader("💸 Top 10 Envolvidos em Saques em Espécie")
            st.caption("Baseado no somatório de valores de comunicações com ocorrências de saque em espécie.")

            if 'idOcorrencia' in df_display.columns:
                saque_especie_ids = ['1008', '1012', '1162', '1163']
                df_saque_comms = df_display[df_display['idOcorrencia'].isin(saque_especie_ids)].copy()

                if not df_saque_comms.empty:
                    comm_values = df_saque_comms[['Indexador_x', 'ValorTotal']].drop_duplicates()
                    target_indexadores = comm_values['Indexador_x'].unique()
                    envolvidos_in_comms = df_display[df_display['Indexador_x'].isin(target_indexadores)][['Indexador_x', 'cpfCnpjEnvolvido', 'nomeEnvolvido']].drop_duplicates()
                    merged_data = pd.merge(envolvidos_in_comms, comm_values, on='Indexador_x')

                    sacadores_agg = merged_data.groupby(['cpfCnpjEnvolvido', 'nomeEnvolvido']).agg(
                        ValorTotal=('ValorTotal', 'sum'),
                        Qtd_Comunicacoes=('Indexador_x', 'nunique')
                    ).reset_index()
                    
                    sacadores_agg.columns = ['CPF/CNPJ', 'Nome', 'Valor Total', 'Qtd. Comunicações']
                    sacadores_agg = sacadores_agg[sacadores_agg['CPF/CNPJ'] != 'DESCONHECIDO'].sort_values('Valor Total', ascending=False).head(10)
                    sacadores_agg['Valor Total (R$)'] = sacadores_agg['Valor Total'].apply(
                        lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    )
                    st.dataframe(sacadores_agg[['CPF/CNPJ', 'Nome', 'Valor Total (R$)', 'Qtd. Comunicações']], width='stretch', hide_index=True)
                else:
                    st.info("Nenhuma ocorrência de saque em espécie encontrada nos dados filtrados.")
            else:
                st.info("Coluna 'idOcorrencia' ausente para esta análise.")
            
            # ===== ANÁLISE DE BENFORD =====
            st.subheader("Lei de Benford – Valores das Transações (CampoA)")
            
            real_count = df_display['Indexador_x'].nunique()
            
            if real_count < 500:
                st.info(f"""
                ⚠️ **Atenção:** A Lei de Benford é estatisticamente robusta apenas para grandes amostras.  
                A literatura técnica recomenda, no mínimo, 500 a 1.000 registros para que as conclusões sejam confiáveis.  
                Como o filtro atual contém **{real_count} comunicações**, use este gráfico apenas como tendência visual.
                """)
            else:
                st.info(f"""
                ⚠️ **Atenção:** A Lei de Benford é estatisticamente robusta apenas para grandes amostras.  
                O filtro atual contém **{real_count} comunicações**.
                """)
            
            df_benford_input = df_display.drop_duplicates(subset=['Indexador_x'])
            fig_benford = plot_benford_analysis(df_benford_input)
            
            if fig_benford is not None:
                st.plotly_chart(fig_benford, width='stretch', key='chart_benford')
            else:
                st.caption("Não há valores positivos suficientes em 'ValorTotal' para aplicar Benford.")
            
            st.divider()
            
            # ===== TABELA DE PEPs =====
            if 'bitPepCitado' in df_display.columns:
                st.subheader("👤 PEPs Identificados e Comunicações Associadas")

                df_pep_base = df_display[df_display['bitPepCitado'] == True].copy()
                
                if not df_pep_base.empty:
                    pep_final = df_pep_base.groupby([
                        'Indexador_x', 'idComunicacao', 'Data_da_operacao', 
                        'cpfCnpjEnvolvido', 'nomeEnvolvido', 'tipoEnvolvido', 
                        'DescricaoCampos'
                    ]).agg({
                        'ValorTotal': 'max',
                        'Ocorrencia': lambda x: " | ".join(sorted(set(x.astype(str))))
                    }).reset_index()
                    
                    pep_final = pep_final.sort_values(by=['nomeEnvolvido', 'Data_da_operacao'], ascending=[True, False])
                    pep_final['Valor_Total_fmt'] = pep_final['ValorTotal'].apply(
                        lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    )
                    
                    st.dataframe(
                        pep_final[[
                            'Indexador_x', 'idComunicacao', 'Data_da_operacao', 'cpfCnpjEnvolvido', 
                            'nomeEnvolvido', 'tipoEnvolvido', 'Valor_Total_fmt', 'Ocorrencia', 'DescricaoCampos'
                        ]],
                        width='stretch',
                        column_config={
                            "Indexador_x": "Indexador",
                            "idComunicacao": "ID Com.",
                            "Data_da_operacao": st.column_config.DatetimeColumn("Data Operação", format="DD/MM/YYYY"),
                            "cpfCnpjEnvolvido": "CPF/CNPJ PEP",
                            "nomeEnvolvido": "Nome PEP",
                            "tipoEnvolvido": "Papel na Com.",
                            "Valor_Total_fmt": "Valor Principal (CampoA)",
                            "Ocorrencia": st.column_config.TextColumn("Ocorrências Identificadas", width="large"),
                            "DescricaoCampos": st.column_config.TextColumn("Contexto Valor", width="medium")
                        },
                        hide_index=True
                    )
                else:
                    st.info("Nenhum PEP identificado nos dados filtrados.")
            
            # ===== TABELA: PESSOAS OBRIGADAS =====
            if 'bitPessoaObrigadaCitado' in df_display.columns:
                st.subheader("👥 Análise de Pessoas Obrigadas (Filtrado)")
                
                df_obrigada_base = df_display[df_display['bitPessoaObrigadaCitado'] == True].copy()
                
                if not df_obrigada_base.empty:
                    obrigada_final = df_obrigada_base.groupby([
                        'Indexador_x', 'idComunicacao', 'Data_da_operacao', 
                        'cpfCnpjEnvolvido', 'nomeEnvolvido', 'tipoEnvolvido'
                    ]).agg({
                        'ValorTotal': 'max',
                        'Ocorrencia': lambda x: " | ".join(sorted(set(x.astype(str))))
                    }).reset_index()
                    
                    obrigada_final = obrigada_final.sort_values(by=['nomeEnvolvido', 'Data_da_operacao'], ascending=[True, False])
                    obrigada_final['Valor_Total_fmt'] = obrigada_final['ValorTotal'].apply(
                        lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    )
                    
                    st.dataframe(
                        obrigada_final[[
                            'Indexador_x', 'idComunicacao', 'Data_da_operacao', 'cpfCnpjEnvolvido',
                            'nomeEnvolvido', 'tipoEnvolvido', 'Valor_Total_fmt', 'Ocorrencia'
                        ]],
                        width='stretch',
                        column_config={
                            "Indexador_x": "Indexador",
                            "idComunicacao": "ID Comunicação",
                            "Data_da_operacao": st.column_config.DatetimeColumn("Data Operação", format="DD/MM/YYYY"),
                            "cpfCnpjEnvolvido": "CPF/CNPJ",
                            "nomeEnvolvido": "Nome",
                            "tipoEnvolvido": "Papel da Comunicação",
                            "Valor_Total_fmt": "Valor Principal (Campo A)",
                            "Ocorrencia": st.column_config.TextColumn("Ocorrências Identificadas", width="large")
                        },
                        hide_index=True
                    )
                else:
                    st.info("Nenhuma Pessoa Obrigada identificada nos dados filtrados.")
            
            # ===== TABELA: SERVIDORES PÚBLICOS =====
            if 'intServidorCitado' in df_display.columns:
                st.subheader("🧑‍💼 Análise de Servidores Públicos (Filtrado)")
                
                df_servidor_base = df_display[df_display['intServidorCitado'] == True].copy()
                
                if not df_servidor_base.empty:
                    servidor_final = df_servidor_base.groupby([
                        'Indexador_x', 'idComunicacao', 'Data_da_operacao', 
                        'cpfCnpjEnvolvido', 'nomeEnvolvido', 'tipoEnvolvido'
                    ]).agg({
                        'ValorTotal': 'max',
                        'Ocorrencia': lambda x: " | ".join(sorted(set(x.astype(str))))
                    }).reset_index()
                    
                    servidor_final = servidor_final.sort_values(by=['nomeEnvolvido', 'Data_da_operacao'], ascending=[True, False])
                    servidor_final['Valor_Total_fmt'] = servidor_final['ValorTotal'].apply(
                        lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    )
                    
                    st.dataframe(
                        servidor_final[[
                            'Indexador_x', 'idComunicacao', 'Data_da_operacao', 'cpfCnpjEnvolvido',
                            'nomeEnvolvido', 'tipoEnvolvido', 'Valor_Total_fmt', 'Ocorrencia'
                        ]],
                        width='stretch',
                        column_config={
                            "Indexador_x": "Indexador",
                            "idComunicacao": "ID Comunicação",
                            "Data_da_operacao": st.column_config.DatetimeColumn("Data Operação", format="DD/MM/YYYY"),
                            "cpfCnpjEnvolvido": "CPF/CNPJ",
                            "nomeEnvolvido": "Nome",
                            "tipoEnvolvido": "Papel da Comunicação",
                            "Valor_Total_fmt": "Valor Principal (Campo A)",
                            "Ocorrencia": st.column_config.TextColumn("Ocorrências Identificadas", width="large")
                        },
                        hide_index=True
                    )
                else:
                    st.info("Nenhum Servidor Público identificado nos dados filtrados.")
                
        else:
            st.info("Nenhum dado corresponde aos filtros selecionados para a Análise Geral.")
    
    # -----------------------------------------
    # ABA 2: RANKING DE ENVOLVIDOS (COMPLETO)
    # -----------------------------------------
    with tab_ranking:
        st.header("🏆 Ranking de Risco e Análise de Envolvidos")
        st.caption("O Score Total soma pontos de indicadores matemáticos e padrões suspeitos detectados.")

        # --- SEÇÃO DE AJUDA SOLICITADA ---
        with st.expander("❓ Como é calculado o score de risco"):
            st.markdown("""
            O **Score Total** é uma pontuação integrada que combina a análise comportamental (padrões qualitativos) com métricas estatísticas (indicadores quantitativos).
            
            ### 1. Padrões Comportamentais (Qualitativos)
            Estes alertas são extraídos diretamente das narrativas e ocorrências reportadas, classificados por gravidade:
            * **Crítico (10 pts):** Fracionamento de valores, PEP com múltiplas comunicações, Alto valor em espécie ou Keywords de alto risco (ex: 'Laranja', 'Doleiro').
            * **Alto (5 pts):** Burla de limites (Structuring), Transações de altíssimo valor (> R$ 1Mi), Saques/Depósitos vultosos em espécie ou Alta Frequência.
            * **Moderado (2 pts):** Contas recém-abertas (< 30 dias), Movimentação em múltiplas cidades no mesmo dia ou Resistência a informações.
            
            ### 2. Indicadores Matemáticos (Quantitativos)
            Métricas calculadas sobre o histórico consolidado do envolvido:
            * **HHI (Concentração):** O Índice de Herfindahl-Hirschman mede se o dinheiro está concentrado em poucas contrapartes (Risco de contas-âncora).
            * **Fracionamento Temporal:** Identifica dias com 3 ou mais operações, sugerindo tentativa de divisão de valores para evitar reporte.
            * **Proximidade de Limites:** Monitora operações que ficam propositalmente entre 90% e 99% do limite de R$ 50 mil.
            
            ### 3. Regra de Cálculo do Score
            A pontuação final é a soma de:
            1.  **Pontos Qualitativos:** Soma de todos os alertas detectados pela análise de padrões.
            2.  **Bônus de Perfil:** +5 pontos se for PEP, +5 se Servidor Público e +5 se Pessoa Obrigada.
            3.  **Bônus de Concentração:** +10 pontos se o índice HHI for superior a 0.6.
            4.  **Bônus de Fracionamento:** +2 pontos para cada dia identificado com alta frequência de operações simultâneas.
            """)
        # --- FIM DA SEÇÃO DE AJUDA ---
        
        # --- State Management ---
        if 'selected_cpf_ranking' not in st.session_state:
            st.session_state.selected_cpf_ranking = None
        if 'last_table_selection' not in st.session_state:
            st.session_state.last_table_selection = []
            
        # --- Data Processing ---
        if not df_display.empty:
            with st.spinner("Consolidando Score de Risco..."):
                df_env_math = rif_ind.calc_indicadores_envolvido(df_display)
                df_alertas = analyze_suspicious_patterns(
                    df_display, df_ocorrencias, df_comunicacoes, df_envolvidos
                )
                
                if not df_alertas.empty:
                    df_resumo_alertas = df_alertas.groupby('cpfCnpj').agg(
                        Score_Quali=('Pontos', 'sum'),
                        Qtd_Alertas=('Motivo', 'count')
                    ).reset_index()
                    df_ranking = pd.merge(
                        df_env_math, df_resumo_alertas,
                        left_on='cpfCnpjEnvolvido', right_on='cpfCnpj',
                        how='left'
                    ).fillna(0)
                else:
                    df_ranking = df_env_math.assign(Score_Quali=0, Qtd_Alertas=0)
                
                df_ranking['ScoreTotal'] = df_ranking['Score_Quali']
                df_ranking['ScoreTotal'] += df_ranking['flag_pep'].astype(int) * 5
                df_ranking['ScoreTotal'] += df_ranking['flag_servidor'].astype(int) * 5
                df_ranking['ScoreTotal'] += (df_ranking['hhi_contrapartes'] > 0.6).astype(int) * 10
                
                if 'fracionamento_dias_com_3+_ops' in df_ranking.columns:
                    df_ranking['ScoreTotal'] += df_ranking['fracionamento_dias_com_3+_ops'] * 2
                
                df_ranking = df_ranking.sort_values('ScoreTotal', ascending=False).reset_index(drop=True)
                df_ranking.insert(0, "Pos.", range(1, len(df_ranking) + 1))

            # --- UI Widgets and Selection Logic ---


            st.divider()

            st.subheader("Classificação de Risco")

            # Search box for the table
            search_name = st.text_input(
                "Localizar envolvido na tabela pelo nome:",
                placeholder="Digite um nome para filtrar...",
                key="risk_table_search"
            )

            df_ranking_filtered = df_ranking
            if search_name:
                df_ranking_filtered = df_ranking[df_ranking['nomeEnvolvido'].str.contains(search_name, case=False, na=False)]


            top_n_envolvidos = st.slider(
                "Quantidade de envolvidos a exibir na tabela:",
                min_value=10, 
                max_value=len(df_ranking_filtered) if len(df_ranking_filtered) > 10 else 10, 
                value=min(100, len(df_ranking_filtered)), 
                step=10,
                key="ranking_envolvidos_topn",
                disabled=len(df_ranking_filtered) == 0
            )
            st.caption("Clique em uma linha da tabela para ver os detalhes (alterna com a seleção acima).")

            if not df_ranking_filtered.empty:
                max_score = int(df_ranking_filtered['ScoreTotal'].max()) if not df_ranking_filtered.empty and df_ranking_filtered['ScoreTotal'].max() > 0 else 1
                
                df_table_display = df_ranking_filtered.copy()
                df_table_display['valor_total_fmt'] = df_table_display['valor_total'].apply(
                    lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                )
                df_to_show = df_table_display[["Pos.", "cpfCnpjEnvolvido", "nomeEnvolvido", "n_comunicacoes", "ScoreTotal", "valor_total_fmt", "Qtd_Alertas"]].head(top_n_envolvidos)

                st.dataframe(
                    df_to_show,
                    width='stretch', hide_index=True, on_select="rerun", selection_mode="single-row",
                    column_config={
                        "Pos.": st.column_config.NumberColumn("Pos.", width="small"),
                        "cpfCnpjEnvolvido": st.column_config.TextColumn("CPF/CNPJ", width="medium"),
                        "nomeEnvolvido": st.column_config.TextColumn("Nome do Envolvido", width="large"),
                        "n_comunicacoes": st.column_config.NumberColumn("Comunicações", format="%d"),
                        "ScoreTotal": st.column_config.ProgressColumn("Score", format="%d pts", min_value=0, max_value=max_score),
                        "valor_total_fmt": st.column_config.TextColumn("Valor Total"),
                        "Qtd_Alertas": st.column_config.NumberColumn("Alertas", format="%d")
                    },
                    key="ranking_envolvidos_table"
                )
            else:
                st.info("Nenhum envolvido encontrado com o nome pesquisado.")

            selection = st.session_state.get("ranking_envolvidos_table", {}).get("selection", {"rows": []})
            
            if selection.get("rows") and selection["rows"] != st.session_state.last_table_selection:
                st.session_state.last_table_selection = selection["rows"]
                row_idx = selection["rows"][0]
                if row_idx < len(df_to_show):
                    cpf_from_table = df_to_show.iloc[row_idx]["cpfCnpjEnvolvido"]
                    nome_from_table = df_to_show.iloc[row_idx]["nomeEnvolvido"]
                    st.session_state.selected_cpf_ranking = cpf_from_table

            st.divider()

            # --- Render Details ---
            if st.session_state.selected_cpf_ranking:
                st.header(f"👤 Detalhamento do Envolvido")
                render_individual_details(st.session_state.selected_cpf_ranking, df_display, df_final_loaded, df_ocorrencias, df_comunicacoes, df_envolvidos, key_prefix="rank")
            else:
                st.info("Selecione um envolvido na lista ou na tabela acima para ver o detalhamento.")

            # --- Additional Charts ---
            st.divider()
            with st.expander("Ver Gráficos Adicionais de Ranking"):
                st.subheader("📊 Dispersão: Valor vs Score")
                st.caption("Visualização dos Top 30 envolvidos por Score Total.")
                df_scatter = df_ranking.head(30).copy()
                fig_risk = px.scatter(
                    df_scatter, x='valor_total', y='ScoreTotal', size='ScoreTotal', color='ScoreTotal',
                    hover_name='nomeEnvolvido', hover_data=['cpfCnpjEnvolvido', 'n_comunicacoes'],
                    title="Dispersão: Valor Total vs Score de Risco",
                    labels={'valor_total': 'Valor Total (R$)', 'ScoreTotal': 'Score Total', 'n_comunicacoes': 'Nº Comunicações'},
                    color_continuous_scale='RdYlGn_r'
                )
                st.plotly_chart(fig_risk, width='stretch', key='chart_scatter_ranking')

                st.subheader("🏆 Atores-Chave da Rede")
                st.caption("Identifica os envolvidos mais centrais na rede global de relacionamentos (Betweenness Centrality).")
                with st.spinner("Calculando centralidade da rede global..."):
                    df_centrality = analyze_global_network_actors(df_final_loaded)

                if not df_centrality.empty:
                    st.subheader("Ranking de Atores por Centralidade")
                    st.dataframe(
                        df_centrality.head(20),
                        column_config={
                            "cpfCnpjEnvolvido": "CPF/CNPJ",
                            "nomeEnvolvido": st.column_config.TextColumn("Nome", width="large"),
                            "centrality_score": st.column_config.ProgressColumn("Score de Centralidade", format="%.4f", min_value=0, max_value=float(df_centrality['centrality_score'].max()))
                        },
                        width='stretch', hide_index=True
                    )
        else:
            st.info("Nenhum dado disponível para o Ranking com os filtros selecionados.")
    
    # -----------------------------------------
    # ABA 3: ANÁLISE INDIVIDUAL - REMOVIDA
    # -----------------------------------------
    
    with tab_ranking_com:
        st.header("💬 Ranking de Comunicações")
        st.caption(
            "Ranking de comunicações (Indexador) baseado em valor total, quantidade de envolvidos, "
            "uso de espécie e presença de PEP/servidores/pessoas obrigadas."
        )
        
        if not df_display.empty:
            with st.spinner("Calculando indicadores por comunicação..."):
                df_com = rif_ind.calc_indicadores_comunicacao(df_final_loaded)
            
            if df_com is not None and not df_com.empty:
                # ===== PARÂMETROS DO RANKING =====
                st.subheader("Parâmetros do Ranking")
                
                criterio_map_com = {
                    "Valor total (R$)": "valor_total",
                    "Quantidade de envolvidos": "n_envolvidos",
                }
                
                criterio_escolhido_com = st.selectbox(
                    "Ordenar por:",
                    options=list(criterio_map_com.keys()),
                    index=0,
                    key="ranking_com_criterio",
                )
                
                col_ordenacao_com = criterio_map_com[criterio_escolhido_com]
                df_rank_com = df_com.copy()
                
                if col_ordenacao_com not in df_rank_com.columns:
                    st.warning(f"O critério selecionado não está disponível.")
                else:
                    df_rank_com = df_rank_com.sort_values(col_ordenacao_com, ascending=False).reset_index(drop=True)
                    
                    top_n_com = st.slider(
                        "Quantidade de comunicações a exibir",
                        min_value=10, max_value=200, value=50, step=10,
                        key="ranking_com_topn",
                    )
                    
                    df_rank_com_top = df_rank_com.head(top_n_com).copy()
                    df_rank_com_top.insert(0, "Posição", range(1, len(df_rank_com_top) + 1))
                    
                    # ===== MÉTRICAS RESUMO =====
                    col1c, col2c, col3c, col4c = st.columns(4)
                    col1c.metric("Total de Comunicações", int(df_rank_com.shape[0]))
                    
                    if "valor_total" in df_rank_com.columns and not df_rank_com["valor_total"].isna().all():
                        col2c.metric(
                            "Maior valor total (R$)",
                            f"R$ {df_rank_com['valor_total'].max():,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        )
                    else:
                        col2c.metric("Maior valor total", "N/D")
                    
                    if "n_envolvidos" in df_rank_com.columns:
                        col3c.metric("Máx. envolvidos", int(df_rank_com["n_envolvidos"].max()))
                    else:
                        col3c.metric("Máx. envolvidos", 0)
                    
                    if "flag_pep_na_com" in df_rank_com.columns:
                        col4c.metric("Com. com PEP", int(df_rank_com["flag_pep_na_com"].sum()))
                    else:
                        col4c.metric("Com. com PEP", 0)
                    
                    # ===== TABELA DE RANKING =====
                    st.subheader("Tabela de Ranking de Comunicações")
                    
                    # Preparar titulares
                    df_env_base = df_envolvidos.copy()
                    df_env_base["Indexador"] = df_env_base["Indexador"].astype(str)
                    
                    mask_titular = df_env_base["tipoEnvolvido"].str.lower().isin(["titular", "titular da conta"])
                    df_titulares = df_env_base[mask_titular].copy()
                    
                    if not df_titulares.empty:
                        titulares_por_idx = (
                            df_titulares.groupby("Indexador")["nomeEnvolvido"]
                            .agg(lambda x: "; ".join(sorted(set(x))))
                            .reset_index()
                            .rename(columns={"nomeEnvolvido": "Titular"})
                        )
                    else:
                        titulares_por_idx = pd.DataFrame(columns=["Indexador", "Titular"])
                    
                    # Merge com titulares
                    df_rank_com_top = df_rank_com_top.merge(
                        titulares_por_idx,
                        left_on="Indexador_x",
                        right_on="Indexador",
                        how="left",
                    )
                    df_rank_com_top["Titular"] = df_rank_com_top["Titular"].fillna("N/D")
                    
                    # Preparar Comunicantes
                    df_comunicantes = df_final_loaded[['Indexador_x', 'nomeComunicante']].drop_duplicates()
                    df_rank_com_top = df_rank_com_top.merge(
                        df_comunicantes,
                        on="Indexador_x",
                        how="left",
                    )
                    df_rank_com_top["nomeComunicante"] = df_rank_com_top["nomeComunicante"].fillna("N/D")
                    
                    # Formatação
                    if "valor_total" in df_rank_com_top.columns:
                        df_rank_com_top["valor_total_fmt"] = df_rank_com_top["valor_total"].apply(
                            lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        )
                    
                    # Colunas a exibir
                    cols_view_com = ["Posição", "Indexador_x"]
                    if "nomeComunicante" in df_rank_com_top.columns:
                        cols_view_com.append("nomeComunicante")
                    if "Titular" in df_rank_com_top.columns:
                        cols_view_com.append("Titular")
                    if "n_envolvidos" in df_rank_com_top.columns:
                        cols_view_com.append("n_envolvidos")
                    if "valor_total_fmt" in df_rank_com_top.columns:
                        cols_view_com.append("valor_total_fmt")
                    elif "valor_total" in df_rank_com_top.columns:
                        cols_view_com.append("valor_total")
                    
                    for flag_col in ["flag_pep_na_com", "flag_servidor_na_com", "flag_pessoa_obrigada_na_com"]:
                        if flag_col in df_rank_com_top.columns:
                            cols_view_com.append(flag_col)
                    
                    df_show_com = df_rank_com_top[cols_view_com].copy()
                    
                    column_config_com = {
                        "Posição": st.column_config.NumberColumn("Posição", format="%d"),
                        "Indexador_x": st.column_config.TextColumn("Indexador"),
                        "nomeComunicante": st.column_config.TextColumn(
                            "Comunicante",
                            help="Instituição que realizou a comunicação",
                        ),
                        "Titular": st.column_config.TextColumn(
                            "Titular(es)",
                            help="Nome(s) do(s) titular(es) da comunicação",
                        ),
                        "n_envolvidos": st.column_config.NumberColumn(
                            "Qtd. Envolvidos",
                            help="Número de envolvidos distintos na comunicação",
                        ),
                        "valor_total_fmt": st.column_config.TextColumn(
                            "Valor Total",
                            help="Soma do valor principal (CampoA) na comunicação",
                        ),
                        "flag_pep_na_com": st.column_config.CheckboxColumn(
                            "PEP",
                            help="Comunicação envolve ao menos um PEP",
                        ),
                        "flag_servidor_na_com": st.column_config.CheckboxColumn(
                            "Servidor",
                            help="Comunicação envolve ao menos um servidor público",
                        ),
                        "flag_pessoa_obrigada_na_com": st.column_config.CheckboxColumn(
                            "P. Obrigada",
                            help="Comunicação envolve ao menos uma pessoa obrigada",
                        ),
                    }
                    
                    edited = st.dataframe(
                        df_show_com,
                        width='stretch',
                        hide_index=True,
                        column_config={k: v for k, v in column_config_com.items() if k in df_show_com.columns},
                        key="ranking_com_table",
                        height=400,
                        selection_mode="single-row",
                        on_select="rerun",
                    )
                    
                    # ===== DETALHAMENTO AO SELECIONAR =====
                    selection = st.session_state.get("ranking_com_table", {}).get("selection", {})
                    selected_rows = selection.get("rows", [])
                    
                    selected_indexador_from_rank = None
                    if selected_rows:
                        row_idx = selected_rows[0]
                        if 0 <= row_idx < len(df_show_com):
                            selected_indexador_from_rank = df_show_com.iloc[row_idx]["Indexador_x"]
                    
                    if selected_indexador_from_rank:
                        st.markdown("---")
                        render_communication_details(selected_indexador_from_rank, df_final_loaded, df_display, df_envolvidos, key_prefix="rank")
                    else:
                        st.caption("Selecione uma linha na tabela acima para ver o detalhamento completo da comunicação.")
        else:
            st.info("Nenhum dado disponível para calcular o ranking de comunicações.")
    
    # -----------------------------------------
    # ABA 6: PORTAL DA TRANSPARÊNCIA (COMPLETA)
    # -----------------------------------------
    with tab_portal:
        st.header("🔍 Pagamentos - Portal da Transparência")
        st.markdown("""
        Esta ferramenta realiza uma busca pelos pagamentos no período **2021-2026** cruzando os dados do RIF com 
        recebimentos do Governo Federal.
        """)
        
        if st.session_state.get('data_loaded') and st.session_state.df_final is not None:
            # Seletor de Envolvido
            envolvidos_unicos = st.session_state.df_final[['nomeEnvolvido', 'cpfCnpjEnvolvido']].drop_duplicates()
            envolvidos_unicos = envolvidos_unicos[envolvidos_unicos['cpfCnpjEnvolvido'] != 'DESCONHECIDO']
            
            opcoes = [f"{row['nomeEnvolvido']} ({row['cpfCnpjEnvolvido']})" for _, row in envolvidos_unicos.iterrows()]
            selecionado = st.selectbox("Selecione um envolvido para diligência:", sorted(opcoes), key="sel_diligencia_portal")
            
            # Extrair documento alvo
            doc_alvo = ''.join(filter(str.isdigit, selecionado))
            
            # Máscara de normalização
            mask_rif_alvo = st.session_state.df_final['cpfCnpjEnvolvido'].str.replace(r'\D', '', regex=True).str.contains(doc_alvo)
            
            # Execução da Busca Automática
            if st.button("🚀 Iniciar Busca"):
                ano_atual = pd.Timestamp.now().year
                lista_resultados = []
                
                with st.status(f"📡 Consultando base da CGU para {selecionado}...") as status:
                    for ano in range(2021, ano_atual + 1):
                        status.write(f"Buscando exercício {ano}...")
                        df_ano = fetch_portal_transparencia_data(doc_alvo, pd.Timestamp(year=ano, month=1, day=1), None)
                        if not df_ano.empty:
                            lista_resultados.append(df_ano)
                    
                    if lista_resultados:
                        st.session_state.df_pagamentos_resultado = pd.concat(lista_resultados, ignore_index=True)
                        status.update(label="✅ Consulta concluída!", state="complete")
                    else:
                        st.session_state.df_pagamentos_resultado = pd.DataFrame()
                        status.update(label="ℹ️ Nenhum pagamento encontrado no Portal.", state="complete")
            
            # Exibição dos Resultados Consolidados
            if 'df_pagamentos_resultado' in st.session_state and not st.session_state.df_pagamentos_resultado.empty:
                df_res = st.session_state.df_pagamentos_resultado.copy()
                
                # Tratamento de datas e valores
                col_valor_orig = 'valor' if 'valor' in df_res.columns else 'valorTotal'
                df_res['valor_float'] = df_res[col_valor_orig].apply(limpar_valor_portal)
                df_res['data_dt'] = pd.to_datetime(df_res['data'], format='%d/%m/%Y', errors='coerce')
                df_res['Ano'] = df_res['data_dt'].dt.year
                df_res['mes_ref'] = df_res['data_dt'].dt.to_period('M').dt.to_timestamp()
                
                # Resumo Financeiro
                st.markdown("### 📊 Resumo de Pagamentos")
                resumo_anual = df_res.groupby('Ano')['valor_float'].sum().reset_index()
                total_geral = df_res['valor_float'].sum()
                
                c1, c2 = st.columns([1, 2])
                c1.metric("Total Geral (2021-2026)", f"R$ {total_geral:,.2f}")
                c2.table(resumo_anual.style.format({'valor_float': 'R$ {:,.2f}'}))
                
                # Tabela com Alerta
                st.markdown("---")
                st.subheader("📑 Ordens Bancárias")
                
                # Aplicação da máscara para buscar datas do RIF
                datas_rif = st.session_state.df_final[mask_rif_alvo]['Data_da_operacao'].dt.to_period('M').unique()
                
                def verificar_nexo_expandido(dt_pag_dt):
                    try:
                        pag_period = dt_pag_dt.to_period('M')
                        return any(rif_p == pag_period or rif_p == (pag_period + 1) for rif_p in datas_rif)
                    except:
                        return False
                
                df_res['Alerta_Temporal'] = df_res['data_dt'].apply(verificar_nexo_expandido)
                
                # Estilo: Texto Preto sobre Fundo Amarelo
                def style_proximidade(row):
                    if row['Alerta_Temporal']:
                        return ['background-color: #fff3cd; color: black; font-weight: bold'] * len(row)
                    return [''] * len(row)
                
                cols_display = ['data', 'orgaoSuperior', 'valor', 'documento', 'observacao', 'Alerta_Temporal']
                cols_display = [c for c in cols_display if c in df_res.columns]
                
                st.dataframe(
                    df_res[cols_display].style.apply(style_proximidade, axis=1).hide(['Alerta_Temporal'], axis="columns"),
                    width='stretch',
                    hide_index=True
                )
                
                # Gráfico Mensal
                st.markdown("---")
                st.subheader("📅 Linha do Tempo Mensal: Sinalização de Alertas")
                
                # Agrupamento Mensal dos Pagamentos
                df_portal_m = df_res.groupby('mes_ref')['valor_float'].sum().reset_index()
                max_val_portal = df_portal_m['valor_float'].max() if not df_portal_m.empty else 1000
                
                # Agrupamento Mensal do RIF
                df_rif_all = st.session_state.df_final[mask_rif_alvo].copy()
                df_rif_all['mes_ref'] = df_rif_all['Data_da_operacao'].dt.to_period('M').dt.to_timestamp()
                
                # Remover duplicatas
                df_rif_unique = df_rif_all.drop_duplicates(subset=['idComunicacao'])
                
                df_rif_m = df_rif_unique.groupby('mes_ref').agg({
                    'ValorTotal': 'sum',
                    'idComunicacao': 'count'
                }).reset_index()
                
                # Desenho do Gráfico
                altura_fixa = max_val_portal * 1.05
                fig_timeline = go.Figure()
                
                # Barras de Pagamento
                fig_timeline.add_trace(go.Bar(
                    x=df_portal_m['mes_ref'], y=df_portal_m['valor_float'],
                    name='💰 Recebimento União', marker_color='#2ECC71'
                ))
                
                # Diamantes no Teto
                if not df_rif_m.empty:
                    fig_timeline.add_trace(go.Scatter(
                        x=df_rif_m['mes_ref'], y=[altura_fixa] * len(df_rif_m),
                        mode='markers', name='🚩 Alerta COAF (RIF)',
                        marker=dict(size=18, color='#E74C3C', symbol='diamond', line=dict(width=2, color='white')),
                        hovertemplate="<b>ALERTA IDENTIFICADO</b><br>Mês: %{x|%m/%Y}<br>Valor: R$ %{text}<extra></extra>",
                        text=[f"{v:,.2f}" for v in df_rif_m['ValorTotal']]
                    ))
                
                fig_timeline.update_layout(
                    template="plotly_white", hovermode="x unified", height=500,
                    xaxis=dict(title="Mês/Ano", tickformat="%m/%Y"),
                    yaxis=dict(title="Volume (R$)", range=[0, altura_fixa * 1.1]),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig_timeline, width='stretch', key='chart_portal_timeline')
        
        elif 'df_pagamentos_resultado' in st.session_state:
            st.info("Nenhum registro encontrado.")
        else:
            st.warning("⚠️ Carregue os arquivos RIF na barra lateral primeiro.")

    # -----------------------------------------
    # ABA: TRILHAS DA DIE
    # -----------------------------------------
    with tab_trilhas_die:
        if st.session_state.get("excel_file_uploaded"):
            render_trilhas_die_tab(
                st.session_state["excel_datasets"],
                st.session_state["excel_tabela_documentos"]
            )
        else:
            st.info("Para visualizar as Trilhas da DIE, carregue a planilha de detalhamento na barra lateral.")


# ==============================================
# BOTÃO DE ENCERRAMENTO DE SESSÃO
# ==============================================
st.sidebar.divider()
st.sidebar.subheader("🛡️ Segurança e Sessão")

if st.sidebar.button("🧹 Encerrar Sessão e Limpar Dados"):
    realizar_limpeza_seguranca()
    st.success("Sessão encerrada com sucesso!")
    st.rerun()


# ==============================================
# RODAPÉ
# ==============================================
st.sidebar.caption(f"Versão {VERSAO} | {DATA_VERSAO}")
st.sidebar.caption("⚠️ Nunca usar LLMs abertas com estes dados.")
