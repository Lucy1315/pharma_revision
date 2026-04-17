"""
식약처 의약품통합정보시스템(nedrug)에서 제품 정보를 스크래핑.
URL 형식: https://nedrug.mfds.go.kr/pbp/CCBBB01/getItemDetailCache?cacheSeq=...

주의: nedrug는 한국 외부 IP에서 접속 차단/타임아웃될 수 있음 (ECONNRESET).
실패 시 URL의 cacheSeq에서 품목기준코드만 추출되며, 나머지 필드는 수동 입력 필요.
"""
import json
import re
import socket
import ssl
import time
import urllib.request
import urllib.parse
from dataclasses import dataclass, field


@dataclass
class ProductInfo:
    item_name: str = ""
    company_name: str = ""
    approval_date: str = ""
    item_seq: str = ""              # 품목기준코드 (= 의약품 코드)
    atc_code: str = ""
    ingredient_name: str = ""       # 한글 성분명 (ingrMainName JSON 필드)
    ingredient_name_en: str = ""    # 영문 성분명 (ATC코드 괄호)
    standard_code: str = ""
    storage: str = ""
    use_period: str = ""
    source_url: str = ""
    warnings: list = field(default_factory=list)


def _fetch_html(url: str, retries: int = 3, timeout: int = 20) -> tuple[str, str]:
    """HTML 다운로드. (html, error_msg) 반환. 실패 시 html은 빈 문자열."""
    last_err = ""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        "Accept-Encoding": "identity",           # gzip 비활성화 (decode 단순화)
        "Connection": "close",                   # keep-alive 회피
        "Referer": "https://nedrug.mfds.go.kr/",
    }
    ctx = ssl.create_default_context()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                return r.read().decode("utf-8", errors="replace"), ""
        except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
            last_err = f"{type(e).__name__}: {e}"
            if attempt < retries - 1:
                time.sleep(1.0 * (attempt + 1))  # 1초, 2초 backoff
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            break
    return "", last_err


def scrape_product_info(url: str) -> ProductInfo:
    """nedrug URL에서 제품 정보를 파싱하여 ProductInfo 반환."""
    info = ProductInfo(source_url=url)

    # cacheSeq에서 품목기준코드 추출 (네트워크 실패해도 확보됨)
    seq_match = re.search(r"cacheSeq=(\d+)", url)
    if seq_match:
        info.item_seq = seq_match.group(1)

    html, err = _fetch_html(url)
    if not html:
        # 한국 정부 사이트는 해외 IP에서 ECONNRESET 나는 경우가 많음
        info.warnings.append(
            f"nedrug 접속 실패 ({err}). "
            "해외 서버에서 차단되었을 가능성이 있습니다. "
            "품목기준코드는 URL에서 자동 추출되었으니 제품명/회사명 등만 수동 입력하시면 보고서 생성이 가능합니다."
        )
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

    # ATC 코드에서 영문 성분명 추출 (예: "L01XG01 (bortezomib)" → "bortezomib")
    atc_raw = field_map.get("ATC코드", "")
    info.atc_code = atc_raw
    atc_ingr = re.search(r"\(([^)]+)\)", atc_raw)
    if atc_ingr:
        info.ingredient_name_en = atc_ingr.group(1)

    # 한글 성분명: ingrMainName JSON 필드에서 추출
    # 형식: {"ingrMainName":"유효성분 : 보르테조밉삼합체", ...}
    ingr_json = re.search(r'\{[^{}]*"ingrMainName"[^{}]*\}', html)
    if ingr_json:
        try:
            obj = json.loads(ingr_json.group())
            raw_ingr = obj.get("ingrMainName", "")
            info.ingredient_name = re.sub(r"^유효성분\s*:\s*", "", raw_ingr).strip()
        except (json.JSONDecodeError, Exception):
            pass

    # ingredient_name이 비어있으면 영문으로 fallback
    if not info.ingredient_name:
        info.ingredient_name = info.ingredient_name_en

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
