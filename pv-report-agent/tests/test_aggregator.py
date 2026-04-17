import pandas as pd
from src.aggregator import compute_aggregates


def _make_merged():
    """transform+join 이후 merged DataFrame 모양"""
    return pd.DataFrame({
        "KAERS_NO": ["K1", "K1", "K2", "K3"],
        "PTNT_SEX_NM": ["남", "남", "여", "남"],
        "PTNT_AGRDE_NM": ["19~65세", "19~65세", "65세이상", "19~65세"],
        "RPT_TY_NM": ["자발적보고", "자발적보고", "시험/연구에서보고", "자발적보고"],
        "IS_QUICK": [False, False, True, True],
        "SOC_NM": ["중추/말초신경계 장애", "전신계 장애", "감염 및 기생충 침입", "중추/말초신경계 장애"],
        "ADR_MEDDRA_KOR_NM": ["말초 신경 병증", "발열", "세균성 감염", "말초 신경 병증"],
        "IS_SERIOUS": [False, True, True, False],
    })


def _make_ll():
    return pd.DataFrame({
        "번호": [1, 2, 3, 4],
        "KAERS번호": ["K1", "K1", "K2", "K3"],
        "중대성": ["N", "Y", "Y", "N"],
    })


class TestComputeAggregates:
    def test_basic_counts(self):
        stats = compute_aggregates(_make_merged(), _make_ll())
        assert stats["n_events"] == 4
        assert stats["n_cases"] == 3

    def test_sex_split(self):
        stats = compute_aggregates(_make_merged(), _make_ll())
        # K1 남, K2 여, K3 남 → 남 2 / 여 1
        assert stats["male"] == 2
        assert stats["female"] == 1

    def test_seriousness_from_line_listing(self):
        stats = compute_aggregates(_make_merged(), _make_ll())
        assert stats["n_serious"] == 2
        assert stats["n_non_serious"] == 2

    def test_age_counts(self):
        stats = compute_aggregates(_make_merged(), _make_ll())
        ages = stats["age_counts"]
        # K1: 19~65세, K2: 65세이상, K3: 19~65세 → 19~65세 2 / 65세이상 1
        assert ages["19~65세"] == 2
        assert ages["65세이상"] == 1

    def test_rpt_cross_structure(self):
        stats = compute_aggregates(_make_merged(), _make_ll())
        rpt = stats["rpt_cross"]
        assert "신속보고" in rpt.columns or "일반보고" in rpt.columns
        assert "자발적보고" in rpt.index or "시험/연구에서보고" in rpt.index

    def test_n_quick(self):
        stats = compute_aggregates(_make_merged(), _make_ll())
        # K2 신속(True), K3 신속(True) → 사례 단위로 2
        assert stats["n_quick"] == 2

    def test_soc_summary_has_correct_top(self):
        stats = compute_aggregates(_make_merged(), _make_ll())
        soc = stats["soc_summary"]
        # 중추/말초신경계 장애 2건이 top
        assert soc.iloc[0]["SOC_NM"] == "중추/말초신경계 장애"
        assert soc.iloc[0]["건수"] == 2

    def test_empty_input_returns_zeros(self):
        empty_m = pd.DataFrame(columns=_make_merged().columns)
        empty_ll = pd.DataFrame(columns=_make_ll().columns)
        stats = compute_aggregates(empty_m, empty_ll)
        assert stats["n_events"] == 0
        assert stats["n_cases"] == 0
        assert stats["male"] == 0
        assert stats["female"] == 0

    def test_top3_returns_at_most_three(self):
        stats = compute_aggregates(_make_merged(), _make_ll())
        assert len(stats["top3"]) <= 3
        # 가장 흔한 '말초 신경 병증' 2건이 top
        assert stats["top3"].index[0] == "말초 신경 병증"
