import pandas as pd
import pytest
from src.transformer import (
    PTNT_SEX_MAP, PTNT_AGRDE_MAP, ADR_RESULT_MAP,
    DRUG_GB_MAP, EVALT_RESULT_MAP, RPT_TY_MAP,
    filter_invalid, transform_demo, transform_drug, transform_event,
    detect_period,
)


# ── filter_invalid ─────────────────────────────────────────
class TestFilterInvalid:
    def test_removes_reprt_change_cd_1(self):
        df = pd.DataFrame({"KAERS_NO": ["A", "B", "C"], "REPRT_CHANGE_CD": ["1", "2", None]})
        result, removed = filter_invalid(df)
        assert removed == 1
        assert "A" not in result["KAERS_NO"].values

    def test_keeps_all_when_no_invalid(self):
        df = pd.DataFrame({"KAERS_NO": ["A", "B"], "REPRT_CHANGE_CD": ["2", None]})
        result, removed = filter_invalid(df)
        assert removed == 0
        assert len(result) == 2

    def test_no_reprt_change_cd_column(self):
        df = pd.DataFrame({"KAERS_NO": ["A", "B"]})
        result, removed = filter_invalid(df)
        assert removed == 0
        assert len(result) == 2


# ── detect_period ──────────────────────────────────────────
class TestDetectPeriod:
    def test_returns_min_max(self):
        df = pd.DataFrame({"RPT_DL_DT": ["20210101", "20200501", "20221231"]})
        start, end = detect_period(df)
        assert start == "20200501"
        assert end == "20221231"

    def test_skips_non_date_values(self):
        df = pd.DataFrame({"RPT_DL_DT": ["20210101", "N/A", None, "20220601"]})
        start, end = detect_period(df)
        assert start == "20210101"
        assert end == "20220601"

    def test_missing_column_returns_empty(self):
        df = pd.DataFrame({"OTHER": ["x"]})
        start, end = detect_period(df)
        assert start == "" and end == ""

    def test_all_invalid_returns_empty(self):
        df = pd.DataFrame({"RPT_DL_DT": [None, "N/A", ""]})
        start, end = detect_period(df)
        assert start == "" and end == ""


# ── transform_demo ─────────────────────────────────────────
class TestTransformDemo:
    def _make_demo(self, **kwargs):
        base = {
            "KAERS_NO": ["K001"],
            "PTNT_SEX": ["1"],
            "PTNT_AGRDE": ["5"],
            "RPT_TY": ["1"],
            "QCK_RPT_YN": ["Y"],
            "RPT_DL_DT": ["20210601"],
            "REPRT_CHANGE_CD": ["2"],
        }
        base.update(kwargs)
        return pd.DataFrame(base)

    def test_sex_mapping(self):
        df = transform_demo(self._make_demo(), [])
        assert df.iloc[0]["PTNT_SEX_NM"] == "남"

    def test_unknown_sex_code_recorded(self):
        unknown = []
        df = transform_demo(self._make_demo(PTNT_SEX=["9"]), unknown)
        assert any(u["col"] == "PTNT_SEX" for u in unknown)

    def test_is_quick_true(self):
        df = transform_demo(self._make_demo(QCK_RPT_YN=["Y"]), [])
        assert df.iloc[0]["IS_QUICK"] is True or df.iloc[0]["IS_QUICK"] == True

    def test_rpt_dl_dt_formatted(self):
        df = transform_demo(self._make_demo(RPT_DL_DT=["20210601"]), [])
        assert df.iloc[0]["RPT_DL_DT_FMT"] == "2021-06-01"


# ── transform_drug ─────────────────────────────────────────
class TestTransformDrug:
    def test_drug_gb_mapping(self):
        df = pd.DataFrame({"DRUG_GB": ["1"], "DRUG_ACTION": ["1"]})
        result = transform_drug(df, [])
        assert result.iloc[0]["DRUG_GB_NM"] == "의심"

    def test_drug_action_mapping(self):
        df = pd.DataFrame({"DRUG_GB": ["2"], "DRUG_ACTION": ["2"]})
        result = transform_drug(df, [])
        assert result.iloc[0]["DRUG_ACTION_NM"] == "투여량감소"


# ── transform_event ────────────────────────────────────────
class TestTransformEvent:
    def _make_event(self, **kwargs):
        base = {
            "KAERS_NO": ["K001"],
            "ADR_SEQ": ["1"],
            "ADR_MEDDRA_KOR_NM": ["말초 신경 병증"],
            "ADR_MEDDRA_ENG_NM": ["Neuropathy peripheral"],
            "ADR_RESULT_CODE": ["1"],
            "WHOART_ARRN": ["1313"],
        }
        base.update(kwargs)
        return pd.DataFrame(base)

    def test_adr_result_mapping(self):
        df = transform_event(self._make_event(), [])
        assert df.iloc[0]["ADR_RESULT_NM"] == "회복됨"

    def test_soc_mapping(self):
        df = transform_event(self._make_event(WHOART_ARRN=["0401"]), [])
        assert "중추" in df.iloc[0]["SOC_NM"] or "신경" in df.iloc[0]["SOC_NM"]

    def test_seriousness_from_se_death(self):
        df = self._make_event()
        df["SE_DEATH"] = "Y"
        result = transform_event(df, [])
        assert result.iloc[0]["IS_SERIOUS"] == True

    def test_non_serious_when_no_se(self):
        df = transform_event(self._make_event(), [])
        assert df.iloc[0]["IS_SERIOUS"] == False


# ── 코드 매핑 완전성 체크 ──────────────────────────────────
class TestCodeMaps:
    @pytest.mark.parametrize("code,expected", [
        ("1", "남"), ("2", "여"),
    ])
    def test_sex_map(self, code, expected):
        assert PTNT_SEX_MAP[code] == expected

    @pytest.mark.parametrize("code,expected", [
        ("1", "확실함"), ("6", "평가불가"),
    ])
    def test_evalt_map(self, code, expected):
        assert EVALT_RESULT_MAP[code] == expected

    def test_all_drug_gb_codes_present(self):
        for code in ["1", "2", "3", "4"]:
            assert code in DRUG_GB_MAP
