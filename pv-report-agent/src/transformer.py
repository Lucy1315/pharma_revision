import pandas as pd
import openpyxl
from pathlib import Path


# ── 공통코드 매핑 ──────────────────────────────────────────
PTNT_SEX_MAP = {"1": "남", "2": "여"}
PTNT_AGRDE_MAP = {
    "0": "태아", "1": "출생~28일", "2": "28일~24개월",
    "3": "24개월~12세", "4": "12~19세", "5": "19~65세", "6": "65세이상",
}
ADR_RESULT_MAP = {
    "1": "회복됨", "2": "회복중", "3": "회복안됨",
    "4": "후유증", "5": "치명적", "0": "알려지지않음",
}
DRUG_GB_MAP = {"1": "의심", "2": "병용", "3": "상호작용", "4": "비투여"}
DRUG_ACTION_MAP = {
    "1": "투여중지", "2": "투여량감소", "3": "투여량증가",
    "4": "투여량유지", "0": "모름", "9": "해당없음",
}
EVALT_RESULT_MAP = {
    "1": "확실함", "2": "상당히확실함", "3": "가능함",
    "4": "가능성적음", "5": "평가곤란", "6": "평가불가",
}
RPT_TY_MAP = {"1": "자발적보고", "2": "시험/연구에서보고", "3": "기타", "4": "모름"}

# ── WHOART SOC 매핑 (하드코딩) ────────────────────────────
WHOART_SOC_MAP = {
    "01": "피부 및 피하조직 장애",
    "02": "근골격계 및 결합조직 장애",
    "03": "위장관계 장애",
    "04": "중추/말초신경계 장애",
    "05": "자율신경계 장애",
    "06": "시각 장애",
    "07": "청각 및 전정 장애",
    "08": "심장 장애",
    "09": "혈관계 장애",
    "10": "호흡기계, 흉곽 및 종격 장애",
    "11": "적혈구 계통 장애",
    "12": "혈소판/출혈/응고 장애",
    "13": "혈액 및 림프계 장애",
    "14": "간담도계 장애",
    "15": "대사 및 영양 장애",
    "16": "내분비 장애",
    "17": "비뇨기계 장애",
    "18": "생식기(여성) 장애",
    "19": "생식기(남성) 장애",
    "20": "신생아 및 영아 장애",
    "21": "전신계 장애",
    "22": "신생물",
    "23": "감염 및 기생충 침입",
    "24": "손상",
    "25": "선천성 장애",
    "26": "신생물 양성",
    "27": "심리적 장애",
    "28": "임신, 출산 및 주산기 상태",
    "29": "면역계 장애",
    "30": "신체 검사 결과 이상",
    "31": "의료 및 외과적 시술",
    "32": "사회 환경",
    "99": "기타",
}


def _map_code(val: str | None, mapping: dict, col_name: str, unknown_codes: list) -> str:
    if val is None or str(val).strip() == "" or str(val).strip().lower() == "nan":
        return ""
    key = str(val).strip()
    if key in mapping:
        return mapping[key]
    marker = f"[미확인코드: {key}]"
    unknown_codes.append({"col": col_name, "code": key})
    return marker


def map_soc(whoart_arrn: str | None) -> str:
    if not whoart_arrn or str(whoart_arrn).strip() in ("", "nan"):
        return "기타"
    code = str(whoart_arrn).strip()
    prefix = code[:2].zfill(2)
    return WHOART_SOC_MAP.get(prefix, f"[미확인코드: {whoart_arrn}]")


def format_date(val: str | None) -> str:
    if not val or str(val).strip() in ("", "nan"):
        return "모름"
    s = str(val).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s


def filter_invalid(demo_df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    before = len(demo_df)
    df = demo_df[demo_df["REPRT_CHANGE_CD"].astype(str).str.strip() != "1"].copy()
    removed = before - len(df)
    return df, removed


def transform_demo(demo_df: pd.DataFrame, unknown_codes: list) -> pd.DataFrame:
    df = demo_df.copy()
    df["PTNT_SEX_NM"] = df["PTNT_SEX"].apply(
        lambda v: _map_code(v, PTNT_SEX_MAP, "PTNT_SEX", unknown_codes)
    )
    df["PTNT_AGRDE_NM"] = df["PTNT_AGRDE"].apply(
        lambda v: _map_code(v, PTNT_AGRDE_MAP, "PTNT_AGRDE", unknown_codes)
    )
    df["RPT_TY_NM"] = df["RPT_TY"].apply(
        lambda v: _map_code(v, RPT_TY_MAP, "RPT_TY", unknown_codes)
    )
    df["IS_QUICK"] = df.get("QCK_RPT_YN", pd.Series(dtype=str)).astype(str).str.strip().eq("Y")
    df["RPT_DL_DT_FMT"] = df["RPT_DL_DT"].apply(format_date)
    df["FIRST_OCCR_DT_FMT"] = df.get("FIRST_OCCR_DT", pd.Series(dtype=str)).apply(format_date)
    return df


def transform_drug(drug_df: pd.DataFrame, unknown_codes: list) -> pd.DataFrame:
    df = drug_df.copy()
    df["DRUG_GB_NM"] = df["DRUG_GB"].apply(
        lambda v: _map_code(v, DRUG_GB_MAP, "DRUG_GB", unknown_codes)
    )
    df["DRUG_ACTION_NM"] = df.get("DRUG_ACTION", pd.Series(dtype=str)).apply(
        lambda v: _map_code(v, DRUG_ACTION_MAP, "DRUG_ACTION", unknown_codes)
    )
    return df


def transform_event(event_df: pd.DataFrame, unknown_codes: list) -> pd.DataFrame:
    df = event_df.copy()
    df["ADR_RESULT_NM"] = df["ADR_RESULT_CODE"].apply(
        lambda v: _map_code(v, ADR_RESULT_MAP, "ADR_RESULT_CODE", unknown_codes)
    )
    df["SOC_NM"] = df.get("WHOART_ARRN", pd.Series(dtype=str)).apply(map_soc)
    df["ADR_START_DT_FMT"] = df.get("ADR_START_DT", pd.Series(dtype=str)).apply(format_date)
    df["ADR_END_DT_FMT"] = df.get("ADR_END_DT", pd.Series(dtype=str)).apply(format_date)

    SE_COLS = [
        "SE_DEATH", "SE_LIFE_MENACE", "SE_HSPTLZ_EXTN",
        "SE_FNCT_DGRD", "SE_ANMLY", "SE_ETC_IMPRTNC_SITTN",
    ]
    present_se = [c for c in SE_COLS if c in df.columns]
    df["IS_SERIOUS"] = df[present_se].eq("Y").any(axis=1) if present_se else False

    def seriousness_label(row) -> str:
        labels = []
        mapping = {
            "SE_DEATH": "사망", "SE_LIFE_MENACE": "생명위협",
            "SE_HSPTLZ_EXTN": "입원", "SE_FNCT_DGRD": "기능저하",
            "SE_ANMLY": "선천기형", "SE_ETC_IMPRTNC_SITTN": "기타중요",
        }
        for col, label in mapping.items():
            if col in row and str(row[col]).strip() == "Y":
                labels.append(label)
        return "/".join(labels) if labels else ""

    df["SERIOUSNESS_CRITERIA"] = df.apply(seriousness_label, axis=1)
    return df


def transform_assessment(assessment_df: pd.DataFrame, unknown_codes: list) -> pd.DataFrame:
    df = assessment_df.copy()
    df["EVALT_RESULT_NM"] = df["EVALT_RESULT_CODE"].apply(
        lambda v: _map_code(v, EVALT_RESULT_MAP, "EVALT_RESULT_CODE", unknown_codes)
    )
    return df
