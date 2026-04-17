"""CLI 실행기 — 테스트 데이터로 보고서 생성"""
import argparse
from pathlib import Path
from src.validator import load_and_validate
from src.transformer import filter_invalid, transform_demo, transform_drug, transform_event, transform_assessment
from src.joiner import detect_drug_code, join_tables, build_line_listing
from src.report_builder import build_report
from src.types import ProcessedData

BASE = Path(__file__).parent.parent / "docs" / "files"
CODEBOOK = Path(__file__).parent.parent / "[붙임 2] 의약품부작용보고원시자료 코드집.xlsx"


def run(
    demo_path: Path,
    drug_path: Path,
    event_path: Path,
    assessment_path: Path | None,
    start_date: str,
    end_date: str,
    drug_code: str,
    drug_name: str,
    company_name: str,
    output_path: Path,
):
    print("[1/4] 파일 검증 중...")
    demo_df, drug_df, event_df, assessment_df, warnings = load_and_validate(
        demo_path, drug_path, event_path, assessment_path, start_date, end_date,
    )

    print("[2/4] 코드 변환 중...")
    unknown_codes: list[dict] = []
    demo_df, removed = filter_invalid(demo_df)
    if removed:
        print(f"  REPRT_CHANGE_CD=1 무효 건 {removed}건 제거")
    demo_df = transform_demo(demo_df, unknown_codes)
    drug_df = transform_drug(drug_df, unknown_codes)
    event_df = transform_event(event_df, unknown_codes)
    if assessment_df is not None:
        assessment_df = transform_assessment(assessment_df, unknown_codes)

    if not drug_code:
        drug_code = detect_drug_code(drug_df)
        print(f"  자동 감지된 의약품 코드: {drug_code}")

    print("[3/4] 데이터 병합 중...")
    merged_df = join_tables(demo_df, drug_df, event_df, assessment_df, drug_code, warnings)
    ll_df = build_line_listing(merged_df)
    n_cases = merged_df["KAERS_NO"].nunique() if len(merged_df) > 0 else 0
    print(f"  유효 이상사례: {len(ll_df)}건 / 사례: {n_cases}건")

    if warnings:
        print("  경고:")
        for w in warnings:
            print(f"    - {w}")
    if unknown_codes:
        print(f"  미확인 코드 {len(unknown_codes)}건")

    print("[4/4] Word 문서 생성 중...")
    data = ProcessedData(
        df_merged=merged_df,
        df_line_listing=ll_df,
        total_cases=n_cases,
        warnings=warnings,
        unknown_codes=unknown_codes,
        analysis_period=(start_date, end_date),
        drug_name=drug_name or drug_code,
        drug_code=drug_code,
        company_name=company_name,
        has_assessment=assessment_df is not None,
    )
    docx_bytes = build_report(data)
    output_path.write_bytes(docx_bytes)
    print(f"✅ 완료: {output_path}")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PV 보고서 자동 생성 CLI")
    parser.add_argument("--demo", default=str(BASE / "DEMO.txt"))
    parser.add_argument("--drug", default=str(BASE / "DRUG.txt"))
    parser.add_argument("--event", default=str(BASE / "EVENT.txt"))
    parser.add_argument("--assessment", default=str(BASE / "ASSESSMENT.txt"))
    parser.add_argument("--start", default="20200921")
    parser.add_argument("--end", default="20240630")
    parser.add_argument("--drug-code", default="")
    parser.add_argument("--drug-name", default="프로테조밉주")
    parser.add_argument("--company", default="㈜삼양홀딩스")
    parser.add_argument("--output", default="data/output/generated_report.docx")
    args = parser.parse_args()

    Path("data/output").mkdir(parents=True, exist_ok=True)
    run(
        Path(args.demo), Path(args.drug), Path(args.event),
        Path(args.assessment) if Path(args.assessment).exists() else None,
        args.start, args.end, args.drug_code, args.drug_name, args.company,
        Path(args.output),
    )
