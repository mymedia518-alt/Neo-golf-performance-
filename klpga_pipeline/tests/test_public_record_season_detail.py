"""Tests for klpga.collectors.public_record_season_detail -- the
official-season-stat parser, built against the real, already-committed
fixture (tests/fixtures/official_detail/8436_publicRecordSeasonDetail
.html, confirmed real via klpga.config's own provenance note)."""
from __future__ import annotations

from pathlib import Path

from klpga import config
from klpga.collectors.public_record_season_detail import (
    fetch_public_record_season_detail,
    parse_public_record_season_detail_html,
)

FIXTURE = (
    Path(__file__).parent / "fixtures" / "official_detail" / "8436_publicRecordSeasonDetail.html"
)


class FakeResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


class FakeClient:
    def __init__(self, response_text: str, status_code: int = 200):
        self.response_text = response_text
        self.status_code = status_code
        self.throttled_hosts: list[str] = []
        self.calls: list[tuple] = []

    def _throttle(self, host):
        self.throttled_hosts.append(host)

    def _do_request(self, method, url, **kwargs):
        self.calls.append((method, url, tuple(sorted((kwargs.get("data") or {}).items()))))
        return FakeResponse(self.status_code, self.response_text)


def test_fetch_calls_confirmed_endpoint_with_exact_params():
    client = FakeClient("<html></html>")
    status, html = fetch_public_record_season_detail(client, "10095", 2023, "2023100001")
    assert status == 200
    assert client.calls == [(
        "POST", config.PUBLIC_RECORD_SEASON_DETAIL_ENDPOINT,
        (("gameCode", "2023100001"), ("playerCode", "10095"), ("season", 2023), ("tourType", "RE")),
    )]
    assert client.throttled_hosts == ["klpga.co.kr"]


def test_parse_real_fixture_extracts_all_five_target_metrics_exactly():
    html = FIXTURE.read_text(encoding="utf-8")
    result = parse_public_record_season_detail_html(html)

    assert result["평균타수"]["value"] == 77.625
    assert result["평균타수"]["detail"]["전체타수"] == "621.000"
    assert result["평균타수"]["detail"]["라운드수"] == "8"

    assert result["파5성적"]["value"] == 5.1176
    assert result["파5성적"]["detail"]["파5 전체 타수"] == "174.000"
    assert result["파5성적"]["detail"]["파5 홀수"] == "34"

    assert result["페어웨이 안착률"]["value"] == 60.0
    assert result["페어웨이 안착률"]["detail"]["페어웨이 안착 수"] == "66"
    assert result["페어웨이 안착률"]["detail"]["전체 측정 홀"] == "110"

    assert result["드라이브 거리"]["value"] == 238.308
    assert result["드라이브 거리"]["detail"]["전체 비거리"] == "3574.6197"
    assert result["드라이브 거리"]["detail"]["전체 측정 홀"] == "15"

    assert result["그린적중률"]["value"] == 56.9444
    assert result["그린적중률"]["detail"]["그린적중수"] == "82.000"


def test_parse_handles_empty_dash_cells_as_none_never_fabricated_zero():
    html = FIXTURE.read_text(encoding="utf-8")
    result = parse_public_record_season_detail_html(html)
    assert result["홀인원"]["value"] is None
    assert result["이글"]["value"] is None


def test_parse_rejects_garbage_html_gracefully():
    result = parse_public_record_season_detail_html("<html><body>not a real page</body></html>")
    assert result == {}
