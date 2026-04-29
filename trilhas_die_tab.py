import streamlit as st
import pandas as pd
import re
import streamlit.components.v1 as components
import plotly.express as px
from pyvis.network import Network

# IMPORTS ABSOLUTOS
from config import MAPA_ABAS_REGRAS, ABAS_REDE
from project_utils.helpers import normalize_string

def render_trilhas_die_tab(excel_datasets: dict, excel_tabela_documentos: pd.DataFrame):
    """
    Renders the "Trilhas da DIE" tab content based on pre-loaded Excel data.

    Args:
        excel_datasets: A dictionary of DataFrames loaded from the Excel file.
        excel_tabela_documentos: A DataFrame with master identity information.
    """
    st.title("🕵️‍♂️ Analisador de RIF - Trilhas DIE")
    st.markdown("---")

    # --- INTERFACE DE FILTROS ---
    if excel_datasets:
        c1, c2 = st.columns(2)
        with c1:
            if not excel_tabela_documentos.empty:
                opcoes = (
                    excel_tabela_documentos
                    .apply(
                        lambda x: f"{x['nome_razao_social']} ({x['cpf_cnpj']})",
                        axis=1,
                    )
                    .tolist()
                )
                alvos_sel = st.multiselect(
                    "Alvos Investigados (Nome/Documento):",
                    options=sorted(opcoes),
                    key="trilhas_alvos_sel" # Unique key for this widget
                )
            else:
                alvos_sel = []

        with c2:
            ids_com = set()
            for d in excel_datasets.values():
                cs = [
                    c
                    for c in d.columns
                    if "ID" in c.upper()
                    and "COMUNICA" in c.upper()
                    and "DATA" not in c.upper()
                ]
                for c in cs:
                    ids_com.update(d[c].dropna().astype(str).unique())
            ids_sel = st.multiselect(
                "IDs Comunicação:",
                options=sorted(
                    [i for i in ids_com if "/" not in i and len(i) > 4]
                ),
                key="trilhas_ids_sel" # Unique key for this widget
            )

        # --- REDE PESSOAS/EMPRESAS ↔ COMUNICAÇÕES (PyVis, filtrada por alvos E IDs) ---
        edges = []
        nodes_docs = set()
        nodes_ids = set()

        # documentos selecionados (cpfs/cnpjs) a partir dos alvos
        docs_busca_rede = [
            re.search(r"\((.*?)\)", s).group(1)
            for s in alvos_sel
            if "(" in s
        ]

        ids_rede_filtrados = set()

        # CASO 1: há alvos selecionados -> mesma lógica de antes (alvos + IDs)
        if docs_busca_rede:
            regex_doc_rede = "|".join(
                [re.escape(d) for d in docs_busca_rede]
            )

            # IDs de comunicação que têm pelo menos um dos alvos
            for nome_aba, df in excel_datasets.items():
                aba_norm = normalize_string(nome_aba)
                if aba_norm not in ABAS_REDE:
                    continue

                col_doc_aba = MAPA_ABAS_REGRAS.get(aba_norm)
                col_doc_real = None
                if col_doc_aba:
                    col_doc_real = next(
                        (
                            c
                            for c in df.columns
                            if normalize_string(c) == normalize_string(col_doc_aba)
                        ),
                        None,
                    )
                if not col_doc_real:
                    continue

                cols_id = [
                    c
                    for c in df.columns
                    if "ID" in c.upper()
                    and "COMUNICA" in c.upper()
                    and "DATA" not in c.upper()
                ]
                if not cols_id:
                    continue
                col_id = cols_id[0]

                df_tmp = df[[col_id, col_doc_real]].dropna()
                df_tmp[col_id] = df_tmp[col_id].astype(str)
                df_tmp[col_doc_real] = df_tmp[col_doc_real].astype(str)

                mask_docs = df_tmp[col_doc_real].str.contains(
                    regex_doc_rede, na=False
                )
                df_ids_alvo = df_tmp[mask_docs]

                ids_rede_filtrados.update(df_ids_alvo[col_id].unique())

            # aplicar filtro de IDs Comunicação do usuário, se houver
            if ids_sel:
                ids_rede_filtrados = ids_rede_filtrados.intersection(
                    set(ids_sel)
                )

        # CASO 2: não há alvos, mas há IDs Comunicação selecionados
        elif ids_sel:
            ids_rede_filtrados = set(ids_sel)

        # 2) Montar arestas doc <-> comunicação com todos os envolvidos nessas comunicações
        if ids_rede_filtrados:
            for nome_aba, df in excel_datasets.items():
                aba_norm = normalize_string(nome_aba)
                if aba_norm not in ABAS_REDE:
                    continue

                col_doc_aba = MAPA_ABAS_REGRAS.get(aba_norm)
                col_doc_real = None
                if col_doc_aba:
                    col_doc_real = next(
                        (
                            c
                            for c in df.columns
                            if normalize_string(c) == normalize_string(col_doc_aba)
                        ),
                        None,
                    )
                if not col_doc_real:
                    continue

                cols_id = [
                    c
                    for c in df.columns
                    if "ID" in c.upper()
                    and "COMUNICA" in c.upper()
                    and "DATA" not in c.upper()
                ]
                if not cols_id:
                    continue
                col_id = cols_id[0]

                df_tmp = df[[col_id, col_doc_real]].dropna()
                df_tmp[col_id] = df_tmp[col_id].astype(str)
                df_tmp[col_doc_real] = df_tmp[col_doc_real].astype(str)

                df_tmp = df_tmp[df_tmp[col_id].isin(ids_rede_filtrados)]

                for _, r in df_tmp.iterrows():
                    doc = r[col_doc_real]
                    id_com = r[col_id]
                    edges.append((doc, id_com))
                    nodes_docs.add(doc)
                    nodes_ids.add(id_com)


        # construção do grafo bipartido com PyVis
        if edges:
            df_edges = pd.DataFrame(edges, columns=["doc", "id_com"])
            df_edges["peso"] = 1
            df_edges = (
                df_edges.groupby(["doc", "id_com"])["peso"]
                .sum()
                .reset_index()
            )

            # mapa doc -> nome/razão social
            mapa_nome = {}
            if not excel_tabela_documentos.empty:
                for _, r in excel_tabela_documentos.iterrows():
                    doc = str(r["cpf_cnpj"])
                    nome = str(r["nome_razao_social"])
                    mapa_nome[doc] = nome if nome else doc

            docs_alvo_set = set(docs_busca_rede)

            # --- PyVis Network ---
            net = Network(
                height="800px",
                width="100%",
                bgcolor="#ffffff",
                font_color="#222222",
            )
            net.barnes_hut(
                gravity=-2000,
                central_gravity=0.1,
                spring_length=250,
                spring_strength=0.01,
                damping=0.4,
            )

            # nós de documentos (pessoas/empresas)
            for d in nodes_docs:
                label = mapa_nome.get(d, d)
                if d in docs_alvo_set:
                    net.add_node(
                        d,
                        label=label,
                        color="#FF4136",   # vermelho para alvos
                        size=30,
                        title=f"Envolvido (alvo) - {label}",
                        font={"size": 20},
                    )
                else:
                    net.add_node(
                        d,
                        label=label,
                        color="#34495E",
                        size=20,
                        title=f"Envolvido - {label}",
                        font={"size": 16},
                    )

            # nós de comunicações (ID COMUNICAÇÃO)
            for c in nodes_ids:
                net.add_node(
                    c,
                    label=str(c),
                    color="#1F77B4",
                    shape="dot",
                    size=15,
                    title=f"ID Comunicação {c}",
                    font={"size": 16},
                )

            # arestas doc <-> comunicação
            for _, row in df_edges.iterrows():
                net.add_edge(
                    row["doc"],
                    row["id_com"],
                    value=row["peso"],
                    color="#AAAAAA",
                )

            # interatividade: arrastar nós, ajustar física
            net.toggle_drag_nodes(True)
            net.toggle_physics(True)
            net.show_buttons(filter_=["physics"])

            # gerar HTML e embedar no Streamlit
            html_file = "rede_pessoas_comunicacoes.html"
            net.save_graph(html_file)
            st.markdown(
                "### 🌐 Rede de Pessoas/Empresas ↔ Comunicações "
                "(Interativa, filtrada por Alvos e IDs Comunicação)"
            )
            with open(html_file, "r", encoding="utf-8") as f:
                components.html(f.read(), height=750, scrolling=True)
        else:
            st.info(
                "Não há comunicações com os filtros atuais suficientes para montar a rede de vínculos."
            )

        # --- EXIBIÇÃO DOS RESULTADOS (TRILHAS) ---
        if alvos_sel or ids_sel:
            docs_busca = [
                re.search(r"\((.*?)\)", s).group(1)
                for s in alvos_sel
                if "(" in s
            ]
            st.markdown("---")
            st.header("🔍 Trilhas")
            st.info(
                "Aqui você vê os registros das trilhas para os critérios de filtragem"
            )
            algum_res = False

            for nome_aba, df in excel_datasets.items():
                aba_norm = normalize_string(nome_aba)
                col_mapeada = MAPA_ABAS_REGRAS.get(aba_norm)

                mask_doc = pd.Series([False] * len(df))
                col_real = None

                if docs_busca:
                    regex_doc = "|".join([re.escape(d) for d in docs_busca])
                    if col_mapeada:
                        col_real = next(
                            (
                                c
                                for c in df.columns
                                if normalize_string(c) == normalize_string(col_mapeada)
                            ),
                            None,
                        )

                    if col_real:
                        mask_doc = df[col_real].astype(str).str.contains(
                            regex_doc, na=False
                        )
                    else:
                        cols_alt = [
                            c
                            for c in df.columns
                            if "CPF" in c.upper() or "CNPJ" in c.upper()
                        ]
                        if cols_alt:
                            mask_doc = (
                                df[cols_alt]
                                .astype(str)
                                .apply(
                                    lambda x: x.str.contains(
                                        regex_doc, na=False
                                    )
                                )
                                .any(axis=1)
                            )

                c_id = [
                    c
                    for c in df.columns
                    if "ID" in c.upper()
                    and "COMUNICA" in c.upper()
                    and "DATA" not in c.upper()
                ]
                mask_id = (
                    df[c_id].astype(str).isin(ids_sel).any(axis=1)
                    if (ids_sel and c_id)
                    else pd.Series([False] * len(df))
                )

                df_res = df[mask_doc | mask_id]

                if not df_res.empty:
                    algum_res = True
                    with st.expander(
                        f"📊 {nome_aba} ({len(df_res)} registros)",
                        expanded=False,
                    ):
                        st.dataframe(
                            df_res,
                            width='stretch',
                            hide_index=True,
                        )

                        # --- LÓGICA ESPECIAL: RECURSOS FEDERAIS ---
                        if aba_norm == normalize_string("Recursos Federais"):
                            st.markdown(
                                "#### 💰 Resumo Consolidado de Pagamentos (Por Fonte/Ano)"
                            )

                            col_valor_rf = (
                                "RECURSOS DE COMPETÊNCIA FEDERAL PAGOS - R$"
                            )
                            col_nome_rf = "NOME DO FAVORECIDO"
                            colunas_resumo = [
                                col_real if col_real else "CPF/CNPJ",
                                col_nome_rf,
                                "ÓRGÃO FEDERAL / ENTE SUBNACIONAL PAGADOR",
                                "FONTE DOS RECUROS",
                                "ANO",
                                col_valor_rf,
                            ]

                            cols_existentes = [
                                c for c in colunas_resumo if c in df_res.columns
                            ]

                            if len(cols_existentes) > 1:
                                df_unicos = (
                                    df_res[cols_existentes]
                                    .drop_duplicates()
                                    .copy()
                                )
                                df_unicos[col_valor_rf] = pd.to_numeric(
                                    df_unicos[col_valor_rf],
                                    errors="coerce",
                                ).fillna(0)

                                st.dataframe(
                                    df_unicos,
                                    width='stretch',
                                    hide_index=True,
                                    column_config={
                                        col_valor_rf: st.column_config.NumberColumn(
                                            "Valor Pago (R$)",
                                            format="R$ %.2f",
                                        ),
                                        "ANO": st.column_config.NumberColumn(
                                            "Ano", format="%d"
                                        ),
                                    },
                                )

                                # --- GRÁFICO DE BARRAS (PLOTLY INTERATIVO) ---
                                st.markdown(
                                    "#### 📈 Evolução Anual de Pagamentos"
                                )

                                df_grafico = (
                                    df_unicos.groupby(
                                        [col_nome_rf, "ANO"]
                                    )[col_valor_rf]
                                    .sum()
                                    .reset_index()
                                )

                                if not df_grafico.empty:
                                    fig_plotly = px.bar(
                                        df_grafico,
                                        x="ANO",
                                        y=col_valor_rf,
                                        color=col_nome_rf,
                                        barmode="group",
                                        title="Volume de Recursos por Ano",
                                        labels={
                                            "ANO": "Ano",
                                            col_valor_rf: "Total Pago (R$)",
                                            col_nome_rf: "Favorecido",
                                        },
                                    )
                                    fig_plotly.update_layout(
                                        legend_title_text="Favorecido"
                                    )
                                    fig_plotly.update_yaxes(
                                        tickprefix="R$ ",
                                        separatethousands=True,
                                    )

                                    st.plotly_chart(
                                        fig_plotly,
                                        width='stretch',
                                    )
                                    
                        # --- LÓGICA ESPECIAL: EMENDAS PARLAMENTARES ---
                        if aba_norm == normalize_string("Envolv. emendas parl."):
                            st.markdown("#### 📈 Evolução Anual de Valores de Emendas")

                            col_valor_emenda = "VALOR PAGO R$"
                            col_ano = "ANO"
                            col_razao = "RAZÃO SOCIAL"
                            col_tipo_emenda = "TIPO EMENDA"
                            col_autor = "AUTOR"

                            # garante que as colunas existam
                            cols_necessarias = [col_valor_emenda, col_ano]
                            if not all(c in df_res.columns for c in cols_necessarias):
                                st.warning("Colunas necessárias para os gráficos de emendas não foram encontradas nesta aba.")
                            else:
                                df_plot = df_res.copy()
                                df_plot[col_valor_emenda] = pd.to_numeric(
                                    df_plot[col_valor_emenda], errors="coerce"
                                ).fillna(0)
                                df_plot[col_ano] = pd.to_numeric(
                                    df_plot[col_ano], errors="coerce"
                                ).astype("Int64")

                                opcao = st.selectbox(
                                    "Agregação do gráfico:",
                                    ["por Razão Social", "por Tipo de Emenda", "por Autor"],
                                    key=f"agr_emendas_{nome_aba}",
                                )

                                if opcao == "por Razão Social":
                                    col_grupo = col_razao
                                    titulo = "Total de Valor Pago por Razão Social e Ano"
                                    legenda = "Razão Social"
                                elif opcao == "por Tipo de Emenda":
                                    col_grupo = col_tipo_emenda
                                    titulo = "Total de Valor Pago por Tipo de Emenda e Ano"
                                    legenda = "Tipo de Emenda"
                                else:  # "por Autor"
                                    col_grupo = col_autor
                                    titulo = "Total de Valor Pago por Autor e Ano"
                                    legenda = "Autor"

                                if col_grupo not in df_plot.columns:
                                    st.warning(f'A coluna "{col_grupo}" não foi encontrada na aba de emendas.')
                                else:
                                    df_group = (
                                        df_plot.groupby([col_grupo, col_ano])[col_valor_emenda]
                                        .sum()
                                        .reset_index()
                                    )

                                    if df_group.empty:
                                        st.info("Não há dados suficientes para gerar o gráfico.")
                                    else:
                                        fig = px.bar(
                                            df_group,
                                            x=col_ano,
                                            y=col_valor_emenda,
                                            color=col_grupo,
                                            barmode="group",
                                            title=titulo,
                                            labels={
                                                col_ano: "Ano",
                                                col_valor_emenda: "Valor Pago (R$)",
                                                col_grupo: legenda,
                                            },
                                        )
                                        fig.update_yaxes(
                                            tickprefix="R$ ",
                                            separatethousands=True,
                                        )
                                        fig.update_layout(legend_title_text=legenda)
                                        st.plotly_chart(fig, width='stretch')            

            if not algum_res:
                st.warning(
                    "Nenhum registro encontrado para os critérios selecionados."
                )

        # --- EXPLORAÇÃO DE ABAS ---
        st.markdown("---")
        with st.expander(
            "📂 Explorar Abas Completas (Visualização Integral)", expanded=False
        ):
            aba_escolhida = st.selectbox(
                "Selecione a aba:",
                list(excel_datasets.keys()),
                key="trilhas_aba_escolhida" # Unique key for this widget
            )
            if aba_escolhida:
                st.dataframe(
                    excel_datasets[aba_escolhida],
                    width='stretch',
                )

    else:
        st.info("Aguardando carregamento da planilha de detalhamento na barra lateral.")