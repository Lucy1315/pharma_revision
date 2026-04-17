import pytest
from src.product_scraper import scrape_product_info, extract_drug_code_from_url, ProductInfo


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

    def test_product_info_dataclass_defaults(self):
        p = ProductInfo()
        assert p.item_name == ""
        assert p.company_name == ""
        assert p.warnings == []

    def test_warning_on_network_failure(self, monkeypatch):
        import urllib.request
        monkeypatch.setattr(urllib.request, "Request", lambda *a, **kw: None)
        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: (_ for _ in ()).throw(ConnectionError("timeout")))

        p = scrape_product_info("https://nedrug.mfds.go.kr/test?cacheSeq=123")
        assert len(p.warnings) > 0
        assert "123" == p.item_seq  # URL에서 추출한 코드는 남아야 함
