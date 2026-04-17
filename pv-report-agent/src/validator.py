import pandas as pd
from pathlib import Path


class ValidationError(Exception):
    pass


REQUIRED_COLUMNS = {
    "DEMO": ["KAERS_NO", "REPRT_CHANGE_CD", "RPT_DL_DT"],
    "DRUG": ["KAERS_NO", "DRUG_SEQ", "DRUG_GB", "DRUG_CD"],
    "EVENT": ["KAERS_NO", "ADR_SEQ", "ADR_MEDDRA_KOR_NM", "ADR_MEDDRA_ENG_NM"],
    "ASSESSMENT": ["KAERS_NO", "DRUG_SEQ", "ADR_SEQ", "EVALT_RESULT_CODE"],
}


def read_file(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    for enc in ("utf-8-sig", "euc-kr", "utf-8"):
        try:
            df = pd.read_csv(path, sep="|", encoding=enc, dtype=str, low_memory=False)
            return df
        except (UnicodeDecodeError, Exception):
            continue
    raise ValidationError(f"파일 인코딩 감지 실패: {path.name}")


def validate_columns(df: pd.DataFrame, file_type: str) -> None:
    required = REQUIRED_COLUMNS.get(file_type, [])
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValidationError(f"{file_type}.txt 필수 컬럼 누락: {missing}")


def validate_date_range(
    df: pd.DataFrame,
    date_col: str,
    start_date: str,
    end_date: str,
    file_type: str,
) -> list[str]:
    warnings = []
    if date_col not in df.columns:
        return warnings
    col = pd.to_datetime(df[date_col], format="%Y%m%d", errors="coerce")
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    out_of_range = ((col < start) | (col > end)) & col.notna()
    count = out_of_range.sum()
    if count > 0:
        warnings.append(f"{file_type}: {date_col} 기준 기간 외 데이터 {count}건 포함 (참고용)")
    return warnings


def load_and_validate(
    demo_path: str | Path,
    drug_path: str | Path,
    event_path: str | Path,
    assessment_path: str | Path | None,
    start_date: str,
    end_date: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame | None, list[str]]:
    warnings: list[str] = []

    demo_df = read_file(demo_path)
    drug_df = read_file(drug_path)
    event_df = read_file(event_path)

    validate_columns(demo_df, "DEMO")
    validate_columns(drug_df, "DRUG")
    validate_columns(event_df, "EVENT")

    warnings += validate_date_range(demo_df, "RPT_DL_DT", start_date, end_date, "DEMO")

    assessment_df = None
    if assessment_path and Path(assessment_path).exists():
        assessment_df = read_file(assessment_path)
        validate_columns(assessment_df, "ASSESSMENT")
    else:
        warnings.append("ASSESSMENT.txt 미제공 — 인과성 평가 컬럼이 비어 있습니다.")

    return demo_df, drug_df, event_df, assessment_df, warnings
