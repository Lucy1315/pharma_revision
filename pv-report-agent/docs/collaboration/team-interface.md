# 팀 간 인터페이스 정의서

작성일: 2026-04-17
마지막 업데이트: 2026-04-18
목적: 데이터 분석팀 · 보고서 작성팀 · 통합/배포팀 간 데이터 계약 정의

---

## 팀 역할

### 데이터 분석팀 (Data Analysis Team)
- 담당 모듈: `validator.py`, `transformer.py`, `joiner.py`
- 책임: KIDS 원시자료 검증(인코딩·스키마), 코드→텍스트 변환, 테이블 병합/필터링
- 출력: 정제된 `df_merged`, 리포트용 `df_line_listing`, `unknown_codes`, `warnings`

### 보고서 작성팀 (Report Writing Team)
- 담당 모듈: `report_builder.py`, `excel_builder.py`
- 책임: Word 문서 생성(식약처 99~115p 구조), 원시자료 분석 엑셀 생성(8~9시트)
- 입력: `ProcessedData` + `aggregator.compute_aggregates()`가 반환한 `shared_stats`
- 출력: `.docx` bytes, `.xlsx` bytes

### 통합/집계팀 (Aggregation & Integration Team)  ← **신설 2026-04-18**
- 담당 모듈: `aggregator.py`, `product_scraper.py`, `app.py`, `main.py`, `make_excel.py`, `compare.py`
- 책임:
  - **수치 일관성 보장**: `aggregator.compute_aggregates()`가 Word/Excel 공통 집계 dict 제공 — 양 파이프라인이 동일 수치 사용
  - **외부 데이터 조회**: 공공데이터포털 API + nedrug 스크래핑 fallback
  - **Streamlit UI**: 업로드 → 조회 → 기간 감지 → 생성 → 다운로드 → 수정본 보관 오케스트레이션
  - **회귀 검증**: `compare.py`로 수작업 참조 보고서와 8개 핵심 수치 1:1 매칭

---

## 데이터 계약 (Data Contract)

### ProcessedData (src/types.py)

```python
@dataclass
class ProcessedData:
    df_merged: pd.DataFrame           # 병합된 최종 DataFrame
    df_line_listing: pd.DataFrame     # Line Listing용 정렬된 DataFrame
    total_cases: int                  # 유효 이상사례 총 건수(=KAERS_NO 고유수)
    warnings: list[str]               # 경고 메시지(고아 데이터, 무효 건 제거 수 등)
    unknown_codes: list[dict]         # 미확인 코드 [{col, code, kaers_no}]
    analysis_period: tuple[str, str]  # (start_date, end_date) — "YYYY-MM-DD"
    drug_name: str                    # 분석 대상 의약품명
    drug_code: str                    # 품목기준코드 (=의약품 코드)
    company_name: str = ""            # 회사명 (표지용)
    ingredient_name: str = ""         # 성분명 (표지용)
    approval_date: str = ""           # 허가일 (표지용)
    approval_number: str = ""         # 허가번호 (표지용, 없으면 item_seq로 대체)
    has_assessment: bool = False      # ASSESSMENT.txt 제공 여부 — False면 인과성 섹션에 [검토필요:] 마커
```

### df_merged 컬럼 스펙

| 컬럼명 | 설명 | 예시 |
|--------|------|------|
| KAERS_NO | 접수번호 | 2020300248843 |
| RPT_DL_DT | 보고일 | 20201118 |
| FIRST_OCCR_DT | 발생일 | 20201109 |
| PTNT_SEX_NM | 성별(변환) | 남/여 |
| PTNT_OCCURSYMT_AGE | 나이 | 66 |
| PTNT_AGRDE_NM | 연령대(변환) | 65세이상 |
| DRUG_GB_NM | 의약품구분(변환) | 의심/병용/상호작용 |
| DRUG_ACTION_NM | 의약품 조치(변환) | 투여 중지 |
| ADR_MEDDRA_KOR_NM | 이상사례명(한글) | 말초 신경 병증 |
| ADR_MEDDRA_ENG_NM | 이상사례명(영문) | Neuropathy peripheral |
| ADR_START_DT | 이상사례 발생일 | 20201109 |
| ADR_END_DT | 이상사례 종료일 | |
| ADR_RESULT_CODE_NM | 이상사례 결과(변환) | 회복됨 |
| IS_SERIOUS | 중대한 이상사례 여부 | True/False |
| SERIOUSNESS_CRITERIA | 중대성 기준 | 사망/생명위협/입원... |
| WHOART_ARRN | WHO-ART SOC 코드 원본 | 1313 |
| SOC_NM | SOC 한글명 (앞 2자리 → domain.md 매핑) | 백혈구 및 세망내피계 장애 |
| RPT_TY_NM | 보고유형(변환) | 자발적보고/시험·연구/기타/모름 |
| IS_QUICK | 신속보고 여부 (QCK_RPT_YN=='Y') | True/False |
| EVALT_RESULT_NM | 인과성 평가(변환) | 확실함/상당히확실함/... |

### df_line_listing 컬럼 스펙 (보고서용)

| 컬럼명 | 표시명 |
|--------|-------|
| NO | 연번 |
| KAERS_NO | 접수번호 |
| RPT_DL_DT | 보고일 |
| FIRST_OCCR_DT | 최초 발생일 |
| PTNT_SEX_NM | 성별 |
| PTNT_OCCURSYMT_AGE | 나이(세) |
| DRUG_GB_NM | 의약품 구분 |
| ADR_MEDDRA_KOR_NM | 이상사례명(한글) |
| ADR_MEDDRA_ENG_NM | 이상사례명(영문) |
| ADR_START_DT | 이상사례 발생일 |
| ADR_END_DT | 이상사례 종료일 |
| ADR_RESULT_CODE_NM | 이상사례 결과 |
| IS_SERIOUS / 중대성 | 중대성 Y/N |
| SERIOUSNESS_CRITERIA | 중대성 기준 |

### shared_stats — aggregator.compute_aggregates() 출력  ← **신설 2026-04-18**

Word/Excel 양 파이프라인이 참조하는 단일 진입점. 수치 불일치 원천 차단.

```python
shared_stats: dict = {
    "n_cases":        int,           # 유효 이상사례 사례수 (KAERS_NO 고유)
    "n_events":       int,           # Line Listing 행수 = 이상사례 건수
    "male":           int,           # 남성 사례수
    "female":         int,           # 여성 사례수
    "age_counts":     pd.Series,     # 연령대별 사례수
    "rpt_cross":      pd.DataFrame,  # 보고유형 × (신속/일반) 교차표
    "n_quick":        int,           # 신속보고 건수
    "n_serious":      int,           # 중대성 Y 건수
    "n_non_serious":  int,           # n_events - n_serious
    "soc_pt":         pd.DataFrame,  # SOC × PT 전체건수/중대성건수/비율
    "soc_summary":    pd.DataFrame,  # SOC별 건수 요약
    "pt_summary":     pd.DataFrame,  # PT별 건수 요약
    "top3":           pd.Series,     # 상위 3 이상사례 (ADR_MEDDRA_KOR_NM)
    "evalt_counts":   pd.Series,     # 인과성 평가 결과별 건수
}
```

**계약 불변식**:
- `len(df_line_listing) == shared_stats["n_events"]`
- `df_merged["KAERS_NO"].nunique() == shared_stats["n_cases"]`
- `shared_stats["n_serious"] + shared_stats["n_non_serious"] == shared_stats["n_events"]`

### ProductInfo (src/product_scraper.py)  ← **신설 2026-04-18**

```python
@dataclass
class ProductInfo:
    item_name: str = ""        # 제품명
    company_name: str = ""     # 업체명
    approval_date: str = ""    # 허가일 (YYYY-MM-DD)
    item_seq: str = ""         # 품목기준코드 (= drug_code)
    atc_code: str = ""         # ATC 코드
    ingredient_name: str = ""  # 한글 성분명
    approval_number: str = ""  # 허가번호
    warnings: list[str] = []   # 조회 경고 메시지
```

**조회 경로 (우선순위)**:
1. `lookup_product_info(item_seq=...)` — 공공데이터포털 API (품목기준코드)
2. `search_drug_by_name(name=...)` — 공공데이터포털 API (제품명, 다중 결과)
3. `scrape_product_info(url=...)` — nedrug HTML 스크래핑 (fallback, 해외 IP 차단 시 실패)

---

## 출력물 계약

### Word 문서 (report_builder.build_report)

가이드라인 99~115p 기준 섹션 커버리지:

| 섹션 | 내용 | 데이터 소스 |
|------|------|-------------|
| 표지 | 회사/제품/허가일/허가번호 테이블 | ProcessedData.company_name, drug_name, approval_date, approval_number |
| 1. 요약 | 전체 집계 요약 | shared_stats.n_cases, n_events |
| 2.1 업무 절차 | 정적 텍스트 + 노란색 하이라이트 입력란 | — |
| 2.2 가. 신속보고 | 텍스트 + 건수 | shared_stats.n_quick |
| 2.2 나. 정기보고 | 텍스트 | — |
| 2.2 다. (ㄱ) 보고 건수 | 보고유형 × 신속/일반 교차표 | shared_stats.rpt_cross |
| 2.2 다. (ㄴ) 인구학적 | 성별/연령대 표 + 텍스트 | shared_stats.male/female/age_counts |
| 2.2 다. (ㄷ) 이상사례 | SOC/PT · 중대성 · Line Listing | shared_stats.soc_pt/n_serious, df_line_listing |
| 2.2 다. (ㄹ) 허가사항 비교 | 정성 텍스트 (KIDS 데이터 기반 초안) | df_merged ADR 목록 |
| 2.2 다. (ㅁ) 허가사항 외 | 정성 텍스트 초안 + `[검토필요:]` 마커 | df_merged |
| 2.2 다. (ㅂ) 검토 | 종합 검토 텍스트 + `[검토필요:]` 마커 | shared_stats |

**Placeholder 3색 규칙**:
- 🟡 노란색 하이라이트 — 사내 데이터 직접 입력 필요 (`[이곳에 연간 판매량을 입력하세요]`)
- 🔴 빨간색 텍스트 — 미확인 코드 (`[미확인코드: M999]`)
- 🔵 파란색 텍스트 — 검토 필요 (`[검토필요: 인과성 평가 없음]`)

### 분석 엑셀 (excel_builder.build_excel)

8~9 시트 구성 (ASSESSMENT 유무에 따라 가변):

| 순서 | 시트명 | 내용 | 데이터 소스 |
|------|--------|------|-------------|
| ① | 요약통계 | 사례수/건수/성별/연령대/중대성 | shared_stats |
| ② | Word연동수치 | Word 문서에 들어가는 핵심 수치 그대로 | shared_stats |
| ③ | 분석테이블 | SOC/PT 교차표 | shared_stats.soc_pt |
| ④ | LineListing | 리포트용 Line Listing | df_line_listing |
| ⑤ | DEMO | 원본 DEMO.txt 테이블 | raw |
| ⑥ | DRUG | 원본 DRUG.txt 테이블 | raw |
| ⑦ | EVENT | 원본 EVENT.txt 테이블 | raw |
| ⑧ | ASSESSMENT (선택) | 원본 ASSESSMENT.txt | raw (if has_assessment) |
| ⑨ | 코드참조 | 코드→한글 매핑 참조 | domain.md |

**엑셀 빌더 시그니처**:
```python
build_excel(files_dir: Path, drug_code: str, drug_name: str,
            shared_stats: dict | None = None) -> bytes
```
- `shared_stats=None` 이면 내부에서 재계산 (CLI 독립 실행 시)
- Streamlit 경로에서는 app.py가 `compute_aggregates()` 1회 호출 후 전달 — 재계산 비용 제거

---

## 소통 로그

팀 간 결정사항은 이 문서에 기록합니다.

### [2026-04-17] 초기 인터페이스 합의
- WHOART_ARRN을 SOC 그룹핑에 사용 (MedDRA 계층 코드 없으므로)
- REPRT_CHANGE_CD == 1 건은 transformer.py에서 완전 제거
- 미확인 코드는 문자열로 반환 (`[미확인코드: XXX]`)
- 중대성 = SE_DEATH/SE_LIFE_MENACE/SE_HSPTLZ_EXTN/SE_FNCT_DGRD/SE_ANMLY/SE_ETC_IMPRTNC_SITTN 중 하나라도 'Y'

### [2026-04-17] QA 피드백 반영
- ISSUE-001: `excel_builder._DEFAULT_BASE` 경로 오류 수정
- ISSUE-002: ASSESSMENT/DRUG1/2/3 누락 시 엑셀 생성 실패 해결 — 선택 파일 부재 시 해당 시트만 스킵

### [2026-04-18] 통합/집계팀 신설 및 데이터 계약 확장
- **`aggregator.compute_aggregates()` 도입** — Word/Excel 수치 일관성 단일 진입점. `shared_stats` dict 계약 정의.
- **`ProcessedData` 필드 확장** — company_name/ingredient_name/approval_date/approval_number/has_assessment 추가 (표지 테이블 + 인과성 분기).
- **`ProductInfo` 계약 신설** — 공공데이터포털 API + nedrug 스크래핑 공통 반환 타입.
- **3-way 제품 조회 합의** — 품목기준코드 / 제품명 검색 / nedrug URL (순서대로 우선). 해외 IP 차단 시 사용자에게 브라우저 직접 열기 링크 제공.
- **README.txt 자동 감지** — 업로드 파일셋에 README가 포함되면 품목기준코드·보고기간을 세션 상태로 선반영. 사용자 수정은 보존.
- **분석 기간 자동 감지** — DEMO.txt의 RPT_DL_DT 최소/최대값. 사용자 수정 가능.
- **(ㄹ)(ㅁ)(ㅂ) 섹션 초안 자동 생성** — KIDS 데이터 기반 SOC/PT 목록 + `[검토필요:]` 파란색 마커. 담당자가 최종 보완.
- **Line Listing 행 분리 원칙 재확인** — 1사례 × 다중 이상사례 → 이상사례별 1행 (건수 정확성).

### [2026-04-18] Streamlit Cloud 배포 합의
- 배포 URL: `https://pharmarevision.streamlit.app/`
- GitHub: `Lucy1315/pharma_revision`, Main file: `pv-report-agent/app.py`
- `runtime.txt`에 `3.11` 고정 (Heroku 스타일 `python-3.11` 아님)
- `requirements.txt`는 `>=` 범위 사용 — wheel 호환성 확보
- **보안 이슈 (미해결)**: `product_scraper.py` 공공데이터포털 API 키 평문 하드코딩 → `st.secrets` 이관 필요 (백로그 [High])
- **배포환경 제약**: Streamlit Cloud(미국) → nedrug.mfds.go.kr 접속은 KR 방화벽이 차단. 공공데이터포털 API 우선 + 사용자 브라우저 직접 열기 링크로 우회.

### [2026-04-18] 수정본 세션 보관 영역 합의
- Word 초안 다운로드 후 사용자가 노란색/검토필요 항목을 수정한 최종본을 재업로드하면, 세션이 종료되기 전까지 (또는 🔄 새로고침 전까지) 보관되어 재다운로드 가능.
- `st.session_state.edited_files = {"xlsx": {"bytes", "name"}, "docx": {"bytes", "name"}}` 구조.
- 🔄 새로고침은 `nonce` 증가로 위젯 key를 완전히 교체 — 업로드 파일까지 리셋.

### 남은 계약 논의 대상 (백로그)
- [High] `st.secrets` 이관 — API 키 평문 제거 (보안)
- [High] `_call_api` 에러 분기 UX — 429/5xx/만료키 구분 메시지
- [High] `product_scraper` mock 테스트 — items dict/list/빈값 3분기 회귀 방지
- [Med] (ㄹ)(ㅁ)(ㅂ) 초안 축약 — 상위 N + 기타 M건 패턴, 체크박스 UX
- [Med] 수정본 업로드 MIME/매직바이트 검증
- [Low] 사내 Docker 배포 옵션, nedrug 스크래핑 경로 제거 검토
