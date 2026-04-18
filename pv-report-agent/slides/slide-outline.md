# PV 보고서 자동화 에이전트 (6장 압축판)

## Meta
- **Topic**: KIDS 원시자료 기반 안전관리책임자 보고서 자동 생성 에이전트 소개
- **Target Audience**: 제약회사 약물감시(PV) 담당자, QA/RA 팀, 품목갱신 관리자
- **Tone/Mood**: 전문적·신뢰감·간결
- **Slide Count**: 6 slides (기존 14장 압축)
- **Aspect Ratio**: 16:9
- **style**: warm-neutral
- **Color Accent**: 베이지 베이스 + 골드 포인트, 중요 내용은 **노란색 하이라이트**

## Slide Composition

### Slide 1 — Cover
- **Type**: Cover
- **Title**: PV 보고서 자동화 에이전트
- **Subtitle**: 식약처 품목갱신용 *안전관리책임자 작성 자료*를 KIDS 원시자료에서 자동 생성
- **Footer**: 2026 · 의약품 안전관리 실무용 에이전트

### Slide 2 — 문제와 솔루션
- **Type**: Split (Problem ↔ Solution)
- **Problem**:
  - KIDS 원시자료 4종(DEMO·DRUG·EVENT·ASSESSMENT) 수동 파싱 — EUC-KR/UTF-8 혼재
  - 식약처 가이드라인 99~115p 구조 수작업 문서화
  - 중대성·인과성·SOC 분류 집계 수치 교차 검증 필요
- **Solution**:
  - 업로드 한 번 → **Word 초안 + 분석 엑셀 동시 생성**
  - Streamlit Cloud 배포 (`pharmarevision.streamlit.app`)
- **Highlight**: "담당자 1인당 품목당 수 시간 → 수 분"

### Slide 3 — 주요 기능 & 핵심 가치
- **Type**: Feature grid + 3-value cards
- **Features**:
  - 🔎 **2-way 제품 조회** — 품목기준코드 / 제품명 검색 (공공데이터포털 API) + nedrug 확인 링크
  - 📑 **README.txt 자동 감지** — 품목코드·보고기간 자동 선반영
  - 🧮 **공유 집계 모듈 (`aggregator.py`)** — Word/Excel 일관성 보장
  - 📊 **8시트 분석 엑셀 + Word 초안** — 표지·요약·(ㄱ)~(ㅂ) 자동 생성
  - 🚦 **검토 마커** — 노란(입력), 빨강(미확인 코드), 파랑(검토 필요)
- **Value cards**:
  - ⏱ **수 시간 → 수 분**
  - ✅ **100% 수치 일치** (Word ↔ Excel)
  - 📋 **가이드라인 99~115p 완전 준수**

### Slide 4 — 워크플로 & Streamlit UI
- **Type**: Timeline + UI sections
- **Steps (6단계)**:
  1. 업로드 (ZIP 또는 개별 .txt 드래그앤드롭)
  2. README.txt 자동 감지 → 품목코드·보고기간 선반영
  3. 제품 조회 — 공공데이터포털 API
  4. 검증·변환 — 인코딩 감지, 코드→텍스트, 무효 필터
  5. 공유 집계 — `aggregator.compute_aggregates()` 1회 호출
  6. 동시 생성 — 분석 엑셀 + Word 다운로드
- **UI 섹션**:
  - ① 원시자료 업로드 ② 제품 정보 조회 ③ 분석 기간 ④ 제품 정보 확인/수정 ⑤ 다운로드

### Slide 5 — 출력물 & 기술 스택
- **Type**: Split (출력 구조 ↔ 기술 + 품질)
- **Word 구조**:
  - 표지 → 1.요약 → 2.상세
  - 2.2.다: (ㄱ)보고건수 → (ㄴ)인구학적 → (ㄷ)SOC/PT·중대성·Line Listing → (ㄹ)허가비교 → (ㅁ)허가외 → (ㅂ)검토
- **엑셀 시트 (8~9)**: 요약통계 · Word연동 · 분석테이블 · Line Listing · DEMO · DRUG · EVENT · (ASSESSMENT) · 코드참조
- **Tech**: Python 3.11 · pandas · openpyxl · python-docx · streamlit · 공공데이터포털 `DrugPrdtPrmsnInfoService07`
- **품질**: pytest **74개** 통과 · `compare.py` 회귀 검증 · `pre-push` 훅으로 자동 실행 · 도메인 규칙 `.claude/rules/` 문서화

### Slide 6 — 활용 방안 & Closing
- **Type**: Closing + Use Cases
- **Use Cases**:
  - 🏭 품목갱신 실무 초안 산출
  - 📊 분기/연간 사내 안전성 리뷰
  - 🔍 내부 감사 / 실사 대응
  - 🧪 신규 품목 안전성 모니터링
- **Message**: **수작업 대신 검토에 집중하세요**
- **CTA**: pharmarevision.streamlit.app · github.com/Lucy1315/pharma_revision
