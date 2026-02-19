# indicadores.py
# Módulo de indicadores quantitativos para o RIFAnalyst_3.2
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
    if df is None or df.empty:
        return pd.DataFrame(columns=[
            "cpfCnpjEnvolvido", "nomeEnvolvido", "n_comunicacoes", "valor_total", 
            "valor_medio", "n_dias_atividade", "fracionamento_dias_com_3+_ops",
            "pct_ops_proximas_limite_50k", "hhi_contrapartes", "pct_top1_contraparte",
            "pct_top3_contrapartes", "pct_top5_contrapartes", "pct_valor_especie_A",
            "pct_valor_especie_B", "flag_pep", "flag_servidor", "flag_pessoa_obrigada"
        ])

    df_local = df.copy()

    # Normalização
    for col in ["cpfCnpjEnvolvido", "Indexador_x", "idComunicacao"]:
        if col not in df_local.columns: df_local[col] = np.nan
    
    df_local[valor_col] = pd.to_numeric(df_local[valor_col], errors="coerce").fillna(0.0)
    df_local[data_col] = _ensure_datetime(df_local, data_col)
    if "nomeEnvolvido" not in df_local.columns: df_local["nomeEnvolvido"] = "DESCONHECIDO"

    # Flags
    for flag in ["bitPepCitado", "bitPessoaObrigadaCitado", "intServidorCitado"]:
        if flag in df_local.columns:
            df_local[flag] = df_local[flag].fillna(False).apply(
                lambda x: True if str(x).strip().lower() == "sim" else bool(x)
            )
        else:
            df_local[flag] = False

    # 1. MÉTRICAS AGREGADAS
    df_unique_comm = (
        df_local.groupby(["cpfCnpjEnvolvido", "Indexador_x"], dropna=False)
        .agg({
            "nomeEnvolvido": "first",
            valor_col: "max", 
            "idComunicacao": "first",
            data_col: "first"
        })
        .reset_index()
    )

    base_agg = (
        df_unique_comm.groupby("cpfCnpjEnvolvido", dropna=False)
        .agg(
            nomeEnvolvido=("nomeEnvolvido", lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else x.iloc[0]),
            n_comunicacoes=("Indexador_x", "nunique"),
            valor_total=(valor_col, "sum"), 
            valor_medio=(valor_col, "mean"),
            n_dias_atividade=(data_col, lambda x: x.dt.date.nunique()),
        )
        .reset_index()
    )

    # 2. FRACIONAMENTO
    daily_counts = (
        df_local.dropna(subset=["cpfCnpjEnvolvido", data_col])
        .assign(dia=lambda x: x[data_col].dt.date)
        .groupby(["cpfCnpjEnvolvido", "dia"], dropna=False)
        .agg(n_ops=("idComunicacao", "nunique"), valor_dia=(valor_col, "max"))
        .reset_index()
    )
    limite_reporte = 50000.0
    frac_diaria = daily_counts[daily_counts["n_ops"] >= 3].groupby("cpfCnpjEnvolvido")["dia"].nunique().reset_index(name="dias_com_3plus")
    df_structuring = df_local[(df_local[valor_col].between(0.9 * limite_reporte, 0.99 * limite_reporte))].copy()
    struct_counts = df_structuring.groupby("cpfCnpjEnvolvido")["idComunicacao"].nunique().reset_index(name="n_ops_prox_limite")
    total_ops = df_local.groupby("cpfCnpjEnvolvido")["idComunicacao"].nunique().reset_index(name="n_ops_total")
    frac_merged = total_ops.merge(frac_diaria, on="cpfCnpjEnvolvido", how="left").merge(struct_counts, on="cpfCnpjEnvolvido", how="left").fillna(0)
    frac_merged["pct_ops_proximas_limite_50k"] = frac_merged.apply(lambda r: _safe_div(r["n_ops_prox_limite"], r["n_ops_total"]) * 100, axis=1)

    # 3. CONCENTRAÇÃO HHI
    df_contra_base = (
        df_local.dropna(subset=["cpfCnpjEnvolvido", "Indexador_x"])
        .groupby(["Indexador_x", "cpfCnpjEnvolvido"])[valor_col]
        .max()
        .reset_index()
    )
    df_pairs = df_contra_base.merge(df_contra_base, on="Indexador_x", suffixes=("_orig", "_contra")).query("cpfCnpjEnvolvido_orig != cpfCnpjEnvolvido_contra")
    pares_agg = df_pairs.groupby(["cpfCnpjEnvolvido_orig", "cpfCnpjEnvolvido_contra"])[f"{valor_col}_contra"].sum().reset_index(name="valor_par")
    total_por_env = pares_agg.groupby("cpfCnpjEnvolvido_orig")["valor_par"].sum().reset_index(name="total_vinc")
    pares_agg = pares_agg.merge(total_por_env, on="cpfCnpjEnvolvido_orig")
    pares_agg["share"] = pares_agg.apply(lambda r: _safe_div(r["valor_par"], r["total_vinc"]), axis=1)

    def _calc_hhi(grp):
        shares = np.sort(grp["share"].values)[::-1]
        return pd.Series({
            "hhi_contrapartes": float(np.sum(shares**2)),
            "pct_top1_contraparte": float(shares[0]*100) if shares.size > 0 else 0,
            "pct_top3_contrapartes": float(np.sum(shares[:3])*100) if shares.size > 0 else 0,
            "pct_top5_contrapartes": float(np.sum(shares[:5])*100) if shares.size > 0 else 0
        })
    conc_agg = pares_agg.groupby("cpfCnpjEnvolvido_orig").apply(_calc_hhi).reset_index().rename(columns={"cpfCnpjEnvolvido_orig": "cpfCnpjEnvolvido"})

    # 4. PERFIL ESPÉCIE (COM PROTEÇÃO CONTRA COLUNAS AUSENTES)
    segmentos_especie = {"19", "23", "15", "46", "48", "49", "51", "52"}
    df_local["CodigoSegmento_str"] = df_local["CodigoSegmento"].astype(str) if "CodigoSegmento" in df_local.columns else ""
    
    col_A = "ValorCampoA" if "ValorCampoA" in df_local.columns else None
    col_B = "ValorCampoB" if "ValorCampoB" in df_local.columns else None

    if col_A or col_B:
        agg_map = {}
        if col_A: agg_map["vA"] = (col_A, "max")
        if col_B: agg_map["vB"] = (col_B, "max")
        
        esp_sub = df_local[df_local["CodigoSegmento_str"].isin(segmentos_especie)].groupby(["cpfCnpjEnvolvido", "Indexador_x"]).agg(**agg_map).reset_index()
        especie_agg = esp_sub.groupby("cpfCnpjEnvolvido").agg(
            sA=("vA", "sum") if col_A else ("cpfCnpjEnvolvido", "count"), # Dummy se ausente
            sB=("vB", "sum") if col_B else ("cpfCnpjEnvolvido", "count")
        ).reset_index()
        if not col_A: especie_agg["sA"] = 0
        if not col_B: especie_agg["sB"] = 0
    else:
        especie_agg = pd.DataFrame(columns=["cpfCnpjEnvolvido", "sA", "sB"])

    especie_agg = especie_agg.merge(base_agg[["cpfCnpjEnvolvido", "valor_total"]], on="cpfCnpjEnvolvido", how="right").fillna(0)
    especie_agg["pct_valor_especie_A"] = especie_agg.apply(lambda r: _safe_div(r["sA"], r["valor_total"]) * 100, axis=1)
    especie_agg["pct_valor_especie_B"] = especie_agg.apply(lambda r: _safe_div(r["sB"], r["valor_total"]) * 100, axis=1)

    # CONSOLIDAÇÃO FINAL
    flags_agg = df_local.groupby("cpfCnpjEnvolvido").agg(flag_pep=("bitPepCitado", "max"), flag_pessoa_obrigada=("bitPessoaObrigadaCitado", "max"), flag_servidor=("intServidorCitado", "max")).reset_index()
    result = base_agg.merge(frac_merged[["cpfCnpjEnvolvido", "dias_com_3plus", "pct_ops_proximas_limite_50k"]], on="cpfCnpjEnvolvido", how="left") \
                     .merge(conc_agg, on="cpfCnpjEnvolvido", how="left") \
                     .merge(especie_agg[["cpfCnpjEnvolvido", "pct_valor_especie_A", "pct_valor_especie_B"]], on="cpfCnpjEnvolvido", how="left") \
                     .merge(flags_agg, on="cpfCnpjEnvolvido", how="left") \
                     .rename(columns={"dias_com_3plus": "fracionamento_dias_com_3+_ops"}).fillna(0)

    return result.sort_values("valor_total", ascending=False).reset_index(drop=True)

# --------------------------------------------------------------------------------------
# Indicadores por comunicação (Indexador_x)
# --------------------------------------------------------------------------------------

def calc_indicadores_comunicacao(df: pd.DataFrame, valor_col: str = "ValorTotal") -> pd.DataFrame:
    if df is None or df.empty or "Indexador_x" not in df.columns:
        return pd.DataFrame(columns=["Indexador_x", "n_envolvidos", "valor_total", "pct_valor_especie_A", "pct_valor_especie_B"])

    df_local = df.copy()
    df_local[valor_col] = pd.to_numeric(df_local[valor_col], errors="coerce").fillna(0.0)
    
    for flag in ["bitPepCitado", "bitPessoaObrigadaCitado", "intServidorCitado"]:
        if flag in df_local.columns:
            df_local[flag] = df_local[flag].fillna(False).apply(lambda x: True if str(x).strip().lower() == "sim" else bool(x))

    base = df_local.groupby("Indexador_x").agg(
        n_envolvidos=("cpfCnpjEnvolvido", "nunique"),
        valor_total=(valor_col, "max"), 
        flag_pep_na_com=("bitPepCitado", "max") if "bitPepCitado" in df_local.columns else ("Indexador_x", "max"),
        flag_pessoa_obrigada_na_com=("bitPessoaObrigadaCitado", "max") if "bitPessoaObrigadaCitado" in df_local.columns else ("Indexador_x", "max"),
        flag_servidor_na_com=("intServidorCitado", "max") if "intServidorCitado" in df_local.columns else ("Indexador_x", "max")
    ).reset_index()

    segmentos_especie = {"19", "23", "15", "46", "48", "49", "51", "52"}
    df_local["CodigoSegmento_str"] = df_local["CodigoSegmento"].astype(str) if "CodigoSegmento" in df_local.columns else ""
    
    col_A = "ValorCampoA" if "ValorCampoA" in df_local.columns else None
    col_B = "ValorCampoB" if "ValorCampoB" in df_local.columns else None

    if col_A or col_B:
        agg_map = {}
        if col_A: agg_map["vA"] = (col_A, "max")
        if col_B: agg_map["vB"] = (col_B, "max")
        especie_agg = df_local[df_local["CodigoSegmento_str"].isin(segmentos_especie)].groupby("Indexador_x").agg(**agg_map).reset_index()
    else:
        especie_agg = pd.DataFrame(columns=["Indexador_x"])

    result = base.merge(especie_agg, on="Indexador_x", how="left").fillna(0)
    result["pct_valor_especie_A"] = result.apply(lambda r: _safe_div(r.get("vA", 0), r["valor_total"]) * 100, axis=1)
    result["pct_valor_especie_B"] = result.apply(lambda r: _safe_div(r.get("vB", 0), r["valor_total"]) * 100, axis=1)

    return result.sort_values("valor_total", ascending=False).reset_index(drop=True)

# --------------------------------------------------------------------------------------
# Indicadores por par de contrapartes
# --------------------------------------------------------------------------------------

def calc_indicadores_pares(df: pd.DataFrame, valor_col: str = "ValorTotal") -> pd.DataFrame:
    if df is None or df.empty or "Indexador_x" not in df.columns:
        return pd.DataFrame(columns=["cpf_origem", "cpf_contraparte", "valor_total_par", "n_comunicacoes_compartilhadas"])

    df_local = df.copy()
    df_local[valor_col] = pd.to_numeric(df_local[valor_col], errors="coerce").fillna(0.0)

    df_contra = df_local.dropna(subset=["cpfCnpjEnvolvido", "Indexador_x"]).groupby(["Indexador_x", "cpfCnpjEnvolvido"])[valor_col].max().reset_index()
    df_pairs = df_contra.merge(df_contra, on="Indexador_x", suffixes=("_orig", "_contra")).query("cpfCnpjEnvolvido_orig != cpfCnpjEnvolvido_contra")

    pares_agg = (
        df_pairs.groupby(["cpfCnpjEnvolvido_orig", "cpfCnpjEnvolvido_contra"])
        .agg(valor_total_par=(f"{valor_col}_contra", "sum"), n_comunicacoes_compartilhadas=("Indexador_x", "nunique"))
        .reset_index()
        .rename(columns={"cpfCnpjEnvolvido_orig": "cpf_origem", "cpfCnpjEnvolvido_contra": "cpf_contraparte"})
    )

    return pares_agg.sort_values("valor_total_par", ascending=False).reset_index(drop=True)