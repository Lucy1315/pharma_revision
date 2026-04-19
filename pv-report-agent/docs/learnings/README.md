# Learnings — pv-report-agent

세션마다 쌓인 **배포/운영/도메인 교훈**을 휘발되지 않게 기록한다.
코드를 읽어 알 수 있는 내용은 여기 쓰지 않는다 — *왜 그렇게 했는지* 를 남긴다.

## 포함 기준

- 커밋 메시지만으로는 알 수 없는 **의사결정 맥락** (왜 A가 아니라 B인가)
- 실제로 부딪힌 **외부 제약** (인프라·정책·공공 API 동작)
- 재발 가능한 **실수 패턴** + 그것을 잡는 장치

## 제외 기준

- 일반 프로그래밍 지식, 파이썬 관용구
- `CLAUDE.md` / `domain.md` 에 이미 있는 도메인 룰
- 아직 재현 안 한 추측

## 파일 목록

- [deployment-streamlit-cloud.md](deployment-streamlit-cloud.md) — Streamlit Cloud 배포에서 실제로 깨졌던 것들
- [external-api.md](external-api.md) — 공공데이터포털 · nedrug 접근 제약과 폴백 전략
- [streamlit-ui-pitfalls.md](streamlit-ui-pitfalls.md) — 위젯 state·업로드·다운로드 흐름의 함정

## 글쓰기 가이드

각 파일은 다음 구조를 따른다.

```markdown
# <주제>

## <한 줄 교훈>

- **상황**: 무엇을 하려 했나
- **깨진 것**: 어떻게 깨졌나 (구체적으로)
- **원인**: 왜 그렇게 됐나
- **해결**: 지금 이 레포에서 어떻게 풀려있나 (파일·함수 레벨)
- **재발 방지**: 미래 나 / 다른 엔지니어가 같은 실수를 피하려면
```
