"""CLI 래퍼 — src/excel_builder.build_excel() 호출"""
import argparse
from pathlib import Path
from src.excel_builder import build_excel, _DEFAULT_BASE, _DEFAULT_DRUG_CODE, _DEFAULT_DRUG_NAME

parser = argparse.ArgumentParser(description="KIDS 원시자료 → 분석 엑셀 생성")
parser.add_argument("--files-dir", default=str(_DEFAULT_BASE), help="원시자료 txt 파일 디렉토리")
parser.add_argument("--drug-code", default=_DEFAULT_DRUG_CODE, help="의약품 품목기준코드")
parser.add_argument("--drug-name", default=_DEFAULT_DRUG_NAME, help="제품명")
parser.add_argument("--output", default="data/output/원시자료분석.xlsx", help="출력 파일 경로")
args = parser.parse_args()

out = Path(args.output)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(build_excel(args.files_dir, args.drug_code, args.drug_name))
print(f"✅ 완료: {out}")
