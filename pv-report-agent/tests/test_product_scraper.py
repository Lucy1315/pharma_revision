import io
import json
import os
import urllib.request

import pytest

from src.product_scraper import (
    ProductInfo,
    _call_api,
    _extract_items,
    _get_api_key,
    _item_to_product_info,
    extract_drug_code_from_url,
    get_drug_detail_by_code,
    lookup_product_info,
    scrape_product_info,
    search_drug_by_name,
)


class _FakeResponse:
    """urlopen을 대체하는 컨텍스트 매니저 — JSON 응답 주입용."""

    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _patch_api(monkeypatch, payload, key="TEST_KEY"):
    """_call_api가 키를 가지고 urlopen 호출 시 payload를 반환하도록 패치."""
    monkeypatch.setenv("DATA_GO_KR_KEY", key)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: _FakeResponse(payload))
    monkeypatch.setattr(urllib.request, "Request", lambda *a, **kw: None)


def _patch_api_error(monkeypatch, exc, key="TEST_KEY"):
    """_call_api 호출 시 예외가 발생하도록 패치."""
    monkeypatch.setenv("DATA_GO_KR_KEY", key)
    monkeypatch.setattr(urllib.request, "Request", lambda *a, **kw: None)

    def _raise(*a, **kw):
        raise exc

    monkeypatch.setattr(urllib.request, "urlopen", _raise)


class TestExtractDrugCodeFromUrl:
    def test_extracts_cache_seq(self):
        url = "https://nedrug.mfds.go.kr/pbp/CCBBB01/getItemDetailCache?cacheSeq=201702641aupdateTs2026-04-10"
        assert extract_drug_code_from_url(url) == "201702641"

    def test_returns_empty_for_no_match(self):
        assert extract_drug_code_from_url("https://example.com/page") == ""

    def test_empty_string_input(self):
        assert extract_drug_code_from_url("") == ""


class TestScrapeProductInfoParsing:
    """HTML 파싱 로직 단위 테스트 (실제 HTTP 요청 없이 mock HTML 사용)"""

    MOCK_HTML = """
    <table>
      <tr><th scope="row">제품명</th><td>테스트주사제5mg</td></tr>
      <tr><th scope="row">업체명</th><td>(주)테스트제약</td></tr>
      <tr><th scope="row">허가일</th><td>2020-03-15</td></tr>
      <tr><th scope="row">품목기준코드</th><td>202000001</td></tr>
      <tr><th scope="row">ATC코드</th><td>L01XG01 (testmab)</td></tr>
    </table>
    <script>{"ingrMainName":"유효성분 : 테스트성분한글","ingrTotqy":"5"}</script>
    """

    def test_parse_mock_html(self, monkeypatch):
        import urllib.request
        import io

        class MockResponse:
            def read(self):
                return self.MOCK_HTML.encode("utf-8")
            def __enter__(self): return self
            def __exit__(self, *a): pass
            MOCK_HTML = TestScrapeProductInfoParsing.MOCK_HTML

        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: MockResponse())
        monkeypatch.setattr(urllib.request, "Request", lambda *a, **kw: None)

        # 내부 파싱 로직만 직접 테스트
        import re
        html = TestScrapeProductInfoParsing.MOCK_HTML
        rows = re.findall(r'<th scope="row">([^<]+)</th>\s*<td[^>]*>(.*?)</td>', html, re.DOTALL)
        field_map = {k.strip(): re.sub(r"<[^>]+>", "", v).strip() for k, v in rows}

        assert field_map["제품명"] == "테스트주사제5mg"
        assert field_map["업체명"] == "(주)테스트제약"
        assert field_map["허가일"] == "2020-03-15"
        assert field_map["품목기준코드"] == "202000001"

        atc = field_map["ATC코드"]
        ingr_match = re.search(r"\(([^)]+)\)", atc)
        assert ingr_match and ingr_match.group(1) == "testmab"

        # 한글 성분명: ingrMainName JSON 파싱
        import json
        ingr_json = re.search(r'\{[^{}]*"ingrMainName"[^{}]*\}', html)
        assert ingr_json is not None
        obj = json.loads(ingr_json.group())
        ko_ingr = re.sub(r"^유효성분\s*:\s*", "", obj["ingrMainName"]).strip()
        assert ko_ingr == "테스트성분한글"

    def test_product_info_dataclass_defaults(self):
        p = ProductInfo()
        assert p.item_name == ""
        assert p.company_name == ""
        assert p.ingredient_name == ""
        assert p.ingredient_name_en == ""
        assert p.warnings == []

    def test_warning_on_network_failure(self, monkeypatch):
        import urllib.request
        monkeypatch.setattr(urllib.request, "Request", lambda *a, **kw: None)
        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: (_ for _ in ()).throw(ConnectionError("timeout")))

        p = scrape_product_info("https://nedrug.mfds.go.kr/test?cacheSeq=123")
        assert len(p.warnings) > 0
        assert "123" == p.item_seq  # URL에서 추출한 코드는 남아야 함


# ══════════════════════════════════════════════════════════════
#  공공데이터포털 API 경로 (mock) — ISSUE-005 회귀 방지
# ══════════════════════════════════════════════════════════════

class TestGetApiKey:
    """환경변수 우선, st.secrets fallback."""

    def test_env_wins(self, monkeypatch):
        monkeypatch.setenv("DATA_GO_KR_KEY", "from_env")
        assert _get_api_key() == "from_env"

    def test_empty_when_missing(self, monkeypatch):
        monkeypatch.delenv("DATA_GO_KR_KEY", raising=False)
        # streamlit 가 없는 경우는 `import streamlit` 실패 → ""
        # streamlit 이 있어도 secrets 미설정이면 "" (보수적 가정)
        key = _get_api_key()
        assert isinstance(key, str)
        # 최소한 하드코딩된 키가 아님을 검증
        assert "78dd2db3fe72" not in key

    def test_env_whitespace_stripped(self, monkeypatch):
        monkeypatch.setenv("DATA_GO_KR_KEY", "  spaced_key  ")
        assert _get_api_key() == "spaced_key"


class TestExtractItems:
    """공공데이터포털 API `body.items` 3-way 분기 (dict/list/empty)."""

    def test_items_as_list(self):
        resp = {"body": {"items": [{"ITEM_NAME": "A"}, {"ITEM_NAME": "B"}]}}
        items = _extract_items(resp)
        assert len(items) == 2
        assert items[0]["ITEM_NAME"] == "A"

    def test_items_as_dict_with_single_item(self):
        """일부 응답은 items가 dict이고 그 안에 item 키가 단일 dict."""
        resp = {"body": {"items": {"item": {"ITEM_NAME": "SOLO"}}}}
        items = _extract_items(resp)
        assert len(items) == 1
        assert items[0]["ITEM_NAME"] == "SOLO"

    def test_items_as_dict_with_list(self):
        resp = {"body": {"items": {"item": [{"ITEM_NAME": "X"}, {"ITEM_NAME": "Y"}]}}}
        items = _extract_items(resp)
        assert len(items) == 2

    def test_items_empty(self):
        assert _extract_items({"body": {"items": []}}) == []
        assert _extract_items({"body": {}}) == []
        assert _extract_items({}) == []

    def test_items_dict_but_empty_item(self):
        resp = {"body": {"items": {"item": ""}}}
        assert _extract_items(resp) == []


class TestCallApi:
    """_call_api의 성공/실패 분기."""

    def test_missing_key_returns_error(self, monkeypatch):
        monkeypatch.delenv("DATA_GO_KR_KEY", raising=False)
        # streamlit secrets 경로가 비어있음을 보장하기 위해 streamlit import 차단
        import sys
        monkeypatch.setitem(sys.modules, "streamlit", None)
        resp, err = _call_api("getDrugPrdtPrmsnInq07", {"item_name": "X"})
        assert resp is None
        assert err == "API_KEY_MISSING"

    def test_success_returns_parsed_json(self, monkeypatch):
        _patch_api(monkeypatch, {"body": {"items": [{"ITEM_NAME": "OK"}]}})
        resp, err = _call_api("getDrugPrdtPrmsnInq07", {"item_name": "X"})
        assert err == ""
        assert resp["body"]["items"][0]["ITEM_NAME"] == "OK"

    def test_network_error_after_retries(self, monkeypatch):
        _patch_api_error(monkeypatch, ConnectionError("refused"))
        resp, err = _call_api("getDrugPrdtPrmsnInq07", {"item_name": "X"}, retries=1)
        assert resp is None
        assert "ConnectionError" in err


class TestSearchAndLookup:
    """`search_drug_by_name` · `lookup_product_info` · `get_drug_detail_by_code` 통합."""

    def test_search_returns_product_list(self, monkeypatch):
        _patch_api(monkeypatch, {
            "body": {"items": [
                {"ITEM_NAME": "프로테조밉주3.5mg", "ENTP_NAME": "㈜삼양홀딩스", "ITEM_SEQ": "201506668"},
                {"ITEM_NAME": "벨케이드주", "ENTP_NAME": "한국얀센", "ITEM_SEQ": "200912345"},
            ]}
        })
        results = search_drug_by_name("프로테조밉")
        assert len(results) == 2
        assert results[0].item_name == "프로테조밉주3.5mg"
        assert results[0].item_seq == "201506668"

    def test_search_empty_on_api_failure(self, monkeypatch):
        _patch_api_error(monkeypatch, OSError("boom"))
        results = search_drug_by_name("프로테조밉")
        assert results == []

    def test_get_drug_detail_by_code(self, monkeypatch):
        _patch_api(monkeypatch, {
            "body": {"items": {"item": {
                "ITEM_NAME": "프로테조밉주3.5mg",
                "ENTP_NAME": "㈜삼양홀딩스",
                "ITEM_SEQ": "201506668",
                "ITEM_PERMIT_DATE": "2015-07-22",
                "MAIN_ITEM_INGR": "[M123] 보르테조밉",
                "ATC_CODE": "L01XG01",
            }}}
        })
        # _enrich_ingredients가 추가 호출하므로 동일 응답이 와도 상관없음
        info = get_drug_detail_by_code("201506668")
        assert info is not None
        assert info.item_name == "프로테조밉주3.5mg"
        assert info.item_seq == "201506668"
        # [M123] 접두사 제거 확인
        assert info.ingredient_name == "보르테조밉"

    def test_get_drug_detail_returns_none_when_empty(self, monkeypatch):
        _patch_api(monkeypatch, {"body": {"items": []}})
        assert get_drug_detail_by_code("000000000") is None

    def test_lookup_uses_item_seq_first(self, monkeypatch):
        """품목기준코드가 있으면 getDrugPrdtPrmsnDtlInq06 응답 사용."""
        _patch_api(monkeypatch, {
            "body": {"items": {"item": {
                "ITEM_NAME": "상세조회결과",
                "ITEM_SEQ": "201506668",
                "ENTP_NAME": "TEST",
            }}}
        })
        info = lookup_product_info(item_seq="201506668")
        assert info.item_name == "상세조회결과"
        assert info.source_method == "api"

    def test_lookup_falls_back_to_name(self, monkeypatch):
        """item_seq 없이 item_name만 있으면 search 결과 중 첫 번째 반환."""
        _patch_api(monkeypatch, {
            "body": {"items": [
                {"ITEM_NAME": "매칭1", "ITEM_SEQ": "A"},
                {"ITEM_NAME": "매칭2", "ITEM_SEQ": "B"},
            ]}
        })
        info = lookup_product_info(item_name="매칭")
        assert info.item_name == "매칭1"

    def test_lookup_warns_when_no_input(self):
        info = lookup_product_info()
        assert info.warnings
        assert any("품목기준코드" in w or "제품명" in w for w in info.warnings)

    def test_item_to_product_info_strip_ingredient_prefix(self):
        """[M123456] 같은 API 접두사를 성분명에서 제거."""
        item = {
            "ITEM_NAME": "X",
            "ENTP_NAME": "Y",
            "ITEM_SEQ": "Z",
            "MAIN_ITEM_INGR": "[M123456] 테스트성분",
            "INGR_NAME": "[M987] TestIngredient",
        }
        info = _item_to_product_info(item)
        assert info.ingredient_name == "테스트성분"
        assert info.ingredient_name_en == "TestIngredient"
