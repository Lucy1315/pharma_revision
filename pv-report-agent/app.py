import io
import re
import urllib.parse
import zipfile
import tempfile
from pathlib import Path

import streamlit as st


MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


from src.validator import load_and_validate, ValidationError
from src.transformer import filter_invalid, transform_demo, transform_drug, transform_event, transform_assessment, detect_period
from src.joiner import detect_drug_code, join_tables, build_line_listing
from src.report_builder import build_report
from src.excel_builder import build_excel
from src.product_scraper import lookup_product_info, search_drug_by_name, ProductInfo
from src.types import ProcessedData


def extract_uploads_to(tmpdir: Path, uploaded) -> list[str]:
    """업로드된 파일 리스트(ZIP + .txt 혼합)를 tmpdir에 평탄화하여 저장.
    반환: 저장된 .txt 파일 이름 목록."""
    if not uploaded:
        return []
    for f in uploaded:
        name = f.name
        if name.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(f.getvalue())) as zf:
                zf.extractall(tmpdir)
        elif name.lower().endswith(".txt"):
            (tmpdir / name).write_bytes(f.getvalue())

    # ZIP 내 서브디렉토리 평탄화
    for txt in list(tmpdir.rglob("*.txt")):
        if txt.parent != tmpdir:
            dest = tmpdir / txt.name
            if not dest.exists():
                txt.rename(dest)
    return sorted(p.name for p in tmpdir.glob("*.txt"))


def read_demo_bytes_from_uploads(uploaded) -> bytes | None:
    """업로드 리스트에서 DEMO.txt 원본 바이트 반환 (기간 자동 감지용)."""
    if not uploaded:
        return None
    for f in uploaded:
        if f.name.lower() == "demo.txt":
            return f.getvalue()
    for f in uploaded:
        if f.name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(f.getvalue())) as zf:
                    for n in zf.namelist():
                        if n.split("/")[-1].upper() == "DEMO.TXT":
                            return zf.read(n)
            except Exception:
                continue
    return None


def read_readme_bytes_from_uploads(uploaded) -> bytes | None:
    """업로드 리스트에서 README.txt 원본 바이트 반환 (품목코드·보고기간 자동 감지용)."""
    if not uploaded:
        return None
    _targets = {"readme.txt", "read.me", "readme"}
    for f in uploaded:
        if f.name.lower() in _targets:
            return f.getvalue()
    for f in uploaded:
        if f.name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(f.getvalue())) as zf:
                    for n in zf.namelist():
                        base = n.split("/")[-1].lower()
                        if base in _targets:
                            return zf.read(n)
            except Exception:
                continue
    return None


def parse_readme(raw: bytes) -> dict:
    """KAERS DB README.txt에서 요청 품목코드·보고기간을 추출한다.

    반환 예: {"item_code": "201506668", "start_date": "2020-09-21", "end_date": "2024-06-30"}
    """
    if not raw:
        return {}
    text = ""
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if not text:
        return {}

    result: dict = {}

    # 요청 품목코드 : 201506668  (또는 "요청 품목기준코드")
    m_code = re.search(r"요청\s*품목(?:기준)?코드\s*[:：]\s*([0-9A-Za-z]+)", text)
    if m_code:
        result["item_code"] = m_code.group(1).strip()

    # 요청 자료 보고기간 : 2020.09.21. ~ 2024.06.30.
    m_period = re.search(
        r"요청\s*자료\s*보고\s*기간\s*[:：]\s*"
        r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\.?\s*~\s*"
        r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\.?",
        text,
    )
    if m_period:
        g = m_period.groups()
        result["start_date"] = f"{g[0]}-{g[1].zfill(2)}-{g[2].zfill(2)}"
        result["end_date"] = f"{g[3]}-{g[4].zfill(2)}-{g[5].zfill(2)}"

    return result

st.set_page_config(page_title="PV 보고서 자동화", page_icon="📋", layout="wide")

# ── 상태 초기화용 nonce (위젯 key를 바꿔 완전 초기화) ─────────
if "nonce" not in st.session_state:
    st.session_state.nonce = 0
_n = st.session_state.nonce
if "generated_result" not in st.session_state:
    st.session_state.generated_result = None
if "edited_files" not in st.session_state:
    st.session_state.edited_files = {"xlsx": None, "docx": None}

# ── 헤더 ─────────────────────────────────────────────────────
_h_col1, _h_col2 = st.columns([6, 1])
with _h_col1:
    st.title("📋 안전관리책임자 보고서 자동 생성")
    st.caption("식약처 품목갱신 가이드라인(99~115p) 기반 Word 문서 + 원시자료 분석 엑셀 자동 생성")
with _h_col2:
    st.write("")  # 세로 정렬용 여백
    if st.button("🔄 새로고침", help="입력값과 업로드 파일을 모두 초기화합니다", use_container_width=True):
        # 모든 세션 상태 초기화 + nonce 증가(위젯 key 변경으로 파일 업로더까지 리셋)
        for _k in list(st.session_state.keys()):
            del st.session_state[_k]
        st.session_state.nonce = _n + 1
        st.rerun()

# ── 워크플로 안내 ────────────────────────────────────────────
with st.expander("📌 사용 방법", expanded=False):
    st.markdown("""
    1. **원시자료 업로드** — 다음 둘 중 편한 방법:
       - **방법 A**: DEMO/DRUG/EVENT/ASSESSMENT.txt를 압축한 **ZIP 파일 1개**
       - **방법 B**: 개별 **.txt 파일 여러 개**를 Ctrl/Cmd+클릭 또는 **드래그앤드롭**으로 선택
    2. **제품 정보 URL** 입력 — [식약처 의약품통합정보시스템](https://nedrug.mfds.go.kr) 제품 상세페이지 URL
    3. **분석 기간** 및 추가 정보 확인 후 **보고서 생성** 클릭
    4. 생성된 **원시자료 분석 엑셀** 및 **안전관리보고서 Word** 다운로드
    5. Word 초안의 노란색 항목을 직접 수정하여 최종화

    필수 파일: `DEMO.txt`, `DRUG.txt`, `EVENT.txt` / 선택: `ASSESSMENT.txt`, `DRUG1/2/3.txt`
    """)

# ── 입력 영역 ────────────────────────────────────────────────
col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.subheader("① 원시자료 업로드")
    uploaded_files = st.file_uploader(
        "원시자료 (ZIP 또는 여러 .txt 파일)",
        type=["zip", "txt"],
        accept_multiple_files=True,
        key=f"uploads_{_n}",
        help=(
            "두 가지 방법 중 편한 쪽으로 업로드:\n"
            "• 방법 1: DEMO/DRUG/EVENT/ASSESSMENT.txt를 압축한 ZIP 파일 1개\n"
            "• 방법 2: 개별 .txt 파일들을 Ctrl/Cmd+클릭으로 여러 개 선택, 또는 드래그앤드롭\n\n"
            "필수: DEMO.txt, DRUG.txt, EVENT.txt / 선택: ASSESSMENT.txt, DRUG1/2/3.txt\n"
            "권장: README.txt 포함 시 품목기준코드·보고기간 자동 입력"
        )
    )

    # ── README.txt 자동 감지: 품목기준코드/보고기간 선반영 ─────────
    _readme_info: dict = {}
    if uploaded_files:
        _readme_bytes = read_readme_bytes_from_uploads(uploaded_files)
        if _readme_bytes:
            _readme_info = parse_readme(_readme_bytes)

        # 업로드 파일셋이 바뀐 시점에만 세션 상태를 강제 갱신 (사용자 수정 보존)
        _upload_sig = tuple(
            (f.name, getattr(f, "size", len(f.getvalue()))) for f in uploaded_files
        )
        _sig_key = f"_last_upload_sig_{_n}"
        if _readme_info and st.session_state.get(_sig_key) != _upload_sig:
            st.session_state[_sig_key] = _upload_sig
            if _readme_info.get("item_code"):
                st.session_state[f"api_code_{_n}"] = _readme_info["item_code"]
                st.session_state[f"drug_code_{_n}"] = _readme_info["item_code"]
                st.session_state[f"search_mode_{_n}"] = "품목기준코드로 조회"
            if _readme_info.get("start_date"):
                st.session_state[f"start_{_n}"] = _readme_info["start_date"]
            if _readme_info.get("end_date"):
                st.session_state[f"end_{_n}"] = _readme_info["end_date"]

        if _readme_info:
            _msgs = []
            if _readme_info.get("item_code"):
                _msgs.append(f"품목기준코드 `{_readme_info['item_code']}`")
            if _readme_info.get("start_date") and _readme_info.get("end_date"):
                _msgs.append(
                    f"보고기간 `{_readme_info['start_date']} ~ {_readme_info['end_date']}`"
                )
            if _msgs:
                st.info("📑 **README.txt 자동 감지** — " + ", ".join(_msgs))

    st.subheader("② 제품 정보 조회")
    search_mode = st.radio(
        "조회 방식",
        ["품목기준코드로 조회", "제품명으로 검색"],
        horizontal=True,
        key=f"search_mode_{_n}",
        help="공공데이터포털 API를 통해 조회합니다."
    )

    product: ProductInfo | None = None

    if search_mode == "품목기준코드로 조회":
        _api_code = st.text_input(
            "품목기준코드 입력",
            placeholder="예: 201506668",
            key=f"api_code_{_n}",
            help="의약품 품목기준코드(숫자)를 입력하면 공공데이터포털 API로 조회합니다."
        )
        if _api_code and _api_code.strip():
            with st.spinner("공공데이터포털 API 조회 중..."):
                try:
                    product = lookup_product_info(item_seq=_api_code.strip())
                    if product and product.item_name:
                        st.success(f"✅ API 조회 완료: **{product.item_name}** ({product.company_name})")
                        _nedrug_url = (
                            "https://nedrug.mfds.go.kr/searchDrug"
                            f"?searchYn=true&itemName={urllib.parse.quote(product.item_name)}"
                        )
                        st.markdown(f"🔗 nedrug 에서 확인: [{_nedrug_url}]({_nedrug_url})")
                    elif product and product.warnings:
                        # API 키/네트워크/호출제한 등은 st.error, 결과 없음은 st.warning
                        for w in product.warnings:
                            if any(k in w for k in ("API 키", "연결 실패", "호출 제한", "API 오류", "응답 형식")):
                                st.error(w)
                            else:
                                st.warning(w)
                    else:
                        st.warning("해당 품목기준코드로 조회된 결과가 없습니다. 오른쪽에서 직접 입력하세요.")
                except Exception as e:
                    st.error(f"API 조회 실패: {e}")

    elif search_mode == "제품명으로 검색":
        _api_name = st.text_input(
            "제품명 입력",
            placeholder="예: 프로테조밉주",
            key=f"api_name_{_n}",
            help="제품명(일부 가능)을 입력하면 검색 결과를 표시합니다."
        )
        if _api_name and _api_name.strip():
            with st.spinner("공공데이터포털 API 검색 중..."):
                try:
                    results, _api_err = search_drug_by_name(_api_name.strip(), num_of_rows=10)
                    if _api_err:
                        st.error(_api_err)
                    if results:
                        options = {
                            f"{r.item_name} — {r.company_name} (코드: {r.item_seq})": r
                            for r in results if r.item_name
                        }
                        if options:
                            selected_label = st.selectbox(
                                f"검색 결과 ({len(options)}건)",
                                list(options.keys()),
                                key=f"api_results_{_n}",
                            )
                            product = options[selected_label]
                            # 검색 응답은 성분/허가번호 등 일부 필드가 비어있으므로
                            # item_seq 로 상세+주성분 API 를 재호출하여 보강.
                            if product.item_seq:
                                enriched = lookup_product_info(item_seq=product.item_seq)
                                if enriched and enriched.item_name:
                                    product = enriched
                            st.success(f"✅ 선택: **{product.item_name}**")
                            # nedrug 검색 페이지 링크 (사용자 최종 확인용)
                            if product.item_name:
                                _nedrug_url = (
                                    "https://nedrug.mfds.go.kr/searchDrug"
                                    f"?searchYn=true&itemName={urllib.parse.quote(product.item_name)}"
                                )
                                st.markdown(f"🔗 nedrug 에서 확인: [{_nedrug_url}]({_nedrug_url})")
                        else:
                            st.warning("검색 결과가 없습니다.")
                    elif not _api_err:
                        # 에러가 아니라 단순히 매칭 결과가 없는 경우만 여기 표시
                        st.warning("검색 결과가 없습니다. 제품명을 다시 확인하세요.")
                except Exception as e:
                    st.error(f"API 검색 실패: {e}")

with col_right:
    st.subheader("③ 분석 기간")

    # 업로드된 파일(ZIP 또는 개별)에서 DEMO.txt 찾아 기간 자동 감지
    _auto_start, _auto_end = "", ""
    _demo_bytes = read_demo_bytes_from_uploads(uploaded_files)
    if _demo_bytes is not None:
        try:
            import pandas as _pd
            _demo_raw = _pd.read_csv(
                io.BytesIO(_demo_bytes),
                sep="|", dtype=str, encoding_errors="replace",
            )
            _auto_start, _auto_end = detect_period(_demo_raw)
            if _auto_start:
                _auto_start = f"{_auto_start[:4]}-{_auto_start[4:6]}-{_auto_start[6:]}"
                _auto_end   = f"{_auto_end[:4]}-{_auto_end[4:6]}-{_auto_end[6:]}"
        except Exception:
            pass

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.text_input("시작일 (YYYY-MM-DD)", value=_auto_start,
                                   placeholder="YYYY-MM-DD",
                                   key=f"start_{_n}",
                                   help="업로드된 DEMO.txt에서 자동 감지")
    with col2:
        end_date = st.text_input("종료일 (YYYY-MM-DD)", value=_auto_end,
                                 placeholder="YYYY-MM-DD",
                                 key=f"end_{_n}",
                                 help="업로드된 DEMO.txt에서 자동 감지")

    st.subheader("④ 제품 정보 확인/수정")

    # 제품 조회 결과가 바뀐 시점에만 session_state 에 반영 (사용자 수정은 보존)
    if product and product.item_name:
        _prod_sig = (product.item_seq, product.item_name, product.company_name)
        _prod_sig_key = f"_last_product_sig_{_n}"
        if st.session_state.get(_prod_sig_key) != _prod_sig:
            st.session_state[_prod_sig_key] = _prod_sig
            st.session_state[f"drug_code_{_n}"] = product.item_seq or ""
            st.session_state[f"drug_name_{_n}"] = product.item_name or ""
            st.session_state[f"company_{_n}"] = product.company_name or ""
            st.session_state[f"ingredient_{_n}"] = product.ingredient_name or ""
            st.session_state[f"appr_date_{_n}"] = product.approval_date or ""
            st.session_state[f"appr_num_{_n}"] = product.approval_number or product.item_seq or ""

    drug_code_input = st.text_input(
        "의약품 코드 (품목기준코드)",
        placeholder="자동 감지 또는 직접 입력",
        key=f"drug_code_{_n}",
    )
    drug_name = st.text_input("제품명", key=f"drug_name_{_n}")
    company_name = st.text_input("회사명", key=f"company_{_n}")
    ingredient_name = st.text_input("성분명", key=f"ingredient_{_n}")
    approval_date = st.text_input("허가일", key=f"appr_date_{_n}")
    approval_number = st.text_input("허가번호", key=f"appr_num_{_n}")

# ── 업로드 상태 ─────────────────────────────────────────────
st.divider()
ready = bool(uploaded_files)
if ready:
    n_uploaded = len(uploaded_files)
    _names = ", ".join(f.name for f in uploaded_files)
    st.success(f"📂 {n_uploaded}개 파일 업로드됨: {_names}")
else:
    st.info("원시자료 ZIP 또는 개별 .txt 파일을 업로드하면 보고서 생성이 활성화됩니다.")

if st.button("🚀 보고서 생성", type="primary", disabled=not ready):
    progress = st.progress(0, text="파일 정리 중...")
    warnings_log: list[str] = []

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # ── STEP 1: 업로드 파일 정리 (ZIP 압축 해제 or 개별 .txt 복사) ──
            extracted = extract_uploads_to(tmpdir, uploaded_files)
            if not extracted:
                st.error("❌ .txt 파일이 발견되지 않았습니다. ZIP 또는 .txt 파일을 업로드하세요.")
                st.stop()

            required = ["DEMO.txt", "DRUG.txt", "EVENT.txt"]
            missing = [f for f in required if not (tmpdir / f).exists()]
            if missing:
                st.error(f"❌ ZIP에 필수 파일이 없습니다: {', '.join(missing)}")
                st.stop()

            # ASSESSMENT 경로 (선택)
            assess_path = tmpdir / "ASSESSMENT.txt"
            if not assess_path.exists():
                assess_path = None
                warnings_log.append("ASSESSMENT.txt 없음 — 인과성 평가 제외")

            progress.progress(15, text="파일 검증 및 코드 변환 중...")

            # ── STEP 2: 의약품 코드 확정 ──────────────────────
            from src.validator import read_file
            tmp_drug_df = read_file(tmpdir / "DRUG.txt")
            auto_code = detect_drug_code(tmp_drug_df) if tmp_drug_df is not None else ""
            drug_code = drug_code_input.strip() or auto_code
            if not drug_code:
                st.error("의약품 코드를 입력하거나 URL로 제품 정보를 조회하세요.")
                st.stop()

            progress.progress(25, text="데이터 로드 및 검증 중...")

            # ── STEP 3: Word용 데이터 준비 (검증 → 변환 → 병합) ──
            drug_name_final = drug_name.strip() or drug_code
            demo_df, drug_df, event_df, assessment_df, val_warns = load_and_validate(
                tmpdir / "DEMO.txt",
                tmpdir / "DRUG.txt",
                tmpdir / "EVENT.txt",
                assess_path,
                start_date.replace("-", ""),
                end_date.replace("-", ""),
            )
            warnings_log.extend(val_warns)

            unknown_codes: list[dict] = []
            demo_df, removed = filter_invalid(demo_df)
            if removed:
                warnings_log.append(f"REPRT_CHANGE_CD=1 무효 건 {removed}건 제거")
            demo_df = transform_demo(demo_df, unknown_codes)
            drug_df = transform_drug(drug_df, unknown_codes)
            event_df = transform_event(event_df, unknown_codes)
            if assessment_df is not None:
                assessment_df = transform_assessment(assessment_df, unknown_codes)

            progress.progress(45, text="데이터 병합 중...")
            merged_df = join_tables(demo_df, drug_df, event_df, assessment_df, drug_code, warnings_log)

            if len(merged_df) == 0:
                st.warning(f"⚠️ '{drug_code}'에 해당하는 유효 이상사례 0건 — 빈 보고서 생성")

            ll_df = build_line_listing(merged_df)
            n_cases = merged_df["KAERS_NO"].nunique() if len(merged_df) > 0 else 0

            # ── STEP 4: 공유 집계 (Word/Excel 일관성 보장) ────────
            progress.progress(60, text="공유 집계 계산 중...")
            from src.aggregator import compute_aggregates
            shared_stats = compute_aggregates(merged_df, ll_df)

            # ── STEP 5: 엑셀 생성 (공유 집계 전달) ────────────────
            progress.progress(70, text="원시자료 분석 엑셀 생성 중...")
            xlsx_bytes = build_excel(tmpdir, drug_code, drug_name_final, shared_stats=shared_stats)

            # ── STEP 6: Word 보고서 생성 ──────────────────────────
            progress.progress(85, text="Word 문서 작성 중...")
            data = ProcessedData(
                df_merged=merged_df,
                df_line_listing=ll_df,
                total_cases=n_cases,
                warnings=warnings_log,
                unknown_codes=unknown_codes,
                analysis_period=(start_date, end_date),
                drug_name=drug_name_final,
                drug_code=drug_code,
                company_name=company_name.strip(),
                ingredient_name=ingredient_name.strip(),
                approval_date=approval_date.strip(),
                approval_number=approval_number.strip(),
                has_assessment=assessment_df is not None,
            )
            docx_bytes = build_report(data)

            progress.progress(100, text="완료!")

        # 생성 결과를 세션에 보관하여 다운로드 버튼이 리렌더 후에도 유지되도록 처리
        st.session_state.generated_result = {
            "xlsx_bytes": xlsx_bytes,
            "docx_bytes": docx_bytes,
            "xlsx_name": f"{drug_name_final}_원시자료분석_{start_date}_{end_date}.xlsx",
            "docx_name": f"안전관리보고서_{drug_name_final}_{start_date}_{end_date}.docx",
            "n_events": len(ll_df),
            "n_cases": n_cases,
            "warnings_log": warnings_log,
            "unknown_codes": unknown_codes,
        }

    except ValidationError as e:
        progress.progress(0)
        st.error(f"❌ 검증 오류: {e}")
    except Exception as e:
        progress.progress(0)
        st.error(f"❌ 처리 오류: {e}")
        # 상세 스택트레이스는 expander에만 표시 — 배포 환경에서 stack trace 노출 방지
        import traceback
        with st.expander("🔧 기술 상세 (담당자 문의용)"):
            st.code(traceback.format_exc(), language="text")

# ── 다운로드 영역 (고정) ─────────────────────────────────────
# @st.fragment 으로 격리 — 다운로드 버튼 클릭 시 전체 스크립트가 rerun되지 않고
# 이 블록만 rerun 되므로 상단 업로드/조회 영역의 어떤 state 변화도 다운로드 버튼을
# 건드리지 못한다. (이전에 버튼이 사라지던 근본 원인 제거)
@st.fragment
def _render_downloads_and_edits(nonce: int) -> None:
    if not st.session_state.get("generated_result"):
        return
    result = st.session_state.generated_result

    st.success(f"✅ 생성 완료 — 이상사례 **{result['n_events']}건** / 사례 **{result['n_cases']}건**")

    st.subheader("⑤ 다운로드")
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button(
            label="📊 원시자료 분석 엑셀 다운로드",
            data=result["xlsx_bytes"],
            file_name=result["xlsx_name"],
            mime=MIME_XLSX,
            use_container_width=True,
            key=f"dl_xlsx_{nonce}",
        )
    with col_dl2:
        st.download_button(
            label="📄 안전관리보고서 Word 다운로드",
            data=result["docx_bytes"],
            file_name=result["docx_name"],
            mime=MIME_DOCX,
            use_container_width=True,
            key=f"dl_docx_{nonce}",
        )

    st.info(
        "📝 **다음 단계:** Word 파일을 열어 **노란색 하이라이트** 항목(연간 판매량 등)을 "
        "직접 입력하고, **[검토필요:]** 표시 항목을 검토하세요."
    )

    if result["warnings_log"]:
        with st.expander(f"⚠️ 처리 경고 {len(result['warnings_log'])}건"):
            for w in result["warnings_log"]:
                st.warning(w)
    if result["unknown_codes"]:
        with st.expander(f"🔴 미확인 코드 {len(result['unknown_codes'])}건"):
            for uc in result["unknown_codes"]:
                st.error(f"{uc['col']}: {uc['code']}")

    # ── ⑥ 수정본 업로드/보관 ─────────────────────────────────
    st.divider()
    st.subheader("⑥ 수정본 업로드 (선택)")
    st.caption(
        "노란색 하이라이트/검토필요 항목을 수정한 최종본 엑셀·워드 파일을 올려두면, "
        "새로고침 전까지 세션에 보관되어 다시 다운로드할 수 있습니다."
    )

    up_col1, up_col2 = st.columns(2)
    with up_col1:
        edited_xlsx = st.file_uploader(
            "수정본 엑셀 업로드 (.xlsx)",
            type=["xlsx", "xlsm", "xls"],
            key=f"edited_xlsx_up_{nonce}",
        )
        if edited_xlsx is not None:
            st.session_state.edited_files["xlsx"] = {
                "bytes": edited_xlsx.getvalue(),
                "name": edited_xlsx.name,
            }
        _saved_xlsx = st.session_state.edited_files.get("xlsx")
        if _saved_xlsx:
            st.success(f"📁 보관 중: **{_saved_xlsx['name']}**")
            st.download_button(
                label=f"⬇️ {_saved_xlsx['name']} 다시 다운로드",
                data=_saved_xlsx["bytes"],
                file_name=_saved_xlsx["name"],
                mime=MIME_XLSX,
                use_container_width=True,
                key=f"dl_edited_xlsx_{nonce}",
            )

    with up_col2:
        edited_docx = st.file_uploader(
            "수정본 워드 업로드 (.docx)",
            type=["docx", "doc"],
            key=f"edited_docx_up_{nonce}",
        )
        if edited_docx is not None:
            st.session_state.edited_files["docx"] = {
                "bytes": edited_docx.getvalue(),
                "name": edited_docx.name,
            }
        _saved_docx = st.session_state.edited_files.get("docx")
        if _saved_docx:
            st.success(f"📁 보관 중: **{_saved_docx['name']}**")
            st.download_button(
                label=f"⬇️ {_saved_docx['name']} 다시 다운로드",
                data=_saved_docx["bytes"],
                file_name=_saved_docx["name"],
                mime=MIME_DOCX,
                use_container_width=True,
                key=f"dl_edited_docx_{nonce}",
            )


if st.session_state.get("generated_result"):
    _render_downloads_and_edits(_n)
