# 의약품 품목 갱신 - 안전관리책임자 작성 자료 자동화 에이전트 설계서

**작성일:** 2026년 4월 17일
**목적:** 한국의약품안전관리원(KIDS) 원시자료를 분석하여 식약처 품목 갱신 가이드라인에 부합하는 안전관리책임자 보고서(요약표 및 Line Listing)를 자동 생성한다.

## 1. 아키텍처 및 데이터 흐름 (Data Flow)
1. **Ingestion (데이터 입력):** KIDS 원시자료(txt/csv, `|` 구분자) 및 분석 대상 기간 입력.
2. **Strict Validation (엄격한 검증):** 파일 인코딩 확인, 필수 컬럼(KAERS_NO 등) 누락 및 기간 외 데이터 혼입 여부 검사. (오류 시 즉시 실행 차단)
3. **Processing & Join (전처리 및 병합):**
   - 코드집 기반 텍스트 변환 (성별, 연령, 제형, 투여경로 등)
   - `REPRT_CHANGE_CD = 1` (무효화/삭제 건) 원천 제외
   - `KAERS_NO` 기준 Left Join (DEMO, DRUG, EVENT 테이블)
4. **Output Generation (문서 조립):** 가이드라인 표준 목차에 맞춘 Word(`.docx`) 문서 자동 생성. (사내 필요 데이터는 하이라이트 빈칸 처리)

## 2. 핵심 데이터 처리 기준 (Business Logic)
- **문서 양식:** 식약처 가이드라인(99~115p) 표준 워드 양식 기반 생성. (자사 템플릿 미사용)
- **외부/내부 데이터 분리:** 연간 판매량(환자 노출), 전 세계 허가 현황 등 자사 데이터 필요 영역은 노란색 하이라이트 Placeholder(`[이곳에 연간 판매량을 입력하세요]`)로 처리.
- **의심약물 필터링 기준:** **가장 보수적인 전체 포함 모드** 적용. 자사 품목이 '의심약물(Suspect)', '상호작용(Interacting)', '병용약물(Concomitant)'로 투여된 모든 이상사례 건을 통계에 포함.

## 3. 예외 처리 및 품질 검증 (Error Handling & QA)
- **미확인 코드 처리:** 코드집 엑셀에 없는 신규 코드는 `[미확인코드: M999]` 형태로 문서 내 붉은색 표기 후 진행.
- **고아 데이터(Orphan Data):** 테이블 병합 시 매칭되지 않는 잉여 데이터는 버리지 않고 상세 경고 로그로 출력.
- **통계 무결성 (Reconciliation):** 전처리 후의 DataFrame 총 건수와 최종 Word 문서 표에 기재된 총 행의 수가 단 1건이라도 다를 경우, 문서 첫 장에 에러 경고문 삽입.

## 4. 테스트 전략 (Testing Strategy)
- **Unit Testing:** 무효화 건 필터링 로직 및 코드 변환 로직 검증.
- **Historical Reconciliation (과거 데이터 교차 검증):** 과거 식약처 승인을 받은 수작업 갱신 보고서의 요약표 수치와 에이전트 산출 수치가 100% 일치하는지 검증.
- **UAT (사용자 수용 테스트):** 실무자가 직접 원시자료 업로드 후 Word 파일의 표 양식 보존 상태 및 Placeholder 직관성 검토.

pv-report-agent/
│
├── data/
│   ├── raw/                 # KIDS 원시자료 txt 파일 보관 (DEMO, DRUG, EVENT 등)
│   ├── codebook/            # [붙임 2] 의약품부작용보고원시자료 코드집.xlsx 보관
│   └── output/              # 최종 생성된 Word (.docx) 보고서 출력
│
├── docs/
│   └── plans/               # 설계 문서 및 요구사항 명세서 보관
│       └── 2026-04-17-pv-report-agent-design.md
│
├── src/
│   ├── __init__.py
│   ├── validator.py         # 데이터 정합성 검증 및 에러 차단 모듈
│   ├── transformer.py       # 코드 텍스트 변환 및 무효 데이터 전처리 모듈
│   ├── joiner.py            # 데이터프레임 병합 및 보수적 의심약물 필터링 모듈
│   └── report_builder.py    # python-docx 활용 표준 워드 문서 생성 모듈
│
├── tests/
│   ├── __init__.py
│   ├── test_transformer.py  # 단위 테스트 파일
│   └── test_reconciliation.py # 과거 데이터 교차 검증 스크립트
│
├── requirements.txt         # 필요 라이브러리 목록
└── main.py                  # 전체 파이프라인 실행 엔트리포인트

pandas==2.2.0        # 원시자료 데이터프레임 병합 및 피벗(요약표) 생성
numpy==1.26.3        # 데이터 결측치 처리 및 연산
python-docx==1.1.0   # 식약처 가이드라인 표준 워드 문서 생성 및 표 삽입
openpyxl==3.1.2      # 코드집 엑셀(xlsx) 파일 파싱
pytest==8.0.0        # 테스트 코드 작성 및 실행

Product Requirements Document (PRD): PV Report Automation Agent
1. Project Overview
Objective: Develop a Streamlit-based web application that automates the creation of Pharmacovigilance (PV) renewal reports. The app will ingest raw KIDS (Korea Institute of Drug Safety) data, process it according to strict business rules, and generate a standardized Word (.docx) report.
Target User: Pharmacovigilance Managers (의약품안전관리책임자)
Design Principle: Strict validation, zero-tolerance for data manipulation errors, and highly conservative drug filtering.

2. Tech Stack
Frontend/UI: Streamlit

Data Processing: Pandas, Numpy

Document Generation: Python-docx

Data Ingestion: Openpyxl (for Excel codebook)

Testing: Pytest

3. Directory Structure
Plaintext
pv-report-agent/
├── data/
│   ├── raw/
│   ├── codebook/
│   └── output/
├── src/
│   ├── app.py (Streamlit Entrypoint)
│   ├── validator.py
│   ├── transformer.py
│   ├── joiner.py
│   └── report_builder.py
├── tests/
└── requirements.txt
4. UI/UX Flow (Streamlit)
Sidebar: File uploaders for KIDS raw data files (DEMO.txt, DRUG.txt, EVENT.txt - pipe | separated) and the Codebook Excel file.

Main Area: Date range selector for the target analysis period (e.g., 2018-01-01 to 2022-12-31).

Action Button: "Generate PV Report" button to trigger the pipeline.

Progress Indicator: Streamlit progress bar (st.progress) and status text updating during Validation, Processing, and Document Generation phases.

Output: A prominent Download Button (st.download_button) for the generated .docx file, alongside an expandable log section showing any warnings or parsed code details.

5. Core Business Logic & Processing
Data Ingestion & Validation Gate:

Files must be read with proper encoding handling (fallback between EUC-KR and UTF-8).

Strict Validation: If mandatory columns (e.g., KAERS_NO) are missing, or if rows contain dates outside the selected range, the app must st.error and immediately halt execution.

Transformation & Code Mapping:

Map raw codes to readable text using the uploaded Excel codebook (e.g., Gender, Age Group, Dosage Form).

CRITICAL: Filter out all records where REPRT_CHANGE_CD == 1 (Invalidated/Deleted reports) before any statistical processing.

Join & Filtering (Conservative Mode):

Left join DEMO, DRUG, and EVENT tables using KAERS_NO as the primary key.

CRITICAL: Include ALL cases where the company's product is listed. Do not filter only by "Suspect Drug" (의심약물). Include "Interacting" (상호작용) and "Concomitant" (병용약물) to ensure the most conservative and comprehensive safety reporting.

Document Generation:

Generate a standard Word document following the MFDS guideline structure (sections for Line Listing and Summary Tabulation by SOC/PT).

Placeholder Creation: Insert text like [이곳에 연간 판매량을 입력하세요] with a Yellow Highlight for sections requiring internal company data (e.g., Patient Exposure, Global Approval Status).

6. Error Handling & Quality Assurance
Unknown Codes: If a code is not found in the codebook, do not fail. Render it in the Word document as [미확인코드: M999] with Red Text color so the user can manually verify.

Orphan Data Check: Log a warning in the Streamlit UI if KAERS_NO records exist in DRUG or EVENT but not in DEMO.

Reconciliation Check: Assert that the final row count in the generated Line Listing table exactly matches the length of the fully processed DataFrame. If it mismatches, insert a bold red warning at the top of the Word document.