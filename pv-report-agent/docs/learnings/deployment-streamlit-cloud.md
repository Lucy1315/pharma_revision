# Streamlit Cloud 배포 교훈

pharmarevision.streamlit.app 로 배포하면서 실제로 깨졌던 항목들.

---

## 1) `runtime.txt` 포맷은 `3.11` — Heroku 스타일 아님

- **상황**: 파이썬 버전을 고정하려고 `python-3.11` 로 적어 push 함.
- **깨진 것**: Streamlit Cloud 가 버전을 인식 못 해 기본(3.13 계열) 으로 빌드 → wheel 불일치로 pandas 소스 컴파일 → 빌드 시간 폭발 + 실패.
- **원인**: Streamlit Cloud 의 `runtime.txt` 포맷은 Heroku 포맷이 아님. `3.11` 처럼 **버전 숫자만** 적는다.
- **해결**: `pv-report-agent/runtime.txt` → `3.11` (줄바꿈 1개 포함, 5바이트).
- **재발 방지**: 이 파일은 5바이트 이상이면 의심할 것.

## 2) `requirements.txt` 는 `>=` 범위로

- **상황**: 재현성 확보하려고 `pandas==2.2.0` 처럼 정확 버전 고정.
- **깨진 것**: Cloud 의 Python 마이너 버전과 wheel 이 맞지 않을 때 소스 컴파일로 폴백 → 10분+ 빌드 → 타임아웃 혹은 메모리 부족.
- **원인**: 공개 레지스트리의 wheel 커버리지가 완벽하지 않음. 정확 고정은 로컬에서 재현성은 좋지만 매니지드 플랫폼에서는 독.
- **해결**: `>=X.Y` 범위로. 주요 패키지 하위 호환 꺾일 때만 상한(`<Z`) 추가.
- **재발 방지**: 범위 지정은 **로컬 재현성 희생 대신 배포 안정성을 얻는 트레이드**. 로컬 재현은 venv lockfile 로 별도 관리.

## 3) 미국 → `nedrug.mfds.go.kr` 접속 차단

- **상황**: nedrug 제품 상세 페이지를 서버에서 스크래핑해 허가정보를 채우려 함.
- **깨진 것**: Streamlit Cloud(미국 리전) → nedrug.mfds.go.kr 로 요청 시 `ECONNRESET`. 재시도·타임아웃 조정 무의미.
- **원인**: KR 공공 인프라 방화벽이 해외 IP 를 차단. 우회 불가.
- **해결**:
  1. **서버 조회 경로**: 공공데이터포털 `DrugPrdtPrmsnInfoService07` API 로 대체 (이건 해외 접속 허용).
  2. **사용자 확인 경로**: 조회 성공 시 nedrug `searchDrug` URL 링크를 UI 하단에 노출 → 사용자 KR 브라우저에서 재확인.
- **재발 방지**: 국내 공공 사이트 직접 스크래핑은 **배포 환경 지역 먼저 확인**. `src/product_scraper.py` 의 `scrape_product_info()` 는 남아있으나 `app.py` 에서 import 하지 않는 상태로 유지 — 사내 배포 전환 시 되살릴 수 있게.

## 4) 비밀키는 `.streamlit/secrets.toml` + Cloud Secrets 탭

- **상황**: `DATA_GO_KR_KEY` 를 편의상 환경변수로만 주입하려 함.
- **깨진 것**: 없음 (환경변수도 동작). 다만 `.streamlit/secrets.toml.example` 에 **실제 키를 잘못 붙여넣어** 커밋 직전까지 간 사고가 한 번 있었음.
- **원인**: `.example` 파일명은 gitignore 예외라 그대로 push 되면 공개 레포에 키가 노출된다.
- **해결**:
  - 실제 키 → Streamlit Cloud 의 **앱 설정 → Secrets** 탭.
  - 로컬 개발 → `.streamlit/secrets.toml` (gitignored).
  - 템플릿 → `.streamlit/secrets.toml.example` 에는 **플레이스홀더만** (`"여기에_발급받은_키를_붙여넣으세요"`).
- **재발 방지**: `git diff` 에서 `.example` 파일이 수정되면 항상 내용 확인. 노출된 키는 즉시 재발급.
