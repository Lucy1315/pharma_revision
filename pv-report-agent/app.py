import io
import zipfile
import tempfile
from pathlib import Path

import streamlit as st

from src.validator import load_and_validate, ValidationError
from src.transformer import filter_invalid, transform_demo, transform_drug, transform_event, transform_assessment, detect_period
from src.joiner import detect_drug_code, join_tables, build_line_listing
from src.report_builder import build_report
from src.excel_builder import build_excel
from src.product_scraper import scrape_product_info, ProductInfo
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

st.set_page_config(page_title="PV 보고서 자동화", page_icon="📋", layout="wide")

# ── 상태 초기화용 nonce (위젯 key를 바꿔 완전 초기화) ─────────
if "nonce" not in st.session_state:
    st.session_state.nonce = 0
_n = st.session_state.nonce

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
            "필수: DEMO.txt, DRUG.txt, EVENT.txt / 선택: ASSESSMENT.txt, DRUG1/2/3.txt"
        )
    )

    st.subheader("② 제품 정보 URL")
    nedrug_url = st.text_input(
        "식약처 의약품통합정보시스템 URL",
        placeholder="https://nedrug.mfds.go.kr/pbp/CCBBB01/getItemDetailCache?cacheSeq=...",
        key=f"nedrug_url_{_n}",
        help="nedrug.mfds.go.kr 제품 상세페이지 URL을 붙여넣으세요."
    )

    # URL에서 제품 정보 자동 조회
    product: ProductInfo | None = None
    if nedrug_url and nedrug_url.startswith("http"):
        with st.spinner("제품 정보 조회 중..."):
            try:
                product = scrape_product_info(nedrug_url)
                if product.item_name:
                    st.success(f"✅ 제품 정보 조회 완료: **{product.item_name}**")
                elif product.item_seq:
                    st.info(
                        f"ℹ️ 품목기준코드 **{product.item_seq}** 는 URL에서 자동 추출됐습니다. "
                        "제품명/회사명/허가일은 오른쪽에서 직접 입력하세요."
                    )
                else:
                    st.warning("제품 정보를 가져오지 못했습니다. URL 형식을 확인하거나 오른쪽에서 직접 입력하세요.")
                for w in product.warnings:
                    st.warning(w)
            except Exception as e:
                st.error(f"제품 정보 조회 실패: {e}")

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
        start_date = st.text_input("시작일 (YYYY-MM-DD)", value=_auto_start or "2020-09-21",
                                   key=f"start_{_n}",
                                   help="업로드된 DEMO.txt에서 자동 감지")
    with col2:
        end_date = st.text_input("종료일 (YYYY-MM-DD)", value=_auto_end or "2024-06-30",
                                 key=f"end_{_n}",
                                 help="업로드된 DEMO.txt에서 자동 감지")

    st.subheader("④ 제품 정보 확인/수정")
    drug_code_input = st.text_input(
        "의약품 코드 (품목기준코드)",
        value=product.item_seq if product else "",
        placeholder="자동 감지 또는 직접 입력",
        key=f"drug_code_{_n}",
    )
    drug_name = st.text_input(
        "제품명",
        value=product.item_name if product else "",
        key=f"drug_name_{_n}",
    )
    company_name = st.text_input(
        "회사명",
        value=product.company_name if product else "",
        key=f"company_{_n}",
    )
    ingredient_name = st.text_input(
        "성분명",
        value=product.ingredient_name if product else "",
        key=f"ingredient_{_n}",
    )
    approval_date = st.text_input(
        "허가일",
        value=product.approval_date if product else "",
        key=f"appr_date_{_n}",
    )
    approval_number = st.text_input(
        "허가번호",
        value=product.item_seq if product else "",
        key=f"appr_num_{_n}",
    )

# ── 업로드 상태 ─────────────────────────────────────────────
st.divider()
ready = bool(uploaded_files)
if ready:
    _n = len(uploaded_files)
    _names = ", ".join(f.name for f in uploaded_files)
    st.success(f"📂 {_n}개 파일 업로드됨: {_names}")
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

        # ── STEP 5: 결과 표시 ─────────────────────────────────
        st.success(
            f"✅ 생성 완료 — 이상사례 **{len(ll_df)}건** / 사례 **{n_cases}건**"
        )

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                label="📊 원시자료 분석 엑셀 다운로드",
                data=xlsx_bytes,
                file_name=f"{drug_name_final}_원시자료분석_{start_date}_{end_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with col_dl2:
            st.download_button(
                label="📄 안전관리보고서 Word 다운로드",
                data=docx_bytes,
                file_name=f"안전관리보고서_{drug_name_final}_{start_date}_{end_date}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )

        # ── 다음 단계 안내 ─────────────────────────────────────
        st.info(
            "📝 **다음 단계:** Word 파일을 열어 **노란색 하이라이트** 항목(연간 판매량 등)을 "
            "직접 입력하고, **[검토필요:]** 표시 항목을 검토하세요."
        )

        # 경고 로그
        if warnings_log:
            with st.expander(f"⚠️ 처리 경고 {len(warnings_log)}건"):
                for w in warnings_log:
                    st.warning(w)
        if unknown_codes:
            with st.expander(f"🔴 미확인 코드 {len(unknown_codes)}건"):
                for uc in unknown_codes:
                    st.error(f"{uc['col']}: {uc['code']}")

    except ValidationError as e:
        progress.progress(0)
        st.error(f"❌ 검증 오류: {e}")
    except Exception as e:
        progress.progress(0)
        st.error(f"❌ 처리 오류: {e}")
        raise
