# 팀 간 인터페이스 정의서

작성일: 2026-04-17  
목적: 데이터 분석팀과 보고서 작성팀 간 데이터 계약 정의

## 팀 역할

### 데이터 분석팀 (Data Analysis Team)
- 담당 모듈: `validator.py`, `transformer.py`, `joiner.py`
- 책임: KIDS 원시자료 검증, 코드 변환, 테이블 병합
- 출력: 처리된 DataFrame + 통계 요약

### 보고서 작성팀 (Report Writing Team)
- 담당 모듈: `report_builder.py`, `app.py`
- 책임: Word 문서 생성, Streamlit UI
- 입력: 데이터 분석팀이 제공하는 ProcessedData 객체

---

## 데이터 계약 (Data Contract)

### ProcessedData (dataclass)

```python
@dataclass
class ProcessedData:
    df_merged: pd.DataFrame      # 병합된 최종 DataFrame
    df_line_listing: pd.DataFrame # Line Listing용 정렬된 DataFrame
    total_cases: int             # 유효 이상사례 총 건수
    warnings: list[str]          # 경고 메시지 (고아 데이터 등)
    unknown_codes: list[dict]    # 미확인 코드 목록 [{col, code, kaers_no}]
    analysis_period: tuple       # (start_date: str, end_date: str)
    drug_name: str               # 분석 대상 의약품명
    drug_code: str               # 분석 대상 의약품 코드
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
| WHOART_ARRN | WHO-ART SOC 코드 | 1313 |

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
| IS_SERIOUS | 중대성 |
| SERIOUSNESS_CRITERIA | 중대성 기준 |

---

## 소통 로그

팀 간 결정사항은 이 문서에 기록합니다.

### [2026-04-17] 초기 인터페이스 합의
- WHOART_ARRN을 SOC 그룹핑에 사용 (MedDRA 계층 코드 없으므로)
- REPRT_CHANGE_CD == 1 건은 transformer.py에서 완전 제거
- 미확인 코드는 문자열로 반환 (`[미확인코드: XXX]`)
- 중대성 = SE_DEATH/SE_LIFE_MENACE/SE_HSPTLZ_EXTN/SE_FNCT_DGRD/SE_ANMLY/SE_ETC_IMPRTNC_SITTN 중 하나라도 'Y'
