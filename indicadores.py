# indicadores.py
# Módulo de indicadores quantitativos para o RIFAnalyst_3.1
# Focado em: perfil por envolvido, por comunicação e por par de contrapartes.

from __future__ import annotations

import pandas as pd
import numpy as np

# --------------------------------------------------------------------------------------
# Helpers internos
# --------------------------------------------------------------------------------------


def _is_datetime_series(s: pd.Series) -> bool:
    return pd.api.types.is_datetime64_any_dtype(s)


def _ensure_datetime(df: pd.DataFrame, col: str) -> pd.Series:
    """
    Garante que df[col] esteja em datetime64, tentando parse se necessário.
    Se não existir, cria coluna cheia de NaT.
    """
    if col not in df.columns:
        df[col] = pd.NaT
        return df[col]

    if not _is_datetime_series(df[col]):
        df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
    return df[col]


def _safe_div(num, den):
    if den is None or den == 0 or pd.isna(den):
        return 0.0
    return float(num) / float(den)


# --------------------------------------------------------------------------------------
# Indicadores por envolvido (CPF/CNPJ)
# --------------------------------------------------------------------------------------


def calc_indicadores_envolvido(
    df: pd.DataFrame,
    valor_col: str = "ValorTotal",
    data_col: str = "Datadaoperacao",
) -> pd.DataFrame:
    """
    Gera um DataFrame com uma linha por cpfCnpjEnvolvido contendo:
    - volume total e nº de comunicações
    - indicadores de fracionamento básico
    - concentração de contrapartes (HHI e top-N)
    - perfil de espécie (CampoA/B em espécie, se disponível)
    - exposição a PEP / Servidor / Pessoa Obrigada

    Parâmetros
    ----------
    df : DataFrame equivalente ao dffinal (já com merges efetuados).
    valor_col : nome da coluna de valor principal (padrão: 'ValorTotal').
    data_col  : nome da coluna de data de operação (padrão: 'Datadaoperacao').

    Retorno
    -------
    DataFrame com índices numéricos e coluna 'cpfCnpjEnvolvido'.
    """
    if df is None or df.empty:
        return pd.DataFrame(
            columns=[
                "cpfCnpjEnvolvido",
                "nomeEnvolvido",
                "n_comunicacoes",
                "valor_total",
                "valor_medio",
                "n_dias_atividade",
                "fracionamento_dias_com_3+_ops",
                "pct_ops_proximas_limite_50k",
                "hhi_contrapartes",
                "pct_top1_contraparte",
                "pct_top3_contrapartes",
                "pct_top5_contrapartes",
                "pct_valor_especie_A",
                "pct_valor_especie_B",
                "flag_pep",
                "flag_servidor",
                "flag_pessoa_obrigada",
            ]
        )

    df_local = df.copy()

    # Garante colunas essenciais
    for col in ["cpfCnpjEnvolvido", "Indexador_x", "idComunicacao"]:
        if col not in df_local.columns:
            df_local[col] = np.nan

    # Normaliza valor e data
    if valor_col not in df_local.columns:
        df_local[valor_col] = 0.0

    df_local[valor_col] = pd.to_numeric(df_local[valor_col], errors="coerce").fillna(0.0)
    df_local[data_col] = _ensure_datetime(df_local, data_col)

    # Nome do envolvido (usando o "mais frequente" ou primeiro)
    if "nomeEnvolvido" not in df_local.columns:
        df_local["nomeEnvolvido"] = "DESCONHECIDO"

    # Flags de risco
    for flag in ["bitPepCitado", "bitPessoaObrigadaCitado", "intServidorCitado"]:
        if flag not in df_local.columns:
            df_local[flag] = False
        else:
            df_local[flag] = (
                df_local[flag]
                .fillna(False)
                .apply(lambda x: True if str(x).strip().lower() == "sim" else bool(x))
            )

    # ------------------------------------------------------------------
    # Métricas agregadas simples por envolvido
    # ------------------------------------------------------------------
    base_agg = (
        df_local.groupby("cpfCnpjEnvolvido", dropna=False)
        .agg(
            nomeEnvolvido=("nomeEnvolvido", lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else x.iloc[0]),
            n_comunicacoes=("idComunicacao", "nunique"),
            valor_total=(valor_col, "sum"),
            valor_medio=(valor_col, "mean"),
            n_dias_atividade=(data_col, lambda x: x.dt.date.nunique()),
        )
        .reset_index()
    )

    # ------------------------------------------------------------------
    # Fracionamento básico (dias com 3+ operações no mesmo dia)
    # e % de operações próximas a limite de 50k
    # ------------------------------------------------------------------
    # base diaria por envolvido + dia
    daily_counts = (
        df_local.dropna(subset=["cpfCnpjEnvolvido", data_col])
        .assign(dia=lambda x: x[data_col].dt.date)
        .groupby(["cpfCnpjEnvolvido", "dia"], dropna=False)
        .agg(
            n_ops=("idComunicacao", "nunique"),
            valor_dia=(valor_col, "sum"),
        )
        .reset_index()
    )

    limite_reporte = 50000.0
    faixa_inferior = 0.90 * limite_reporte
    faixa_superior = 0.99 * limite_reporte

    # dias com 3+ ops
    frac_diaria = (
        daily_counts[daily_counts["n_ops"] >= 3]
        .groupby("cpfCnpjEnvolvido", dropna=False)
        .agg(
            dias_com_3plus=("dia", "nunique"),
        )
        .reset_index()
    )

    # operações individuais próximas ao limite (faixa perigosa)
    df_structuring = df_local[
        (df_local[valor_col].between(faixa_inferior, faixa_superior, inclusive="both"))
        & df_local["cpfCnpjEnvolvido"].notna()
    ].copy()

    structuring_counts = (
        df_structuring.groupby("cpfCnpjEnvolvido", dropna=False)
        .agg(
            n_ops_prox_limite=("idComunicacao", "nunique"),
        )
        .reset_index()
    )

    total_ops_por_envolvido = (
        df_local.groupby("cpfCnpjEnvolvido", dropna=False)
        .agg(
            n_ops_total=("idComunicacao", "nunique"),
        )
        .reset_index()
    )

    # Merge de fracionamento
    frac_merged = (
        total_ops_por_envolvido.merge(frac_diaria, on="cpfCnpjEnvolvido", how="left")
        .merge(structuring_counts, on="cpfCnpjEnvolvido", how="left")
    )

    frac_merged["dias_com_3plus"] = frac_merged["dias_com_3plus"].fillna(0).astype(int)
    frac_merged["n_ops_prox_limite"] = frac_merged["n_ops_prox_limite"].fillna(0).astype(int)

    frac_merged["fracionamento_dias_com_3+_ops"] = frac_merged["dias_com_3plus"]
    frac_merged["pct_ops_proximas_limite_50k"] = frac_merged.apply(
        lambda r: _safe_div(r["n_ops_prox_limite"], r["n_ops_total"]) * 100, axis=1
    )

    # ------------------------------------------------------------------
    # Concentração de contrapartes (HHI e top-N)
    # Aqui, para simplificar, definimos contraparte como "outro cpfCnpj"
    # nas mesmas comunicações (Indexador_x) em que o envolvido aparece.
    # ------------------------------------------------------------------
    df_contra = df_local[
        df_local["cpfCnpjEnvolvido"].notna() & df_local["Indexador_x"].notna()
    ][["Indexador_x", "cpfCnpjEnvolvido", valor_col]]

    # self-merge em Indexador_x para obter pares (envolvido, contraparte)
    df_pairs = (
        df_contra.merge(
            df_contra,
            on="Indexador_x",
            suffixes=("_orig", "_contra"),
        )
        .query("cpfCnpjEnvolvido_orig != cpfCnpjEnvolvido_contra")
    )

    df_pairs["valor_par"] = df_pairs[f"{valor_col}_contra"]

    # valor total por (envolvido, contraparte)
    pares_agg = (
        df_pairs.groupby(["cpfCnpjEnvolvido_orig", "cpfCnpjEnvolvido_contra"], dropna=False)
        .agg(valor_par=("valor_par", "sum"))
        .reset_index()
    )

    total_por_envolvido = (
        pares_agg.groupby("cpfCnpjEnvolvido_orig", dropna=False)
        .agg(total_valor=("valor_par", "sum"))
        .reset_index()
    )

    pares_agg = pares_agg.merge(
        total_por_envolvido,
        on="cpfCnpjEnvolvido_orig",
        how="left",
    )

    pares_agg["share"] = pares_agg.apply(
        lambda r: _safe_div(r["valor_par"], r["total_valor"]), axis=1
    )

    # HHI e top-N
    def _calc_concentracao(grp: pd.DataFrame):
        shares = grp["share"].values
        if shares.size == 0:
            return pd.Series(
                {
                    "hhi_contrapartes": 0.0,
                    "pct_top1_contraparte": 0.0,
                    "pct_top3_contrapartes": 0.0,
                    "pct_top5_contrapartes": 0.0,
                }
            )
        shares_sorted = np.sort(shares)[::-1]
        hhi = float(np.sum(shares_sorted ** 2))
        top1 = float(shares_sorted[0])
        top3 = float(np.sum(shares_sorted[:3]))
        top5 = float(np.sum(shares_sorted[:5]))
        return pd.Series(
            {
                "hhi_contrapartes": hhi,
                "pct_top1_contraparte": top1 * 100,
                "pct_top3_contrapartes": top3 * 100,
                "pct_top5_contrapartes": top5 * 100,
            }
        )

    conc_agg = (
        pares_agg.groupby("cpfCnpjEnvolvido_orig", dropna=False)
        .apply(_calc_concentracao)
        .reset_index()
        .rename(columns={"cpfCnpjEnvolvido_orig": "cpfCnpjEnvolvido"})
    )

    # ------------------------------------------------------------------
    # Perfil de espécie (Campos A/B em espécie), se disponíveis
    # Aqui consideramos que ValorCampoA/B são valores de espécie quando o
    # CodigoSegmento está em segmentos de espécie (similar a padrões 12 etc.).
    # ------------------------------------------------------------------
    especie_cols = []
    for c in ["ValorCampoA", "ValorCampoB"]:
        if c in df_local.columns:
            df_local[c] = pd.to_numeric(df_local[c], errors="coerce").fillna(0.0)
            especie_cols.append(c)

    # escolha de alguns segmentos fortemente associados a espécie (mesma ideia dos padrões)
    segmentos_especie = {"19", "23", "15", "46", "48", "49", "51", "52"}
    if "CodigoSegmento" in df_local.columns:
        df_local["CodigoSegmento_str"] = df_local["CodigoSegmento"].astype(str)
    else:
        df_local["CodigoSegmento_str"] = ""

    df_especie = df_local[
        df_local["CodigoSegmento_str"].isin(segmentos_especie)
        & df_local["cpfCnpjEnvolvido"].notna()
    ].copy()

    if not df_especie.empty and especie_cols:
        df_especie["valor_especie_A"] = df_especie["ValorCampoA"] if "ValorCampoA" in especie_cols else 0.0
        df_especie["valor_especie_B"] = df_especie["ValorCampoB"] if "ValorCampoB" in especie_cols else 0.0

        especie_agg = (
            df_especie.groupby("cpfCnpjEnvolvido", dropna=False)
            .agg(
                valor_especie_A=("valor_especie_A", "sum"),
                valor_especie_B=("valor_especie_B", "sum"),
            )
            .reset_index()
        )
    else:
        especie_agg = pd.DataFrame(
            columns=["cpfCnpjEnvolvido", "valor_especie_A", "valor_especie_B"]
        )

    # valor total por envolvido (para denominator)
    valor_total_envolvido = (
        df_local.groupby("cpfCnpjEnvolvido", dropna=False)
        .agg(valor_total_envolvido=(valor_col, "sum"))
        .reset_index()
    )

    especie_agg = especie_agg.merge(
        valor_total_envolvido,
        on="cpfCnpjEnvolvido",
        how="right",
    )

    especie_agg["valor_especie_A"] = especie_agg["valor_especie_A"].fillna(0.0)
    especie_agg["valor_especie_B"] = especie_agg["valor_especie_B"].fillna(0.0)

    especie_agg["pct_valor_especie_A"] = especie_agg.apply(
        lambda r: _safe_div(r["valor_especie_A"], r["valor_total_envolvido"]) * 100, axis=1
    )
    especie_agg["pct_valor_especie_B"] = especie_agg.apply(
        lambda r: _safe_div(r["valor_especie_B"], r["valor_total_envolvido"]) * 100, axis=1
    )

    especie_agg = especie_agg[
        ["cpfCnpjEnvolvido", "pct_valor_especie_A", "pct_valor_especie_B"]
    ]

    # ------------------------------------------------------------------
    # Exposição a PEP / Servidor / Pessoa Obrigada
    # Flagamos se em qualquer comunicação o envolvido aparece com essas flags.
    # ------------------------------------------------------------------
    flags_agg = (
        df_local.groupby("cpfCnpjEnvolvido", dropna=False)
        .agg(
            flag_pep=("bitPepCitado", "max"),
            flag_pessoa_obrigada=("bitPessoaObrigadaCitado", "max"),
            flag_servidor=("intServidorCitado", "max"),
        )
        .reset_index()
    )

    # ------------------------------------------------------------------
    # Consolidar tudo
    # ------------------------------------------------------------------
    result = (
        base_agg.merge(frac_merged[["cpfCnpjEnvolvido", "fracionamento_dias_com_3+_ops", "pct_ops_proximas_limite_50k"]], on="cpfCnpjEnvolvido", how="left")
        .merge(conc_agg, on="cpfCnpjEnvolvido", how="left")
        .merge(especie_agg, on="cpfCnpjEnvolvido", how="left")
        .merge(flags_agg, on="cpfCnpjEnvolvido", how="left")
    )

    # Ajustes finais
    for col in [
        "hhi_contrapartes",
        "pct_top1_contraparte",
        "pct_top3_contrapartes",
        "pct_top5_contrapartes",
        "pct_valor_especie_A",
        "pct_valor_especie_B",
        "pct_ops_proximas_limite_50k",
    ]:
        if col in result.columns:
            result[col] = result[col].fillna(0.0)

    result["fracionamento_dias_com_3+_ops"] = result["fracionamento_dias_com_3+_ops"].fillna(0).astype(int)

    # Ordena por maior valor_total (ou como preferir)
    result = result.sort_values("valor_total", ascending=False).reset_index(drop=True)

    return result


# --------------------------------------------------------------------------------------
# Indicadores por comunicação (Indexador_x)
# --------------------------------------------------------------------------------------


def calc_indicadores_comunicacao(
    df: pd.DataFrame,
    valor_col: str = "ValorTotal",
) -> pd.DataFrame:
    """
    Indicadores por comunicação (Indexador_x):
    - nº de envolvidos
    - valor total (CampoA / ValorTotal)
    - % espécie em segmentos de espécie
    - presença de PEP / Servidor / Pessoa Obrigada dentro da comunicação
    """
    if df is None or df.empty or "Indexador_x" not in df.columns:
        return pd.DataFrame(
            columns=[
                "Indexador_x",
                "n_envolvidos",
                "valor_total",
                "pct_valor_especie_A",
                "pct_valor_especie_B",
                "flag_pep_na_com",
                "flag_servidor_na_com",
                "flag_pessoa_obrigada_na_com",
            ]
        )

    df_local = df.copy()

    # normaliza valor
    if valor_col not in df_local.columns:
        df_local[valor_col] = 0.0
    df_local[valor_col] = pd.to_numeric(df_local[valor_col], errors="coerce").fillna(0.0)

    # flags
    for flag in ["bitPepCitado", "bitPessoaObrigadaCitado", "intServidorCitado"]:
        if flag not in df_local.columns:
            df_local[flag] = False
        else:
            df_local[flag] = (
                df_local[flag]
                .fillna(False)
                .apply(lambda x: True if str(x).strip().lower() == "sim" else bool(x))
            )

    # base agregada por Indexador
    base = (
        df_local.groupby("Indexador_x", dropna=False)
        .agg(
            n_envolvidos=("cpfCnpjEnvolvido", "nunique"),
            valor_total=(valor_col, "sum"),
            flag_pep_na_com=("bitPepCitado", "max"),
            flag_pessoa_obrigada_na_com=("bitPessoaObrigadaCitado", "max"),
            flag_servidor_na_com=("intServidorCitado", "max"),
        )
        .reset_index()
    )

    # espécie A/B por comunicação (se existir)
    especie_cols = []
    for c in ["ValorCampoA", "ValorCampoB"]:
        if c in df_local.columns:
            df_local[c] = pd.to_numeric(df_local[c], errors="coerce").fillna(0.0)
            especie_cols.append(c)

    segmentos_especie = {"19", "23", "15", "46", "48", "49", "51", "52"}
    if "CodigoSegmento" in df_local.columns:
        df_local["CodigoSegmento_str"] = df_local["CodigoSegmento"].astype(str)
    else:
        df_local["CodigoSegmento_str"] = ""

    df_especie = df_local[df_local["CodigoSegmento_str"].isin(segmentos_especie)].copy()

    if not df_especie.empty and especie_cols:
        df_especie["valor_especie_A"] = df_especie["ValorCampoA"] if "ValorCampoA" in especie_cols else 0.0
        df_especie["valor_especie_B"] = df_especie["ValorCampoB"] if "ValorCampoB" in especie_cols else 0.0

        especie_agg = (
            df_especie.groupby("Indexador_x", dropna=False)
            .agg(
                valor_especie_A=("valor_especie_A", "sum"),
                valor_especie_B=("valor_especie_B", "sum"),
            )
            .reset_index()
        )
    else:
        especie_agg = pd.DataFrame(
            columns=["Indexador_x", "valor_especie_A", "valor_especie_B"]
        )

    especie_agg = especie_agg.merge(
        base[["Indexador_x", "valor_total"]],
        on="Indexador_x",
        how="right",
    )

    especie_agg["valor_especie_A"] = especie_agg["valor_especie_A"].fillna(0.0)
    especie_agg["valor_especie_B"] = especie_agg["valor_especie_B"].fillna(0.0)

    especie_agg["pct_valor_especie_A"] = especie_agg.apply(
        lambda r: _safe_div(r["valor_especie_A"], r["valor_total"]) * 100, axis=1
    )
    especie_agg["pct_valor_especie_B"] = especie_agg.apply(
        lambda r: _safe_div(r["valor_especie_B"], r["valor_total"]) * 100, axis=1
    )

    especie_agg = especie_agg[
        ["Indexador_x", "pct_valor_especie_A", "pct_valor_especie_B"]
    ]

    result = base.merge(especie_agg, on="Indexador_x", how="left")

    for col in ["pct_valor_especie_A", "pct_valor_especie_B"]:
        if col in result.columns:
            result[col] = result[col].fillna(0.0)

    result = result.sort_values("valor_total", ascending=False).reset_index(drop=True)

    return result


# --------------------------------------------------------------------------------------
# Indicadores por par de contrapartes (opcional)
# --------------------------------------------------------------------------------------


def calc_indicadores_pares(
    df: pd.DataFrame,
    valor_col: str = "ValorTotal",
) -> pd.DataFrame:
    """
    Indicadores por par de contrapartes (A <-> B), usando coocorrência nas mesmas comunicações.
    - valor total agregado A->B (somando valores de B na mesma comunicação de A)
    - nº de comunicações em comum
    """
    if (
        df is None
        or df.empty
        or "Indexador_x" not in df.columns
        or "cpfCnpjEnvolvido" not in df.columns
    ):
        return pd.DataFrame(
            columns=[
                "cpf_origem",
                "cpf_contraparte",
                "valor_total_par",
                "n_comunicacoes_compartilhadas",
            ]
        )

    df_local = df.copy()
    if valor_col not in df_local.columns:
        df_local[valor_col] = 0.0
    df_local[valor_col] = pd.to_numeric(df_local[valor_col], errors="coerce").fillna(0.0)

    df_contra = df_local[
        df_local["cpfCnpjEnvolvido"].notna() & df_local["Indexador_x"].notna()
    ][["Indexador_x", "cpfCnpjEnvolvido", valor_col]]

    # self-merge em Indexador_x
    df_pairs = (
        df_contra.merge(
            df_contra,
            on="Indexador_x",
            suffixes=("_orig", "_contra"),
        )
        .query("cpfCnpjEnvolvido_orig != cpfCnpjEnvolvido_contra")
    )

    df_pairs["valor_par"] = df_pairs[f"{valor_col}_contra"]

    pares_agg = (
        df_pairs.groupby(
            ["cpfCnpjEnvolvido_orig", "cpfCnpjEnvolvido_contra"],
            dropna=False,
        )
        .agg(
            valor_total_par=("valor_par", "sum"),
            n_comunicacoes_compartilhadas=("Indexador_x", "nunique"),
        )
        .reset_index()
        .rename(
            columns={
                "cpfCnpjEnvolvido_orig": "cpf_origem",
                "cpfCnpjEnvolvido_contra": "cpf_contraparte",
            }
        )
    )

    # ordenar por maior valor_total_par
    pares_agg = pares_agg.sort_values("valor_total_par", ascending=False).reset_index(
        drop=True
    )

    return pares_agg
