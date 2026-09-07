from __future__ import annotations

import json
from pathlib import Path

import pytest

from klpga_pipeline.scripts.validate_home_v4 import DASH, HomeV4Validator, ROOT


HEADERS = ["NEO", "PLAYER", "SPONSOR", "K-RANK", "PERFORMANCE SG", "FORM", "VOL", "TREND", "EVENTS"]


def _player(*, official: bool) -> tuple[str, str | None]:
    base = ROOT / "content" / "website_v2"
    population = json.loads((base / "HOME_REGULAR_TOUR_PLAYER_MASTER.json").read_text(encoding="utf-8"))
    ranking = json.loads((base / "OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json").read_text(encoding="utf-8"))
    ranks = {str(item["player_id"]): str(item["official_rank"])
             for item in ranking["records"] if item.get("validation_state") == "PASS"}
    record = next(item for item in population["records"]
                  if (str(item["player_id"]) in ranks) is official)
    return record["player_name"], ranks.get(str(record["player_id"]))


def _write_site(
    root: Path,
    *,
    metrics: dict[str, str] | None = None,
    official_player: bool = True,
    k_sort: str | None = None,
    sponsor: str = "",
    avatar: str | None = None,
    inspector_value: str = DASH,
    chart_markup: str = "",
    public_text: str = "",
    extra_html: str = "",
    extra_link: str = "",
    js_extra: str = "",
    css_extra: str = "",
    summary_mode: str = "valid",
    reduced_motion: bool = True,
) -> HomeV4Validator:
    root.mkdir(parents=True, exist_ok=True)
    values = {name: DASH for name in ("NEO", "PERFORMANCE SG", "FORM", "VOL", "TREND", "EVENTS")}
    values.update(metrics or {})
    name, official_rank = _player(official=official_player)
    shown_rank = official_rank or DASH
    sort_value = k_sort if k_sort is not None else (official_rank or "null")
    avatar = avatar if avatar is not None else (
        '<span class="t-avatar" aria-hidden="true"><svg viewBox="0 0 24 24">'
        '<circle cx="12" cy="8" r="3"/></svg></span>'
    )
    nav = "".join(f'<a href="{route}">{route}</a>' for route in
                  ("/", "/tournaments/", "/ranking/", "/deep-dive/", "/neo-lab/", "/about/"))

    if summary_mode == "valid":
        coverage_label = "K-RANK COVERAGE"
        coverage_description = "21.8% · denominator: 546 canonical regular-tour players · official snapshot"
        event_label = "SG WAREHOUSE EVENTS"
        event_description = "97-event incomplete validated subset"
        summary = {
            "population_count": 546,
            "k_ranking_join_success": 119,
            "k_rank_coverage_provenance": {
                "denominator_definition": "546 canonical regular-tour players",
                "official_source": "https://k-rankings.klpga.co.kr/allplayer.jsp",
                "snapshot_timestamp": "2026-09-02T14:23:52Z",
            },
            "historical_events": 97,
            "historical_event_provenance": {
                "complete_klpga_history": False,
                "source_artifact": "historical_sg_warehouse_corrected.json",
                "coverage_scope": "SG_WAREHOUSE_VALIDATED_SUBSET",
            },
        }
    elif summary_mode == "ambiguous_coverage":
        coverage_label = "K-RANK COVERAGE"
        coverage_description = "21.8% coverage"
        event_label = "SG WAREHOUSE EVENTS"
        event_description = "97-event incomplete validated subset"
        summary = {"population_count": 546, "k_ranking_join_success": 119, "historical_events": 97}
    else:
        coverage_label = "K-RANK COVERAGE"
        coverage_description = "21.8% · denominator: 546 canonical regular-tour players · official snapshot"
        event_label = "HISTORICAL EVENTS"
        event_description = "tournaments in the SG warehouse"
        summary = {"population_count": 546, "k_ranking_join_success": 119, "historical_events": 97}

    html = f"""<!doctype html><html lang="ko"><head>
    <link rel="stylesheet" href="/assets/home-v4.css"><script src="/assets/home-v4.js" defer></script>
    </head><body class="home-v4"><nav>{nav}</nav>
    <button data-t-nav-toggle aria-controls="nav" aria-expanded="false">menu</button>{extra_link}
    <div class="t-summary"><div class="t-summary__cell"><p class="t-summary__label">{coverage_label}</p>
    <p class="t-summary__value">119/546</p><p class="t-summary__sub">{coverage_description}</p></div>
    <div class="t-summary__cell"><p class="t-summary__label">{event_label}</p>
    <p class="t-summary__value">97</p><p class="t-summary__sub">{event_description}</p></div></div>
    <main><section id="performance-board" aria-labelledby="board-heading"><h2 id="board-heading">Board</h2>
    <div class="t-board-scroll"><table class="t-board"><thead><tr>
    {''.join(f'<th scope="col">{header}</th>' for header in HEADERS)}</tr></thead><tbody data-t-board-body>
    <tr data-player-row tabindex="0" role="button" data-player-name="{name.casefold()}"
      data-player-display-name="{name}" data-k-rank="{sort_value}" data-k-rank-display="{shown_rank}" {extra_html}>
    <td>{values['NEO']}</td><th scope="row"><span class="t-player-cell">{avatar}{name}</span></th>
    <td class="t-sponsor-cell">{sponsor}</td><td>{shown_rank}</td><td>{values['PERFORMANCE SG']}</td>
    <td>{values['FORM']}</td><td>{values['VOL']}</td><td>{values['TREND']}</td><td>{values['EVENTS']}</td>
    </tr></tbody></table></div><div class="t-mobile-list" data-t-mobile-list>
    <div class="t-mobile-row" data-player-row tabindex="0" role="button" data-player-name="{name.casefold()}"
      data-player-display-name="{name}" data-k-rank="{sort_value}" data-k-rank-display="{shown_rank}">
    <span class="t-mobile-row__rank">{values['NEO']}</span><span class="t-mobile-row__name">{name}</span>
    <span class="t-mobile-row__krank">{shown_rank}</span></div></div></section>
    <section aria-labelledby="analytics-heading"><h2 id="analytics-heading">Analytics</h2>
    <div class="t-chart-cell"><svg><line class="t-chart-axis"/><line class="t-chart-grid"/>{chart_markup}</svg>
    <p>데이터 검증 후 공개</p></div></section>
    <section aria-labelledby="validation-heading"><h2 id="validation-heading">Validation</h2>
    <span class="t-badge">VALIDATING</span><span class="t-badge">NOT PUBLISHED</span></section>
    <p>{public_text}</p></main><div data-t-scrim></div>
    <aside class="t-inspector" data-t-inspector aria-hidden="true" aria-label="player inspector">
    <h3 data-t-inspector-name></h3><button data-t-inspector-close aria-label="close">close</button>
    <div class="t-inspector__row"><span>K-RANK</span><span data-t-inspector-krank>{shown_rank}</span></div>
    <div class="t-inspector__row"><span>NEO RANK</span><span>{DASH}</span></div>
    <div class="t-inspector__row"><span>SG TOTAL</span><span>{DASH}</span></div>
    <div class="t-inspector__row"><span>WIN</span><span>{inspector_value}</span></div>
    <div class="t-inspector__group"><div class="t-inspector__chart"><svg>
    <line class="t-chart-axis"/></svg></div><p>데이터 검증 후 공개</p></div></aside></body></html>"""
    (root / "index.html").write_text(html, encoding="utf-8")
    (root / "assets").mkdir()
    css = """
    .home-v4 :focus-visible { outline: 2px solid green; }
    .home-v4 .t-mobile-list { display: none; }
    @media (max-width: 780px) {
      .home-v4 .t-board-scroll { display: none; }
      .home-v4 .t-mobile-list { display: block; }
      .home-v4 .t-inspector { width: 100vw; }
    }
    """
    if reduced_motion:
        css += "@media (prefers-reduced-motion: reduce) { .home-v4 * { animation: none; transition: none; } }\n"
    (root / "assets" / "home-v4.css").write_text(css + css_extra, encoding="utf-8")
    (root / "assets" / "home-v4.js").write_text("'use strict';\n" + js_extra, encoding="utf-8")
    for route in ("tournaments", "ranking", "deep-dive", "neo-lab", "about"):
        (root / route).mkdir()
        (root / route / "index.html").write_text("<!doctype html><html><body>route</body></html>", encoding="utf-8")
    (root / "data").mkdir()
    (root / "data" / "home-v4-summary.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    return HomeV4Validator(root, run_browser=False)


def _status(validator: HomeV4Validator, check_id: str) -> str:
    return next(item["status"] for item in validator.gate.checks if item["id"] == check_id)


@pytest.mark.parametrize("column,value", [
    ("NEO", "8"), ("PERFORMANCE SG", "+1.2"), ("FORM", "0.8"),
    ("VOL", "1.1"), ("TREND", "+2"), ("EVENTS", "30"),
])
def test_unapproved_board_metrics_fail(tmp_path: Path, column: str, value: str) -> None:
    validator = _write_site(tmp_path, metrics={column: value})
    headers, rows = validator._ranking_table()
    result = validator._neo_numeric_policy(headers, rows)
    assert any(metric["count"] for metric in result.values())
    assert _status(validator, "neo_numeric_exposure") == "FAIL"


def test_all_dash_metrics_and_probability_pass(tmp_path: Path) -> None:
    validator = _write_site(tmp_path)
    headers, rows = validator._ranking_table()
    result = validator._neo_numeric_policy(headers, rows)
    assert all(metric["count"] == 0 for metric in result.values())
    assert _status(validator, "neo_numeric_exposure") == "PASS"


def test_probability_in_inspector_fails(tmp_path: Path) -> None:
    validator = _write_site(tmp_path, inspector_value="12.5%")
    headers, rows = validator._ranking_table()
    result = validator._neo_numeric_policy(headers, rows)
    assert result["PROBABILITIES"]["count"] > 0


@pytest.mark.parametrize("surface", ["attribute", "aria", "json", "javascript", "css"])
def test_hidden_numeric_surfaces_fail(tmp_path: Path, surface: str) -> None:
    kwargs = {}
    if surface == "attribute": kwargs["extra_html"] = 'data-performance-sg="1.2"'
    elif surface == "aria": kwargs["extra_html"] = 'aria-label="SG TOTAL 1.2"'
    elif surface == "javascript": kwargs["js_extra"] = "const winProbability = 42;"
    elif surface == "css": kwargs["css_extra"] = '.metric::after { content: "SG 1.2"; }'
    validator = _write_site(tmp_path, **kwargs)
    if surface == "json":
        (tmp_path / "data" / "model.json").write_text(
            json.dumps({"neo_validation_rank": 3, "recent_5_sg": "1.2", "top5": "14%"}), encoding="utf-8"
        )
    headers, rows = validator._ranking_table()
    result = validator._neo_numeric_policy(headers, rows)
    assert any(metric["count"] for metric in result.values())
    assert _status(validator, "neo_numeric_exposure") == "FAIL"


@pytest.mark.parametrize("sentinel", ["999999", "99999", "9999", "424242"])
def test_missing_k_rank_numeric_sentinels_fail(tmp_path: Path, sentinel: str) -> None:
    validator = _write_site(tmp_path, official_player=False, k_sort=sentinel)
    headers, rows = validator._ranking_table()
    result = validator._k_rank_policy(headers, rows)
    assert result["status"] == "FAIL"
    assert any("fabricated numeric" in item.get("reason", "") for item in result["samples"])


def test_official_k_rank_and_explicit_null_missing_rank_pass(tmp_path: Path) -> None:
    official = _write_site(tmp_path / "official")
    headers, rows = official._ranking_table()
    assert official._k_rank_policy(headers, rows)["status"] == "PASS"
    missing = _write_site(tmp_path / "missing", official_player=False, k_sort="null")
    headers, rows = missing._ranking_table()
    assert missing._k_rank_policy(headers, rows)["status"] == "PASS"


def test_summary_provenance_passes_when_scope_is_explicit(tmp_path: Path) -> None:
    assert _write_site(tmp_path)._summary_provenance()["status"] == "PASS"


@pytest.mark.parametrize("mode", ["ambiguous_coverage", "historical_claim"])
def test_ambiguous_summary_claims_fail(tmp_path: Path, mode: str) -> None:
    assert _write_site(tmp_path, summary_mode=mode)._summary_provenance()["status"] == "FAIL"


@pytest.mark.parametrize("text", [
    "1852 players unexplained gap", "BLOCKED_FORMULA_NOT_APPROVED", "NOT_PRODUCTION",
    "round mismatch counts", "red-team implementation review", "DIAGNOSTIC_PLAYER_JOIN_7",
])
def test_public_engineering_copy_fails(tmp_path: Path, text: str) -> None:
    validator = _write_site(tmp_path, public_text=text)
    result = validator._content_language()
    assert result["status"] == "FAIL" or _status(validator, "internal_engineering_strings") == "FAIL"


def test_public_safe_states_pass_and_betting_language_fails(tmp_path: Path) -> None:
    safe = _write_site(tmp_path / "safe")
    assert safe._content_language()["status"] == "PASS"
    betting = _write_site(tmp_path / "betting", public_text="betting odds")
    betting._content_language()
    assert _status(betting, "betting_language") == "FAIL"


def test_blank_sponsor_passes_and_unverified_sponsor_fails(tmp_path: Path) -> None:
    blank = _write_site(tmp_path / "blank")
    headers, rows = blank._ranking_table()
    assert blank._sponsor_policy(rows, headers)["status"] == "PASS"
    hardcoded = _write_site(tmp_path / "hardcoded", sponsor="Inferred Sponsor")
    headers, rows = hardcoded._ranking_table()
    assert hardcoded._sponsor_policy(rows, headers)["status"] == "FAIL"


def test_silhouette_passes_and_unlicensed_photo_fails(tmp_path: Path) -> None:
    assert _write_site(tmp_path / "silhouette")._photo_policy()["status"] == "PASS"
    photo = _write_site(tmp_path / "photo", avatar='<span class="t-avatar"><img src="/assets/p.jpg"></span>')
    (tmp_path / "photo" / "assets" / "p.jpg").write_bytes(b"photo")
    assert photo._photo_policy()["status"] == "FAIL"


def test_klpga_photo_hotlink_fails(tmp_path: Path) -> None:
    validator = _write_site(
        tmp_path, avatar='<span class="t-avatar"><img data-photo-license-status="VERIFIED" '
                         'src="https://klpga.co.kr/player.jpg"></span>',
    )
    assert validator._photo_policy()["status"] == "FAIL"


def test_player_specific_svg_likenesses_fail(tmp_path: Path) -> None:
    validator = _write_site(tmp_path)
    path = tmp_path / "index.html"
    html = path.read_text(encoding="utf-8")
    row = html.split("<tbody data-t-board-body>", 1)[1].split("</tbody>", 1)[0]
    second = row.replace('r="3"', 'r="5"', 1).replace("data-player-name=", "data-copy-player-name=", 1)
    path.write_text(html.replace("</tbody>", second + "</tbody>", 1), encoding="utf-8")
    validator = HomeV4Validator(tmp_path, run_browser=False)
    assert validator._photo_policy()["status"] == "FAIL"


def test_empty_analytics_pass_and_fabricated_series_fails(tmp_path: Path) -> None:
    assert _write_site(tmp_path / "empty")._analytics_policy()["status"] == "PASS"
    fake = _write_site(tmp_path / "fake", chart_markup='<polyline points="0,10 20,5"/>')
    assert fake._analytics_policy()["status"] == "FAIL"


def test_broken_link_and_missing_accessibility_rules_fail(tmp_path: Path) -> None:
    links = _write_site(tmp_path / "links", extra_link='<a href="/missing/">missing</a>')
    assert links._links_and_navigation()
    css = _write_site(tmp_path / "css", reduced_motion=False)
    css._css_accessibility()
    assert _status(css, "reduced_motion") == "FAIL"


def test_missing_required_navigation_route_fails(tmp_path: Path) -> None:
    validator = _write_site(tmp_path)
    path = tmp_path / "index.html"
    path.write_text(path.read_text(encoding="utf-8").replace(
        '<a href="/ranking/">/ranking/</a>', ""
    ), encoding="utf-8")
    validator = HomeV4Validator(tmp_path, run_browser=False)
    validator._links_and_navigation()
    assert _status(validator, "required_navigation") == "FAIL"
