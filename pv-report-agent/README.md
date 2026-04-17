# PV Report Agent

의약품 안전관리책임자 보고서 자동 생성 에이전트.
KIDS 원시자료(DEMO/DRUG/EVENT/ASSESSMENT)를 업로드하면
식약처 품목갱신 가이드라인 기반 Word 보고서 초안과 원시자료 분석 엑셀을 동시에 생성합니다.

## 주요 기능

- **ZIP 업로드** + **nedrug.mfds.go.kr URL 자동 스크래핑** 으로 시작
- **8시트 분석 엑셀**: 요약통계 / Word 연동 수치 / 분석테이블 / Line Listing / DEMO / DRUG / EVENT / ASSESSMENT / 코드참조
- **Word 보고서 초안**: 식약처 가이드라인 구조(99~115p) 기반, 노란색 사용자 입력란 + `[검토필요:]` 마커 자동 삽입
- **공유 집계 모듈**(`aggregator.py`)로 엑셀과 Word 수치 일관성 보장
- 수작업 보고서와 **8/8 핵심 수치 100% 일치** 검증 (`compare.py`)

## 로컬 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

## CLI 사용

```bash
# Word 보고서 생성
python main.py --drug-name "프로테조밉주3.5mg" --company "㈜삼양홀딩스" \
               --drug-code 201506668 --output report.docx

# 원시자료 분석 엑셀만 생성
python make_excel.py --files-dir ../docs/files --drug-code 201506668 \
                     --drug-name 프로테조밉주3.5mg --output analysis.xlsx
```

## Streamlit Cloud 배포

1. https://share.streamlit.io 접속
2. GitHub repo `Lucy1315/pharma_revision` 연결
3. **Main file path**: `pv-report-agent/app.py`
4. **Python version**: 3.10 이상
5. Deploy 클릭

> **보안 주의:** KIDS 원시자료는 민감 데이터입니다. 공개 배포 시 업로드 파일은
> 서버에 영구 저장되지 않지만, 사내 정책에 따라 Docker 사내 호스팅이 더 안전할 수 있습니다.

## 테스트

```bash
pip install -r requirements-dev.txt
pytest                      # 43개 단위 테스트
python compare.py           # 수작업 보고서와 수치 회귀 검증
```

## 디렉토리

```
pv-report-agent/
├── app.py                  ← Streamlit 엔트리포인트
├── main.py                 ← Word 보고서 CLI
├── make_excel.py           ← 엑셀 분석 CLI
├── compare.py              ← 회귀 검증
├── src/
│   ├── validator.py        ← 파일 검증/인코딩
│   ├── transformer.py      ← 코드→텍스트 매핑
│   ├── joiner.py           ← 테이블 병합
│   ├── aggregator.py       ← 공유 집계 (Word/Excel 일관성)
│   ├── report_builder.py   ← Word 생성
│   ├── excel_builder.py    ← 엑셀 생성
│   └── product_scraper.py  ← nedrug URL 파싱
└── tests/                  ← pytest 43개
```

자세한 도메인 규칙은 [`CLAUDE.md`](./CLAUDE.md) 참조.
