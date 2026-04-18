# PV 보고서 자동화 에이전트

## Meta
- **Topic**: KIDS 원시자료 기반 안전관리책임자 보고서 자동 생성 에이전트 소개
- **Target Audience**: 제약회사 약물감시(PV) 담당자, QA/RA 팀, 품목갱신 관리자
- **Tone/Mood**: 전문적·신뢰감·읽기 쉬움 (정부 가이드라인 기반 공식 보고서 도메인)
- **Slide Count**: 14 slides
- **Aspect Ratio**: 16:9
- **style**: warm-neutral
- **Color Accent**: 베이지 베이스 + 골드 포인트, 중요 내용은 **노란색 하이라이트**

## Slide Composition

### Slide 1 - Cover
- **Type**: Cover
- **Title**: PV 보고서 자동화 에이전트
- **Subtitle**: 식약처 품목갱신용 *안전관리책임자 작성 자료*를 KIDS 원시자료에서 자동 생성
- **Footer**: 2026 · 의약품 안전관리 실무용 에이전트

### Slide 2 - Table of Contents
- **Type**: Contents
- **Items**:
  1. 문제 정의 — 왜 자동화인가
  2. 솔루션 개요 & 핵심 가치
  3. 주요 기능
  4. 데이터 & 도메인 룰
  5. 워크플로우
  6. 구현 화면
  7. 출력물 구조
  8. 기술 스택 & 품질
  9. 활용 방안
  10. 다음 단계

### Slide 3 - 문제 정의
- **Type**: Content (Problem Statement)
- **Key Message**: 품목갱신 시마다 반복되는 **수작업 집계·문서화**
- **Details**:
  - KIDS 원시자료 4종(DEMO·DRUG·EVENT·ASSESSMENT) 수동 파싱 — EUC-KR/UTF-8 혼재
  - 식약처 가이드라인 99~115p 구조에 맞춰 표·문단 재작성
  - 중대성·인과성·SOC 분류 집계 수치 **교차 검증 필요**
  - 제품 허가정보(nedrug / 공공데이터포털) 조회 후 표지 작성
- **Highlight**: "담당자 1인당 품목당 수 시간 소요"

### Slide 4 - 솔루션 개요
- **Type**: Content (Solution Overview)
- **Key Message**: 업로드 한 번 → **Word 초안 + 분석 엑셀 동시 생성**
- **Details**:
  - 입력: KIDS ZIP 또는 개별 .txt 드래그앤드롭
  - 출력: 식약처 가이드라인 구조 Word + 8~9시트 분석 엑셀
  - 배포: Streamlit Cloud (`pharmarevision.streamlit.app`)
- **Highlight**: "수작업 보고서와 **8/8 핵심 수치 100% 일치**"

### Slide 5 - 핵심 가치
- **Type**: Statistics / Value Cards (3-card layout)
- **Key Message**: 시간 절감 · 수치 일관성 · 규제 적합성
- **Cards**:
  - ⏱ **수 시간 → 수 분** — 반복 작업 제거
  - ✅ **100% 수치 일치** — aggregator 단일 진입점
  - 📋 **식약처 가이드라인 완전 준수** — 99~115p 구조 내장
- **Highlight**: 중앙 카드 "100% 일치"

### Slide 6 - 주요 기능
- **Type**: Content (Feature Grid)
- **Key Message**: 데이터 파이프라인부터 문서화까지 end-to-end
- **Details**:
  - 🔎 **3-way 제품 조회** — 품목기준코드 / 제품명 / nedrug URL (공공데이터포털 API + 스크래핑 fallback)
  - 📑 **README.txt 자동 감지** — 품목코드·보고기간 자동 선반영
  - 🧮 **공유 집계 모듈** (`aggregator.py`) — Word/Excel 일관성 보장
  - 📊 **8시트 분석 엑셀** — 요약/Word연동/Line Listing/DEMO/DRUG/EVENT/ASSESSMENT/코드참조
  - 📄 **Word 초안** — 표지·요약·상세·(ㄱ)~(ㅂ) 섹션 자동 생성
  - 🚦 **검토 마커** — 노란 하이라이트(사용자 입력), 빨강(미확인 코드), 파랑(검토 필요)

### Slide 7 - 데이터 & 도메인 룰
- **Type**: Content (Rules)
- **Key Message**: 약물감시 핵심 룰을 **코드로 고정**
- **Details**:
  - 무효 건 제거: `REPRT_CHANGE_CD == 1` 우선 필터
  - 보수적 의약품 필터: `DRUG_GB ∈ {1 의심, 2 병용, 3 상호작용}` 모두 포함
  - 중대성 판단: `SE_DEATH/LIFE_MENACE/HSPTLZ_EXTN/FNCT_DGRD/ANMLY/ETC` 중 하나라도 Y
  - 인과성 우선순위: 동일 KAERS_NO 내 의심약물(DRUG_GB=1) 우선
  - Line Listing: 1사례 × 다중 이상사례 → 이상사례별 1행
- **Highlight**: "무효 건 제거 · 보수적 필터 · 중대성 플래그"

### Slide 8 - 워크플로우
- **Type**: Timeline / Workflow (horizontal)
- **Key Message**: 6단계 파이프라인
- **Steps**:
  1. **업로드** — ZIP 또는 개별 .txt (드래그앤드롭)
  2. **자동 감지** — README.txt → 품목코드·보고기간 선반영
  3. **제품 조회** — 공공데이터포털 API (fallback: nedrug)
  4. **검증·변환** — 인코딩 감지, 코드→텍스트 매핑, 무효 필터
  5. **공유 집계** — `aggregator.compute_aggregates()` 1회 호출
  6. **동시 생성** — 분석 엑셀 + Word 보고서 다운로드
- **Highlight**: 5단계 "공유 집계 — 단일 진입점"

### Slide 9 - 구현 화면 (Streamlit UI)
- **Type**: Screenshot / UI Walkthrough
- **Key Message**: 1-페이지 Streamlit UI — 입력 → 생성 → 다운로드 → 수정본 재업로드
- **Screen sections**:
  - ① 원시자료 업로드 (ZIP/다중 .txt)
  - ② 제품 정보 조회 (3가지 모드)
  - ③ 분석 기간 (DEMO.txt에서 자동 감지)
  - ④ 제품 정보 확인/수정
  - ⑤ 다운로드 (엑셀 + Word)
  - ⑥ 수정본 재업로드 보관
- **Note**: 실제 스크린샷은 디자인 단계에서 추가 (Nano Banana 또는 placeholder)

### Slide 10 - 출력물 구조
- **Type**: Split-screen (Word 구조 ↔ 엑셀 시트)
- **Key Message**: 식약처 가이드라인 구조 그대로 재현
- **Word 구조**:
  - 표지 → 1.요약 → 2.상세
  - 2.2.다: (ㄱ)보고 건수 → (ㄴ)인구학적 → (ㄷ)SOC/PT + 중대성 + Line Listing → (ㄹ)허가사항 비교 → (ㅁ)허가사항 외 → (ㅂ)검토
- **엑셀 시트 (8~9)**:
  - 요약통계 · Word연동수치 · 분석테이블 · Line Listing · DEMO · DRUG · EVENT · (ASSESSMENT) · 코드참조
- **Highlight**: "Word ↔ 엑셀 수치 100% 일치"

### Slide 11 - 기술 스택 & 품질
- **Type**: Content (Tech + QA)
- **Key Message**: Python 데이터 스택 + TDD 기반 품질 관리
- **Tech**:
  - Python 3.11 · pandas · openpyxl · python-docx · streamlit
  - 공공데이터포털 `DrugPrdtPrmsnInfoService07`
  - Streamlit Cloud 배포 (runtime.txt `3.11`, requirements `>=` 범위)
- **품질 지표**:
  - **pytest 43개 통과**
  - **`compare.py` 회귀 검증** — 수작업 보고서와 8개 핵심 수치 1:1 매칭
  - **도메인 규칙 `.claude/rules/domain.md` 문서화**
- **Highlight**: "43개 테스트 · 8/8 수치 일치"

### Slide 12 - 활용 방안
- **Type**: Use Case Grid
- **Key Message**: PV·RA·QA 여러 포지션에서 재활용 가능
- **Use Cases**:
  - 🏭 **품목갱신 실무** — 갱신 주기마다 즉시 초안 산출
  - 📊 **분기/연간 사내 안전성 리뷰** — 분석 엑셀 독립 활용
  - 🔍 **내부 감사 / 실사 대응** — Line Listing + 집계 근거 제시
  - 🧪 **신규 품목 안전성 모니터링** — 기간만 바꿔 반복 실행
  - 🎓 **신입 PV 담당자 교육** — 가이드라인 구조 학습 도구
- **Highlight**: "🏭 품목갱신 실무"

### Slide 13 - 다음 단계 & 확장 가능성
- **Type**: Roadmap
- **Key Message**: 보안·UX·확장을 중심으로 다음 스프린트 준비
- **Next**:
  - **[High] 공공데이터포털 API 키 `st.secrets` 이관** — 평문 하드코딩 제거
  - **[High] API 에러 분기** — 429/5xx/만료키 UX 메시지 구분
  - **[High] product_scraper mock 테스트** — 회귀 방지
  - [Med] (ㄹ)(ㅁ)(ㅂ) 초안 축약 UX / 수정본 MIME 검증
  - [Low] 사내 Docker 배포 옵션
- **Highlight**: "[High] API 키 Secrets 이관"

### Slide 14 - Closing
- **Type**: Closing
- **Message**: **수작업 대신 검토에 집중하세요** — PV 보고서 자동화 에이전트
- **CTA**: pharmarevision.streamlit.app · github.com/Lucy1315/pharma_revision
- **Thank you**
