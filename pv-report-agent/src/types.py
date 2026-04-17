from dataclasses import dataclass, field
from typing import Optional
import pandas as pd


@dataclass
class ProcessedData:
    df_merged: pd.DataFrame
    df_line_listing: pd.DataFrame
    total_cases: int
    warnings: list[str] = field(default_factory=list)
    unknown_codes: list[dict] = field(default_factory=list)
    analysis_period: tuple[str, str] = ("", "")
    drug_name: str = ""
    drug_code: str = ""
    company_name: str = ""
    ingredient_name: str = ""
    approval_date: str = ""
    approval_number: str = ""
    has_assessment: bool = False
