# PV 보고서 자동화 에이전트

## 프로젝트 목적

KIDS(한국의약품안전관리원) 원시자료를 분석하여 식약처 품목갱신 가이드라인 기반
**안전관리책임자가 작성한 안전관리에 관한 자료** Word 문서(.docx)를 자동 생성하는 Streamlit 앱.

## 디렉토리 구조

```
pv-report-agent/
├── CLAUDE.md               ← 이 파일
├── .claude/rules/          ← 도메인 규칙
├── data/
│   ├── raw/               ← KIDS 원시자료 txt 파일
│   ├── codebook/          ← 코드집 Excel
│   └── output/            ← 생성된 Word 보고서
├── docs/
│   ├── collaboration/     ← 팀 간 인터페이스 문서
│   └── files/             ← 테스트용 KIDS 원시자료
├── src/
│   ├── types.py           ← ProcessedData dataclass
│   ├── validator.py       ← 파일 검증 및 인코딩 처리
│   ├── transformer.py     ← 코드→텍스트 변환, 무효 필터
│   ├── joiner.py          ← 테이블 병합 및 필터링
│   └── report_builder.py  ← Word 문서 생성
├── tests/
├── app.py                 ← Streamlit 엔트리포인트
├── main.py                ← CLI 실행기
├── compare.py             ← 보고서 비교 검증
└── requirements.txt
```

## KIDS 원시자료 구조

### 사용하는 파일 (4종)

| 파일 | 주요 컬럼 | 설명 |
|------|-----------|------|
| DEMO.txt | KAERS_NO, RPT_DL_DT, REPRT_CHANGE_CD, PTNT_SEX, PTNT_OCCURSYMT_AGE, PTNT_AGRDE, RPT_TY, QCK_RPT_YN | 환자/사례 기본정보 |
| DRUG.txt | KAERS_NO, DRUG_SEQ, DRUG_GB, DRUG_CD, DRUG_ACTION | 의약품 정보 |
| EVENT.txt | KAERS_NO, ADR_SEQ, ADR_MEDDRA_KOR_NM, ADR_MEDDRA_ENG_NM, ADR_RESULT_CODE, WHOART_ARRN, SE_* (6개) | 이상사례 정보 |
| ASSESSMENT.txt | KAERS_NO, DRUG_SEQ, ADR_SEQ, EVALT_RESULT_CODE | 인과성 평가 (선택) |

- 구분자: `|` (pipe)
- 인코딩: EUC-KR 또는 UTF-8 (자동 감지)

### 미사용 파일

DRUG1.txt(성분코드), DRUG2.txt(투여량), DRUG3.txt, HIST_E.txt, PARENT.txt, GROUP.txt — 현 버전 미사용

## 핵심 비즈니스 룰

### 1. 무효 건 제거 (최우선)
```python
df = df[df['REPRT_CHANGE_CD'] != 1]  # 1=삭제, 2=수정(유지)
```

### 2. 보수적 의약품 필터링
```python
# DRUG_GB: 1=의심, 2=병용, 3=상호작용, 4=비투여
# 1/2/3 모두 포함 (가장 보수적인 전체 포함 모드)
target_kaers = drug_df[
    (drug_df['DRUG_CD'] == drug_code) &
    (drug_df['DRUG_GB'].isin([1, 2, 3]))
]['KAERS_NO'].unique()
```

### 3. 중대성 판단
```python
SE_COLS = ['SE_DEATH', 'SE_LIFE_MENACE', 'SE_HSPTLZ_EXTN',
           'SE_FNCT_DGRD', 'SE_ANMLY', 'SE_ETC_IMPRTNC_SITTN']
df['IS_SERIOUS'] = df[SE_COLS].eq('Y').any(axis=1)
```

### 4. 인과성 평가 선택 기준
- ASSESSMENT.txt에서 자사 의약품의 DRUG_SEQ와 매칭
- 동일 KAERS_NO에 여러 DRUG_SEQ가 있으면 의심약물(DRUG_GB=1) 우선
- ASSESSMENT.txt 없으면 `[검토필요: 인과성 평가 없음]` 표시

### 5. Line Listing 행 분리
- 1사례 × 다중 이상사례 → 이상사례별 1행 (건수 정확성 보장)

## 코드 매핑

### 주요 코드 (코드집 Excel '일괄보고 공통코드' 시트)

| 변수 | 코드→텍스트 |
|------|------------|
| PTNT_SEX | 1→남, 2→여 |
| PTNT_AGRDE | 0→태아, 1→출생~28일, 2→28일~24개월, 3→24개월~12세, 4→12~19세, 5→19~65세, 6→65세이상 |
| ADR_RESULT_CODE | 1→회복됨, 2→회복중, 3→회복안됨, 4→후유증, 5→치명적, 0→알려지지않음 |
| DRUG_GB | 1→의심, 2→병용, 3→상호작용, 4→비투여 |
| DRUG_ACTION | 1→투여중지, 2→투여량감소, 3→투여량증가, 4→투여량유지, 0→모름, 9→해당없음 |
| EVALT_RESULT_CODE | 1→확실함, 2→상당히확실함, 3→가능함, 4→가능성적음, 5→평가곤란, 6→평가불가 |
| RPT_TY | 1→자발적보고, 2→시험/연구, 3→기타, 4→모름 |
| QCK_RPT_YN | Y→신속보고 |

### WHOART SOC 코드 → 기관계대분류 (하드코딩)
`.claude/rules/domain.md` 참조

## 출력 문서 구조 (식약처 가이드라인 99~115p)

1. 표지 (회사정보 테이블)
2. 1. 요약
3. 2. 상세
   - 2.1 약물감시 업무 절차 (정적 텍스트 + Placeholder)
   - 2.2 갱신 대상 품목 안전관리에 관한 자료
     - 가. 신속보고 자료
     - 나. 정기보고 자료
     - 다. 수집대상정보
       - (ㄱ) 보고 건수 → **Table: 보고유형 요약**
       - (ㄴ) 인구학적 자료 → **Table: 성별/연령대**
       - (ㄷ) 이상사례 발현 현황 → **Table: SOC/PT 요약** + **Table: 중대성** + **Table: Line Listing**
       - (ㄹ) 허가사항 비교 (정성 텍스트)
       - (ㅁ) 허가사항 외 이상사례 (정성 텍스트)
       - (ㅂ) 검토 (정성 텍스트)

## Placeholder 규칙

| 색상 | 의미 | 예시 |
|------|------|------|
| 노란색 하이라이트 | 사내 데이터 직접 입력 필요 | `[이곳에 연간 판매량을 입력하세요]` |
| 빨간색 텍스트 | 미확인 코드 | `[미확인코드: M999]` |
| 파란색 텍스트 | 검토 필요 항목 | `[검토필요: 인과성 평가 없음]` |

## 통계 무결성 검증

```python
assert len(df_merged) == line_listing_row_count, "건수 불일치!"
# 불일치 시 → Word 문서 첫 장에 굵은 빨간색 경고문 삽입
```

## 개발 가이드

- Python 3.10+
- 패키지: pandas, openpyxl, python-docx, streamlit, pytest, numpy
- 테스트 데이터: `../docs/files/` (DEMO.txt, DRUG.txt, EVENT.txt, ASSESSMENT.txt)
- 코드집: `../[붙임 2] 의약품부작용보고원시자료 코드집.xlsx`
- 참조 보고서: `../안전관리책임자가 작성한 안전관리에 관한 자료.docx`
