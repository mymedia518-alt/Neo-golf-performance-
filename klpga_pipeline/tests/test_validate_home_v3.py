from __future__ import annotations

import json
from pathlib import Path

import pytest

from klpga_pipeline.scripts.validate_home_v3 import DASH, HomeV3Validator, ROOT


HEADERS = [
    "NEO RANK",
    "선수",
    "스폰서",
    "K-RANK",
    "PERFORMANCE SG",
    "RECENT FORM",
    "VOLATILITY",
    "TREND",
    "EVENTS",
]


def _official_player() -> tuple[str, str]:
    base = ROOT / "content" / "website_v2"
    population = json.loads(
        (base / "HOME_REGULAR_TOUR_PLAYER_MASTER.json").read_text(encoding="utf-8")
    )
    ranking = json.loads(
        (base / "OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json").read_text(encoding="utf-8")
    )
    ranks = {
        str(item["player_id"]): str(item["official_rank"])
        for item in ranking["records"]
        if item.get("validation_state") == "PASS"
    }
    player = next(
        item for item in population["records"] if str(item["player_id"]) in ranks
    )
    return player["player_name"], ranks[str(player["player_id"])]


def _write_site(
    root: Path,
    *,
    values: dict[str, str] | None = None,
    sponsor: str = "",
    avatar: str | None = None,
    race_markup: str = "",
    race_text: str = "데이터 검증 후 공개",
    extra_text: str = "",
    extra_link: str = "",
    reduced_motion: bool = True,
) -> HomeV3Validator:
    values = {header: DASH for header in HEADERS if header not in {"선수", "스폰서", "K-RANK"}} | (values or {})
    name, k_rank = _official_player()
    avatar = avatar if avatar is not None else (
        '<span class="v3-avatar" aria-hidden="true">'
        '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="3"/></svg></span>'
    )
    cells = {
        "NEO RANK": values["NEO RANK"],
        "PERFORMANCE SG": values["PERFORMANCE SG"],
        "RECENT FORM": values["RECENT FORM"],
        "VOLATILITY": values["VOLATILITY"],
        "TREND": values["TREND"],
        "EVENTS": values["EVENTS"],
    }
    nav = "".join(f'<a href="{route}">{route}</a>' for route in (
        "/", "/tournaments/", "/ranking/", "/deep-dive/", "/neo-lab/", "/about/"
    ))
    html = f"""<!doctype html><html lang="ko"><head>
    <link rel="stylesheet" href="/assets/home-v3.css"></head><body class="home-v3">
    <nav>{nav}</nav><button data-v3-nav-toggle aria-controls="nav" aria-expanded="false">menu</button>
    {extra_link}<section aria-labelledby="v3-ranking-heading"><h2 id="v3-ranking-heading">Ranking</h2>
    <div class="v3-table-scroll v3-desktop-only"><table class="v3-rank-table">
    <thead><tr>{''.join(f'<th scope="col">{header}</th>' for header in HEADERS)}</tr></thead>
    <tbody><tr data-k-rank="{k_rank}" data-recent-sg="">
    <td>{cells['NEO RANK']}</td>
    <th scope="row"><span class="v3-player-cell">{avatar}{name}</span></th>
    <td class="v3-sponsor-cell">{sponsor}</td><td>{k_rank}</td>
    <td class="v3-metric">{cells['PERFORMANCE SG']}</td>
    <td class="v3-metric">{cells['RECENT FORM']}</td>
    <td class="v3-metric">{cells['VOLATILITY']}</td>
    <td><span class="v3-trend-chip">{cells['TREND']}</span></td>
    <td class="v3-metric">{cells['EVENTS']}</td></tr></tbody></table></div>
    <div class="v3-rank-cards"><article class="v3-rank-card" data-recent-sg="">
    <span class="v3-rank-card__rank">{cells['NEO RANK']}</span>
    <span class="v3-rank-card__name">{name}</span>
    <span class="v3-rank-card__sg">{cells['PERFORMANCE SG']}</span>
    <div class="v3-rank-card__more"><span>RECENT <b>{cells['RECENT FORM']}</b></span>
    <span>VOL <b>{cells['VOLATILITY']}</b></span><span>TREND <b>{cells['TREND']}</b></span>
    <span>EVENTS <b>{cells['EVENTS']}</b></span></div></article></div></section>
    <section aria-labelledby="v3-race-heading"><h2 id="v3-race-heading">Performance Race</h2>
    <svg><line x1="0" x2="100"/><circle class="v3-race-pulse" cx="10" cy="10" r="2"/>{race_markup}</svg>
    <p>{race_text}</p></section><p>{extra_text}</p></body></html>"""
    (root / "assets").mkdir(parents=True)
    css = """
    .home-v3 :focus-visible { outline: 2px solid blue; }
    .home-v3 .v3-rank-cards { display: none; }
    @media (max-width: 760px) {
      .home-v3 .v3-table-scroll.v3-desktop-only { display: none; }
      .home-v3 .v3-rank-cards { display: block; }
    }
    """
    if reduced_motion:
        css += "@media (prefers-reduced-motion: reduce) { .home-v3 * { animation: none; } }\n"
    (root / "assets" / "home-v3.css").write_text(css, encoding="utf-8")
    (root / "index.html").write_text(html, encoding="utf-8")
    for route in ("tournaments", "ranking", "deep-dive", "neo-lab", "about"):
        (root / route).mkdir()
        (root / route / "index.html").write_text(
            "<!doctype html><html><body>route</body></html>", encoding="utf-8"
        )
    (root / "data").mkdir()
    (root / "data" / "home-v3-summary.json").write_text("{}\n", encoding="utf-8")
    return HomeV3Validator(root, run_browser=False)


def _check(validator: HomeV3Validator, check_id: str) -> dict:
    return next(item for item in validator.gate.checks if item["id"] == check_id)


@pytest.mark.parametrize(
    "field,value",
    [
        ("NEO RANK", "7"),
        ("PERFORMANCE SG", "+1.25"),
        ("RECENT FORM", "+0.80"),
        ("VOLATILITY", "1.10"),
        ("EVENTS", "18"),
    ],
)
def test_neo_numeric_fields_fail_closed(tmp_path: Path, field: str, value: str) -> None:
    validator = _write_site(tmp_path, values={field: value})
    headers, rows = validator._ranking_table()
    exposure = validator._neo_numeric_policy(headers, rows)
    assert exposure[field]["count"] > 0
    assert _check(validator, "neo_numeric_exposure")["status"] == "FAIL"


def test_em_dash_placeholders_pass(tmp_path: Path) -> None:
    validator = _write_site(tmp_path)
    headers, rows = validator._ranking_table()
    exposure = validator._neo_numeric_policy(headers, rows)
    assert all(item["count"] == 0 for item in exposure.values())
    assert _check(validator, "neo_numeric_exposure")["status"] == "PASS"


def test_unapproved_numeric_json_cannot_bypass_placeholders(tmp_path: Path) -> None:
    validator = _write_site(tmp_path)
    (tmp_path / "data" / "hidden-model.json").write_text(
        json.dumps({"records": [{"neo_validation_rank": 3, "recent_5_sg": 1.2}]}),
        encoding="utf-8",
    )
    headers, rows = validator._ranking_table()
    exposure = validator._neo_numeric_policy(headers, rows)
    assert exposure["NEO RANK"]["count"] == 1
    assert exposure["RECENT FORM"]["count"] == 1
    assert _check(validator, "neo_numeric_exposure")["status"] == "FAIL"


def test_unverified_sponsor_fails_and_blank_passes(tmp_path: Path) -> None:
    blank = _write_site(tmp_path / "blank")
    headers, rows = blank._ranking_table()
    assert blank._sponsor_policy(rows, headers)["status"] == "PASS"

    unverified = _write_site(tmp_path / "unverified", sponsor="Unverified Sponsor")
    headers, rows = unverified._ranking_table()
    assert unverified._sponsor_policy(rows, headers)["status"] == "FAIL"


def test_silhouette_passes_and_unlicensed_photo_fails(tmp_path: Path) -> None:
    silhouette = _write_site(tmp_path / "silhouette")
    assert silhouette._photo_policy()["status"] == "PASS"

    unlicensed = _write_site(
        tmp_path / "unlicensed", avatar='<span class="v3-avatar"><img src="/assets/player.jpg"></span>'
    )
    (tmp_path / "unlicensed" / "assets" / "player.jpg").write_bytes(b"test")
    assert unlicensed._photo_policy()["status"] == "FAIL"


def test_klpga_image_hotlink_fails(tmp_path: Path) -> None:
    validator = _write_site(
        tmp_path,
        avatar='<span class="v3-avatar"><img data-photo-license-status="VERIFIED" '
        'src="https://klpga.co.kr/images/player.jpg"></span>',
    )
    result = validator._photo_policy()
    assert result["status"] == "FAIL"
    assert any("hotlink" in item["reason"] for item in result["violations"])


def test_performance_race_series_fails_and_empty_shell_passes(tmp_path: Path) -> None:
    empty = _write_site(tmp_path / "empty")
    assert empty._race_policy()["status"] == "PASS"

    fabricated = _write_site(
        tmp_path / "fabricated", race_markup='<polyline points="0,10 50,3 100,8"/>'
    )
    assert fabricated._race_policy()["status"] == "FAIL"


@pytest.mark.parametrize("text", ["BLOCKED_FORMULA_NOT_APPROVED", "betting odds"])
def test_internal_blocker_and_betting_language_fail(tmp_path: Path, text: str) -> None:
    validator = _write_site(tmp_path, extra_text=text)
    validator._content_language()
    expected = "betting_language" if "betting" in text else "internal_engineering_strings"
    assert _check(validator, expected)["status"] == "FAIL"


def test_broken_internal_link_fails(tmp_path: Path) -> None:
    validator = _write_site(tmp_path, extra_link='<a href="/missing/">missing</a>')
    broken = validator._links_and_navigation()
    assert any(item["url"] == "/missing/" for item in broken)
    assert _check(validator, "internal_links")["status"] == "FAIL"


def test_missing_reduced_motion_fails(tmp_path: Path) -> None:
    validator = _write_site(tmp_path, reduced_motion=False)
    validator._css_accessibility()
    assert _check(validator, "reduced_motion")["status"] == "FAIL"


def test_official_k_rank_passes(tmp_path: Path) -> None:
    validator = _write_site(tmp_path)
    headers, rows = validator._ranking_table()
    assert validator._k_rank_policy(headers, rows)["status"] == "PASS"
