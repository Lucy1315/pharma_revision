"""
식약처 의약품통합정보시스템(nedrug)에서 제품 정보를 스크래핑.
URL 형식: https://nedrug.mfds.go.kr/pbp/CCBBB01/getItemDetailCache?cacheSeq=...
"""
import re
import urllib.request
import urllib.parse
from dataclasses import dataclass, field


@dataclass
class ProductInfo:
    item_name: str = ""
    company_name: str = ""
    approval_date: str = ""
    item_seq: str = ""          # 품목기준코드 (= 의약품 코드)
    atc_code: str = ""
    ingredient_name: str = ""   # ATC코드에서 추출한 영문 성분명
    standard_code: str = ""
    storage: str = ""
    use_period: str = ""
    source_url: str = ""
    warnings: list = field(default_factory=list)


def scrape_product_info(url: str) -> ProductInfo:
    """nedrug URL에서 제품 정보를 파싱하여 ProductInfo 반환."""
    info = ProductInfo(source_url=url)

    # cacheSeq에서 품목기준코드 추출 (fallback)
    seq_match = re.search(r"cacheSeq=(\d+)", url)
    if seq_match:
        info.item_seq = seq_match.group(1)

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "ko-KR,ko;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        info.warnings.append(f"nedrug 접속 실패: {e}")
        return info

    # th/td 테이블에서 필드 추출
    table_rows = re.findall(
        r'<th scope="row">([^<]+)</th>\s*<td[^>]*>(.*?)</td>',
        html, re.DOTALL
    )
    field_map: dict[str, str] = {}
    for k, v in table_rows:
        clean_v = re.sub(r"<[^>]+>", "", v).strip()
        clean_v = re.sub(r"\s+", " ", clean_v)
        field_map[k.strip()] = clean_v

    info.item_name    = field_map.get("제품명", "")
    info.company_name = field_map.get("업체명", "")
    info.approval_date = field_map.get("허가일", "")
    info.standard_code = field_map.get("표준코드", "")
    info.storage       = field_map.get("저장방법", "")
    info.use_period    = field_map.get("사용기간", "")

    if field_map.get("품목기준코드"):
        info.item_seq = field_map["품목기준코드"].strip()

    # ATC 코드에서 성분명 추출 (예: "L01XG01 (bortezomib)" → "bortezomib")
    atc_raw = field_map.get("ATC코드", "")
    info.atc_code = atc_raw
    ingr_match = re.search(r"\(([^)]+)\)", atc_raw)
    if ingr_match:
        info.ingredient_name = ingr_match.group(1)

    # H1에서 품목명 보완
    if not info.item_name:
        h1_match = re.search(r"<strong>([가-힣A-Za-z0-9\s\.\(\)]+)</strong>", html)
        if h1_match:
            info.item_name = h1_match.group(1).strip()

    return info


def extract_drug_code_from_url(url: str) -> str:
    """URL에서 품목기준코드(의약품 코드) 추출."""
    seq_match = re.search(r"cacheSeq=(\d+)", url)
    return seq_match.group(1) if seq_match else ""
