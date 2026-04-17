"""
공통 집계 모듈 — report_builder(Word)와 excel_builder(Excel)가 동일한 수치를 사용하도록 보장.

입력: ProcessedData의 df_merged, df_line_listing (joiner.join_tables + build_line_listing 결과)
출력: 주요 집계 수치 dict (모든 하위 모듈이 참조)
"""
import pandas as pd


def compute_aggregates(df_merged: pd.DataFrame, df_line_listing: pd.DataFrame) -> dict:
    """
    두 파이프라인이 공유할 단일 집계 dict 반환.
    모든 수치는 df_merged(이상사례 행 단위), df_line_listing(리포트용)에서 유도.
    """
    n_events = len(df_line_listing)
    n_cases = int(df_merged["KAERS_NO"].nunique()) if len(df_merged) > 0 else 0

    # ── 성별 (사례 단위) ──────────────────────────────────
    if len(df_merged) > 0 and "PTNT_SEX_NM" in df_merged.columns:
        sex_counts = df_merged.drop_duplicates("KAERS_NO")["PTNT_SEX_NM"].value_counts()
    else:
        sex_counts = pd.Series(dtype=int)
    male   = int(sex_counts.get("남", 0))
    female = int(sex_counts.get("여", 0))

    # ── 연령대 (사례 단위) ────────────────────────────────
    if len(df_merged) > 0 and "PTNT_AGRDE_NM" in df_merged.columns:
        age_counts = df_merged.drop_duplicates("KAERS_NO")["PTNT_AGRDE_NM"].value_counts()
    else:
        age_counts = pd.Series(dtype=int)

    # ── 보고유형 × 신속/일반 교차표 ───────────────────────
    if len(df_merged) > 0 and "RPT_TY_NM" in df_merged.columns:
        demo_unique = df_merged.drop_duplicates("KAERS_NO").copy()
        demo_unique["_QCK"] = demo_unique.get("IS_QUICK", False).map(
            {True: "신속보고", False: "일반보고"}
        )
        rpt_cross = pd.crosstab(
            demo_unique["RPT_TY_NM"].fillna("모름"),
            demo_unique["_QCK"].fillna("일반보고"),
        ).fillna(0).astype(int)
        n_quick = int(demo_unique.get("IS_QUICK", pd.Series(dtype=bool)).sum())
    else:
        rpt_cross = pd.DataFrame()
        n_quick = 0

    # ── 중대성 ────────────────────────────────────────────
    if "중대성" in df_line_listing.columns:
        n_serious = int(df_line_listing["중대성"].eq("Y").sum())
    elif "IS_SERIOUS" in df_merged.columns:
        n_serious = int(df_merged["IS_SERIOUS"].sum())
    else:
        n_serious = 0
    n_non_serious = n_events - n_serious

    # ── SOC × PT 요약 ─────────────────────────────────────
    if len(df_merged) > 0 and "SOC_NM" in df_merged.columns:
        soc_pt = (
            df_merged.groupby(["SOC_NM", "ADR_MEDDRA_KOR_NM"])
            .agg(
                전체건수=("ADR_MEDDRA_KOR_NM", "count"),
                중대성건수=("IS_SERIOUS", "sum"),
            )
            .reset_index()
        )
        soc_pt["비율"] = soc_pt["전체건수"].apply(
            lambda n: f"{n/n_events*100:.1f}%" if n_events else "0.0%"
        )
        soc_summary = df_merged["SOC_NM"].value_counts().rename_axis("SOC_NM").reset_index(name="건수")
        pt_summary = df_merged["ADR_MEDDRA_KOR_NM"].value_counts().rename_axis("PT").reset_index(name="건수")
    else:
        soc_pt = pd.DataFrame()
        soc_summary = pd.DataFrame()
        pt_summary = pd.DataFrame()

    # ── 상위 3 이상사례 ───────────────────────────────────
    if len(df_merged) > 0 and "ADR_MEDDRA_KOR_NM" in df_merged.columns:
        top3 = df_merged["ADR_MEDDRA_KOR_NM"].value_counts().head(3)
    else:
        top3 = pd.Series(dtype=int)

    # ── 인과성 평가 ───────────────────────────────────────
    if "EVALT_RESULT_NM" in df_merged.columns:
        evalt_counts = df_merged["EVALT_RESULT_NM"].value_counts()
    else:
        evalt_counts = pd.Series(dtype=int)

    return dict(
        n_cases=n_cases,
        n_events=n_events,
        male=male,
        female=female,
        age_counts=age_counts,
        rpt_cross=rpt_cross,
        n_serious=n_serious,
        n_non_serious=n_non_serious,
        soc_pt=soc_pt,
        soc_summary=soc_summary,
        pt_summary=pt_summary,
        top3=top3,
        n_quick=n_quick,
        evalt_counts=evalt_counts,
    )
