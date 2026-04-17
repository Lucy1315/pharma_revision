import io
import pytest
import pandas as pd
from pathlib import Path
from src.validator import ValidationError, read_file, load_and_validate

SAMPLE_DEMO = (
    "KAERS_NO|RPT_DL_DT|KAERS_GB|RPT_TY|QCK_RPT_YN|REPRT_CHANGE_CD|PTNT_SEX|PTNT_AGRDE|PTNT_OCCURSYMT_AGE\n"
    "K001|20210601|1|1|Y|2|1|5|45\n"
    "K002|20211201|1|2||2|2|6|70\n"
)

SAMPLE_DRUG = (
    "KAERS_NO|DRUG_SEQ|DRUG_GB|DRUG_CD|DRUG_ACTION\n"
    "K001|1|1|201506668|1\n"
    "K001|2|2|999999|4\n"
    "K002|1|1|201506668|2\n"
)

SAMPLE_EVENT = (
    "KAERS_NO|ADR_SEQ|ADR_MEDDRA_KOR_NM|ADR_MEDDRA_ENG_NM|ADR_RESULT_CODE|WHOART_ARRN\n"
    "K001|1|말초 신경 병증|Neuropathy peripheral|1|1313\n"
    "K002|1|세균성 감염|Infection bacterial|2|0738\n"
)


def write_tmp(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


class TestReadFile:
    def test_reads_utf8(self, tmp_path):
        p = write_tmp(tmp_path, "DEMO.txt", SAMPLE_DEMO)
        df = read_file(p)
        assert df is not None
        assert "KAERS_NO" in df.columns

    def test_raises_for_missing(self, tmp_path):
        from src.validator import ValidationError
        with pytest.raises(ValidationError):
            read_file(tmp_path / "NOTEXIST.txt")

    def test_pipe_separator(self, tmp_path):
        p = write_tmp(tmp_path, "DEMO.txt", SAMPLE_DEMO)
        df = read_file(p)
        assert len(df) == 2


class TestLoadAndValidate:
    def test_loads_all_four_files(self, tmp_path):
        demo = write_tmp(tmp_path, "DEMO.txt", SAMPLE_DEMO)
        drug = write_tmp(tmp_path, "DRUG.txt", SAMPLE_DRUG)
        event = write_tmp(tmp_path, "EVENT.txt", SAMPLE_EVENT)
        assess = write_tmp(tmp_path, "ASSESSMENT.txt",
                           "KAERS_NO|DRUG_SEQ|ADR_SEQ|EVALT_RESULT_CODE\nK001|1|1|2\n")
        demo_df, drug_df, event_df, assess_df, warns = load_and_validate(
            demo, drug, event, assess, "20200101", "20221231"
        )
        assert len(demo_df) == 2
        assert len(drug_df) == 3
        assert assess_df is not None

    def test_assessment_optional(self, tmp_path):
        demo = write_tmp(tmp_path, "DEMO.txt", SAMPLE_DEMO)
        drug = write_tmp(tmp_path, "DRUG.txt", SAMPLE_DRUG)
        event = write_tmp(tmp_path, "EVENT.txt", SAMPLE_EVENT)
        demo_df, drug_df, event_df, assess_df, warns = load_and_validate(
            demo, drug, event, None, "20200101", "20221231"
        )
        assert assess_df is None

    def test_raises_for_missing_required_file(self, tmp_path):
        drug = write_tmp(tmp_path, "DRUG.txt", SAMPLE_DRUG)
        event = write_tmp(tmp_path, "EVENT.txt", SAMPLE_EVENT)
        with pytest.raises((ValidationError, Exception)):
            load_and_validate(
                tmp_path / "MISSING.txt", drug, event, None, "20200101", "20221231"
            )
