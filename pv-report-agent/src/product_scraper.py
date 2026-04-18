"""
식약처 의약품 제품 정보 조회 모듈.

두 가지 조회 방식을 지원:
1. 공공데이터포털 REST API (DrugPrdtPrmsnInfoService07) — 안정적, 해외 서버 OK
2. nedrug.mfds.go.kr HTML 스크래핑 — 한국 외부 IP에서 차단될 수 있음 (fallback)

공공데이터포털 API를 우선 사용하고, 실패 시 nedrug 스크래핑으로 대체합니다.
"""
import json
import os
import re
import socket
import ssl
import time
import urllib.request
import urllib.parse
from dataclasses import dataclass, field

_DATA_GO_KR_BASE = "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07"


def _get_api_key() -> str:
    """공공데이터포털 API 키 조회.

    우선순위: 환경변수 `DATA_GO_KR_KEY` → Streamlit `st.secrets["DATA_GO_KR_KEY"]`.
    두 경로 모두 비어있으면 빈 문자열. `_call_api`가 이를 감지해 API_KEY_MISSING 에러 반환.
    """
    key = os.environ.get("DATA_GO_KR_KEY", "").strip()
    if key:
        return key
    try:
        import streamlit as st
        return str(st.secrets.get("DATA_GO_KR_KEY", "")).strip()
    except Exception:
        return ""


@dataclass
class ProductInfo:
    item_name: str = ""
    company_name: str = ""
    approval_date: str = ""
    item_seq: str = ""              # 품목기준코드 (= 의약품 코드)
    atc_code: str = ""
    ingredient_name: str = ""       # 한글 성분명
    ingredient_name_en: str = ""    # 영문 성분명
    standard_code: str = ""
    storage: str = ""
    use_period: str = ""
    approval_number: str = ""       # 허가번호 (품목허가번호)
    rare_drug_yn: str = ""          # 희귀의약품 여부
    narcotic_kind_code: str = ""    # 마약류 구분
    source_url: str = ""
    source_method: str = ""         # "api" 또는 "scrape"
    warnings: list = field(default_factory=list)


def _strip_code_prefix(text: str) -> str:
    """공공데이터포털 API 응답에서 '[M123456]' 형태의 코드 접두사 제거."""
    return re.sub(r"\[M\d+\]", "", text).strip()


def classify_api_error(err: str) -> str:
    """`_call_api`가 반환한 내부 에러 문자열을 사용자용 한글 메시지로 분류.

    정책:
      - 빈 문자열  → "" (오류 없음)
      - API_KEY_MISSING → 키 설정 안내
      - HTTP 429 / RateLimit → 호출 제한
      - HTTP 4xx 키/권한 관련 → 키 만료·승인 대기
      - 네트워크 / 타임아웃 → 연결 실패
      - 그 외  → 원문 유지 + 일반 안내
    """
    if not err:
        return ""
    if err == "API_KEY_MISSING":
        return (
            "공공데이터포털 API 키가 설정되지 않았습니다. "
            "`DATA_GO_KR_KEY` 환경변수 또는 `.streamlit/secrets.toml`을 확인하세요."
        )
    low = err.lower()
    if "429" in err or "rate" in low or "limit" in low:
        return "공공데이터포털 호출 제한(429). 잠시 후 다시 시도하세요."
    if any(k in err for k in ("401", "403", "SERVICE_KEY", "SERVICEKEY", "NO_OPENAPI_SERVICE_ERROR", "INVALID")):
        return "API 키가 만료되었거나 승인 대기 중입니다. 공공데이터포털에서 키 상태를 확인하세요."
    if any(k in low for k in ("timeout", "timed out", "connection", "urlerror", "oserror", "socket")):
        return f"공공데이터포털 연결 실패 — 네트워크를 확인하세요. ({err})"
    if "jsondecodeerror" in low:
        return f"API 응답 형식 오류 — 공공데이터포털 상태를 확인하세요. ({err})"
    return f"API 오류: {err}"


def _call_api(endpoint: str, params: dict, retries: int = 3, timeout: int = 15) -> tuple[dict | None, str]:
    """공공데이터포털 API 호출. (parsed_json, error_msg) 반환.

    error_msg 규약:
      - ""                 : 성공
      - "API_KEY_MISSING"  : 키 미설정 (env / st.secrets 모두 비어있음)
      - 그 외               : urllib / socket / json 예외 메시지
    """
    api_key = _get_api_key()
    if not api_key:
        return None, "API_KEY_MISSING"
    params = {**params, "serviceKey": api_key, "type": "json"}
    url = f"{_DATA_GO_KR_BASE}/{endpoint}?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"
    last_err = ""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
                return data, ""
        except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
            last_err = f"{type(e).__name__}: {e}"
            if attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))
        except json.JSONDecodeError as e:
            last_err = f"JSONDecodeError: {e}"
            break
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            break
    return None, last_err


def _extract_items(resp: dict) -> list[dict]:
    """공공데이터포털 API 응답에서 item 목록 추출."""
    body = resp.get("body", {})
    items = body.get("items", [])
    if isinstance(items, dict):
        item = items.get("item", [])
        return item if isinstance(item, list) else [item] if item else []
    if isinstance(items, list):
        return items
    return []


def _item_to_product_info(item: dict) -> ProductInfo:
    """API 응답의 단일 item → ProductInfo 변환."""
    info = ProductInfo(source_method="api")
    info.item_name = (item.get("ITEM_NAME") or "").strip()
    info.company_name = (item.get("ENTP_NAME") or "").strip()
    info.item_seq = (item.get("ITEM_SEQ") or "").strip()
    info.approval_date = (item.get("ITEM_PERMIT_DATE") or "").strip()
    info.approval_number = (item.get("PERMIT_KIND_CODE") or item.get("PRDUCT_PRMISN_NO") or "").strip()
    info.storage = (item.get("STORAGE_METHOD") or "").strip()
    info.use_period = (item.get("VALID_TERM") or "").strip()
    info.standard_code = (item.get("BAR_CODE") or "").strip()
    info.rare_drug_yn = (item.get("RARE_DRUG_YN") or "").strip()
    info.narcotic_kind_code = (item.get("NARCOTIC_KIND_CODE") or "").strip()

    main_ingr = _strip_code_prefix(item.get("MAIN_ITEM_INGR") or "")
    info.ingredient_name = main_ingr

    ingr_eng = _strip_code_prefix(item.get("INGR_NAME") or item.get("MAIN_INGR_ENG") or "")
    info.ingredient_name_en = ingr_eng

    atc = (item.get("ATC_CODE") or "").strip()
    info.atc_code = atc

    return info


def search_drug_by_name(item_name: str, num_of_rows: int = 10) -> tuple[list[ProductInfo], str]:
    """제품명으로 의약품 허가 목록 검색 (공공데이터포털 API).

    반환: (결과 리스트, 에러 문자열).
    에러 없으면 err="". API 실패 시 빈 리스트 + 분류된 err 메시지.
    """
    resp, err = _call_api("getDrugPrdtPrmsnInq07", {
        "item_name": item_name,
        "numOfRows": str(num_of_rows),
        "pageNo": "1",
    })
    if resp is None:
        return [], classify_api_error(err)
    items = _extract_items(resp)
    return [_item_to_product_info(it) for it in items], ""


def get_drug_detail_by_code(item_seq: str) -> tuple[ProductInfo | None, str]:
    """품목기준코드로 의약품 상세정보 조회 (공공데이터포털 API).

    반환: (ProductInfo|None, 에러 문자열).
    결과가 없으면 (None, "")로 반환 (에러와 구분).
    """
    resp, err = _call_api("getDrugPrdtPrmsnDtlInq06", {
        "item_seq": item_seq,
        "numOfRows": "1",
        "pageNo": "1",
    })
    if resp is None:
        return None, classify_api_error(err)
    items = _extract_items(resp)
    if not items:
        return None, ""
    return _item_to_product_info(items[0]), ""


def get_drug_ingredients(item_seq: str) -> list[dict]:
    """품목기준코드로 주성분 상세정보 조회 (공공데이터포털 API)."""
    resp, err = _call_api("getDrugPrdtMcpnDtlInq07", {
        "item_seq": item_seq,
        "numOfRows": "50",
        "pageNo": "1",
    })
    if resp is None:
        return []
    return _extract_items(resp)


def _enrich_ingredients(info: ProductInfo) -> None:
    """주성분 상세 API를 호출하여 ProductInfo의 성분명을 보강."""
    if not info.item_seq:
        return
    ingredients = get_drug_ingredients(info.item_seq)
    if not ingredients:
        return
    names_ko = []
    names_en = []
    for ingr in ingredients:
        ko = _strip_code_prefix(ingr.get("INGR_NAME") or ingr.get("MAIN_INGR_KOR") or "")
        en = _strip_code_prefix(ingr.get("INGR_ENG_NAME") or ingr.get("MAIN_INGR_ENG") or "")
        if ko:
            names_ko.append(ko)
        if en:
            names_en.append(en)
    if names_ko and not info.ingredient_name:
        info.ingredient_name = ", ".join(names_ko)
    if names_en and not info.ingredient_name_en:
        info.ingredient_name_en = ", ".join(names_en)


def lookup_product_info(item_seq: str = "", item_name: str = "") -> ProductInfo:
    """공공데이터포털 API로 제품 정보 조회. 품목기준코드 우선, 없으면 제품명 검색.

    API 실패 시 빈 ProductInfo(warnings에 분류된 한글 메시지 포함)를 반환.
    """
    info = ProductInfo(source_method="api")

    if item_seq:
        detail, err = get_drug_detail_by_code(item_seq)
        if detail and detail.item_name:
            detail.source_method = "api"
            _enrich_ingredients(detail)
            return detail
        if err:
            info.warnings.append(err)
            return info

    if item_name:
        results, err = search_drug_by_name(item_name, num_of_rows=5)
        if results:
            best = results[0]
            best.source_method = "api"
            _enrich_ingredients(best)
            return best
        if err:
            info.warnings.append(err)
            return info

    if not item_seq and not item_name:
        info.warnings.append("품목기준코드 또는 제품명을 입력하세요.")
    return info


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
