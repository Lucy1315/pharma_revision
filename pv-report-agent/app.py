import io
import zipfile
import tempfile
from pathlib import Path

import streamlit as st

from src.validator import load_and_validate, ValidationError
from src.transformer import filter_invalid, transform_demo, transform_drug, transform_event, transform_assessment
from src.joiner import detect_drug_code, join_tables, build_line_listing
from src.report_builder import build_report
from src.excel_builder import build_excel
from src.product_scraper import scrape_product_info, ProductInfo
from src.types import ProcessedData

st.set_page_config(page_title="PV 보고서 자동화", page_icon="📋", layout="wide")

# ── 헤더 ─────────────────────────────────────────────────────
st.title("📋 안전관리책임자 보고서 자동 생성")
st.caption("식약처 품목갱신 가이드라인(99~115p) 기반 Word 문서 + 원시자료 분석 엑셀 자동 생성")

# ── 워크플로 안내 ────────────────────────────────────────────
with st.expander("📌 사용 방법", expanded=False):
    st.markdown("""
    1. **원시자료 ZIP** 업로드 — DEMO/DRUG/EVENT/ASSESSMENT.txt 포함 ZIP
    2. **제품 정보 URL** 입력 — [식약처 의약품통합정보시스템](https://nedrug.mfds.go.kr) 제품 상세페이지 URL
    3. **분석 기간** 및 추가 정보 확인 후 **보고서 생성** 클릭
    4. 생성된 **원시자료 분석 엑셀** 및 **안전관리보고서 Word** 다운로드
    5. Word 초안의 노란색 항목을 직접 수정하여 최종화
    """)

# ── 입력 영역 ────────────────────────────────────────────────
col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.subheader("① 원시자료 업로드")
    zip_file = st.file_uploader(
        "원시자료 ZIP 파일",
        type=["zip"],
        help="DEMO.txt, DRUG.txt, EVENT.txt가 필수입니다. ASSESSMENT.txt는 선택사항."
    )

    st.subheader("② 제품 정보 URL")
    nedrug_url = st.text_input(
        "식약처 의약품통합정보시스템 URL",
        placeholder="https://nedrug.mfds.go.kr/pbp/CCBBB01/getItemDetailCache?cacheSeq=...",
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
                else:
                    st.warning("제품명을 찾지 못했습니다. 아래에서 직접 입력하세요.")
            except Exception as e:
                st.error(f"제품 정보 조회 실패: {e}")

with col_right:
    st.subheader("③ 분석 기간")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.text_input("시작일 (YYYY-MM-DD)", value="2020-09-21")
    with col2:
        end_date = st.text_input("종료일 (YYYY-MM-DD)", value="2024-06-30")

    st.subheader("④ 제품 정보 확인/수정")
    drug_code_input = st.text_input(
        "의약품 코드 (품목기준코드)",
        value=product.item_seq if product else "",
        placeholder="자동 감지 또는 직접 입력"
    )
    drug_name = st.text_input(
        "제품명",
        value=product.item_name if product else "",
    )
    company_name = st.text_input(
        "회사명",
        value=product.company_name if product else "",
    )
    ingredient_name = st.text_input(
        "성분명",
        value=product.ingredient_name if product else "",
    )
    approval_date = st.text_input(
        "허가일",
        value=product.approval_date if product else "",
    )
    approval_number = st.text_input(
        "허가번호",
        value=product.item_seq if product else "",
    )

# ── 생성 버튼 ────────────────────────────────────────────────
st.divider()
ready = zip_file is not None
if not ready:
    st.info("원시자료 ZIP 파일을 업로드하면 보고서 생성이 활성화됩니다.")

if st.button("🚀 보고서 생성", type="primary", disabled=not ready):
    progress = st.progress(0, text="ZIP 파일 압축 해제 중...")
    warnings_log: list[str] = []

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # ── STEP 1: ZIP 압축 해제 ──────────────────────────
            with zipfile.ZipFile(io.BytesIO(zip_file.getvalue())) as zf:
                zf.extractall(tmpdir)

            # 평탄화: 서브디렉토리 내 txt 파일을 최상위로 이동
            for txt in list(tmpdir.rglob("*.txt")):
                if txt.parent != tmpdir:
                    dest = tmpdir / txt.name
                    if not dest.exists():
                        txt.rename(dest)

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

            progress.progress(25, text="원시자료 분석 엑셀 생성 중...")

            # ── STEP 3: 엑셀 생성 ──────────────────────────────
            drug_name_final = drug_name.strip() or drug_code
            xlsx_bytes = build_excel(tmpdir, drug_code, drug_name_final)
            progress.progress(50, text="Word 보고서 생성 중...")

            # ── STEP 4: Word 보고서 생성 ───────────────────────
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

            progress.progress(65, text="데이터 병합 중...")
            merged_df = join_tables(demo_df, drug_df, event_df, assessment_df, drug_code, warnings_log)

            if len(merged_df) == 0:
                st.warning(f"⚠️ '{drug_code}'에 해당하는 유효 이상사례 0건 — 빈 보고서 생성")

            ll_df = build_line_listing(merged_df)
            n_cases = merged_df["KAERS_NO"].nunique() if len(merged_df) > 0 else 0

            progress.progress(80, text="Word 문서 작성 중...")
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
