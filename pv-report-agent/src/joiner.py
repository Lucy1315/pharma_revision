import pandas as pd


def detect_drug_code(drug_df: pd.DataFrame) -> str:
    if "DRUG_CD" not in drug_df.columns:
        return ""
    counts = drug_df["DRUG_CD"].astype(str).str.strip().value_counts()
    return counts.index[0] if len(counts) > 0 else ""


def filter_target_drug(drug_df: pd.DataFrame, drug_code: str) -> pd.DataFrame:
    df = drug_df[
        (drug_df["DRUG_CD"].astype(str).str.strip() == str(drug_code).strip()) &
        (drug_df["DRUG_GB"].astype(str).str.strip().isin(["1", "2", "3"]))
    ].copy()
    return df


def _merge_assessment(
    event_df: pd.DataFrame,
    drug_target: pd.DataFrame,
    assessment_df: pd.DataFrame | None,
    warnings: list[str],
) -> pd.DataFrame:
    if assessment_df is None:
        event_df = event_df.copy()
        event_df["EVALT_RESULT_NM"] = f"[검토필요: 인과성 평가 없음]"
        return event_df

    # 의심약물(DRUG_GB=1) 우선, 없으면 DRUG_GB 오름차순 첫 번째
    suspect_seq = drug_target[drug_target["DRUG_GB"].astype(str) == "1"][
        ["KAERS_NO", "DRUG_SEQ"]
    ].drop_duplicates("KAERS_NO")
    all_seq = drug_target[["KAERS_NO", "DRUG_SEQ"]].drop_duplicates("KAERS_NO")
    primary_seq = suspect_seq.combine_first(all_seq).drop_duplicates("KAERS_NO")

    assess = assessment_df.merge(
        primary_seq.rename(columns={"DRUG_SEQ": "TARGET_DRUG_SEQ"}),
        on="KAERS_NO", how="inner",
    )
    assess = assess[
        assess["DRUG_SEQ"].astype(str).str.strip() ==
        assess["TARGET_DRUG_SEQ"].astype(str).str.strip()
    ][["KAERS_NO", "ADR_SEQ", "EVALT_RESULT_NM"]].drop_duplicates(["KAERS_NO", "ADR_SEQ"])

    result = event_df.merge(assess, on=["KAERS_NO", "ADR_SEQ"], how="left")
    missing = result["EVALT_RESULT_NM"].isna().sum()
    if missing > 0:
        result["EVALT_RESULT_NM"] = result["EVALT_RESULT_NM"].fillna("[검토필요: 인과성 평가 없음]")
        warnings.append(f"인과성 평가 없는 이상사례 {missing}건 — [검토필요] 마커 삽입")
    return result


def join_tables(
    demo_df: pd.DataFrame,
    drug_df: pd.DataFrame,
    event_df: pd.DataFrame,
    assessment_df: pd.DataFrame | None,
    drug_code: str,
    warnings: list[str],
) -> pd.DataFrame:
    # 자사 의약품 KAERS_NO 집합 추출 (보수적: DRUG_GB 1/2/3 모두)
    drug_target = filter_target_drug(drug_df, drug_code)
    target_kaers = set(drug_target["KAERS_NO"].astype(str).str.strip())

    # DEMO를 대상 KAERS_NO로 필터
    demo_filtered = demo_df[demo_df["KAERS_NO"].astype(str).str.strip().isin(target_kaers)].copy()

    # 고아 EVENT 검출 (EVENT에 있지만 DEMO에 없는 KAERS_NO)
    event_kaers = set(event_df["KAERS_NO"].astype(str).str.strip())
    orphan = event_kaers & target_kaers - set(demo_filtered["KAERS_NO"].astype(str).str.strip())
    if orphan:
        warnings.append(f"고아 이상사례 데이터: DEMO에 없는 KAERS_NO {len(orphan)}건 — {list(orphan)[:5]}")

    # ASSESSMENT 병합
    event_with_assess = _merge_assessment(event_df, drug_target, assessment_df, warnings)

    # EVENT를 대상 KAERS_NO로 필터
    event_filtered = event_with_assess[
        event_with_assess["KAERS_NO"].astype(str).str.strip().isin(target_kaers)
    ].copy()

    # DRUG_GB_NM을 각 KAERS_NO에 대해 가져옴 (자사 약물의 구분)
    drug_gb = drug_target[["KAERS_NO", "DRUG_GB_NM", "DRUG_ACTION_NM"]].drop_duplicates("KAERS_NO")

    # DEMO × EVENT Left Join (이상사례별 1행)
    merged = event_filtered.merge(
        demo_filtered, on="KAERS_NO", how="left", suffixes=("", "_demo")
    )
    merged = merged.merge(drug_gb, on="KAERS_NO", how="left")

    return merged


def build_line_listing(merged_df: pd.DataFrame) -> pd.DataFrame:
    cols = {
        "KAERS_NO": "KAERS번호",
        "EVALT_RESULT_NM": "인과성평가",
        "ADR_MEDDRA_KOR_NM": "이상사례명(한글)",
        "ADR_MEDDRA_ENG_NM": "이상사례명(영문)",
        "ADR_START_DT_FMT": "발현일",
        "ADR_END_DT_FMT": "종료일",
        "ADR_RESULT_NM": "이상사례경과",
        "IS_SERIOUS": "중대성",
        "SERIOUSNESS_CRITERIA": "중대성기준",
        "PTNT_SEX_NM": "성별",
        "PTNT_OCCURSYMT_AGE": "나이",
        "DRUG_GB_NM": "의약품구분",
        "RPT_DL_DT_FMT": "보고일",
    }
    present = {k: v for k, v in cols.items() if k in merged_df.columns}
    df = merged_df[list(present.keys())].rename(columns=present).copy()
    df.insert(0, "번호", range(1, len(df) + 1))
    df["중대성"] = df["중대성"].apply(lambda v: "Y" if v else "N")
    return df.reset_index(drop=True)
