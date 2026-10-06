"""Official KLPGA player season-stat detail collector/parser
(`/load/profile/publicRecordSeasonDetail`) -- the real endpoint that
carries Driving Distance/Fairway Accuracy/GIR/Par5 scoring/Average
Score, per klpga.config.PUBLIC_RECORD_SEASON_DETAIL_ENDPOINT's own
provenance note (CONFIRMED live 2026-10-03, GitHub Actions runner).

Built for the three-winner pre-event player profile validation's
official-stat acquisition (2026-10-06), continued after the earlier
turn incorrectly reported these 5 metrics as UNAVAILABLE -- the real
source exists (confirmed against the committed fixture
tests/fixtures/official_detail/8436_publicRecordSeasonDetail.html);
what was missing was a parser and an acquisition manifest, not the
data itself. Both are built here.

PARAMETERS (from config.py's own documented, live-confirmed call):
    playerCode, season, tourType="RE", gameCode
  gameCode="" is documented as "전체/all tournaments that season" --
  i.e. the FULL-SEASON cumulative. Whether passing a SPECIFIC gameCode
  scopes the response to "cumulative through that tournament" (which
  would make it temporal-safe for a pre-cutoff reconstruction) is
  UNCONFIRMED -- never assumed true. The acquisition script
  (scripts/210_acquire_official_season_stats.py) tests this directly:
  it independently knows each player's own real pre-cutoff round count
  (from the already-acquired, already-verified scoreRecord captures)
  and compares the gameCode-scoped response's own "라운드수" against it.
  A match is evidence the scoping works as hypothesized; a mismatch is
  reported as SOURCE_EXISTS_BUT_TEMPORAL_RECONSTRUCTION_FAILED for that
  player/metric, never silently trusted either way."""
from __future__ import annotations

from bs4 import BeautifulSoup

from klpga import config
from klpga.http_client import PoliteHttpClient


def fetch_public_record_season_detail(
    client: PoliteHttpClient, player_code: str, season: int, game_code: str, tour_type: str = "RE",
) -> tuple[int, str]:
    """Real, always-live POST -- never served from the disk cache, so
    every call proves a real network round-trip happened. Returns
    (status_code, raw_html_fragment). Uses client._throttle +
    client._do_request directly (the same pattern this project's other
    diagnostic/acquisition scripts already use) because
    PoliteHttpClient.post_text only returns the body, not the status
    code this acquisition needs to classify SOURCE_PASS/FAIL."""
    import requests as _requests
    url = config.PUBLIC_RECORD_SEASON_DETAIL_ENDPOINT
    host = _requests.utils.urlparse(url).netloc
    client._throttle(host)
    resp = client._do_request(
        "POST", url,
        data={"playerCode": player_code, "season": season, "tourType": tour_type, "gameCode": game_code},
    )
    return resp.status_code, resp.text


def parse_public_record_season_detail_html(html: str) -> dict[str, dict]:
    """Real parser, built against the real committed fixture's own
    markup: each <tr> is <td class="text-start bg-lightblue">LABEL</td>
    <td>VALUE</td><td>RANK</td> followed by zero or more
    (<td class="text-start bg-lightblue">SUBLABEL</td><td>SUBVALUE</td>)
    pairs ("세부기록" -- the numerator/denominator detail columns).

    Returns {label: {"value": float|None, "rank": str|None,
    "detail": {sublabel: subvalue, ...}}}. A "-" or empty cell becomes
    None, never fabricated as 0. Rows with no label (both td's empty)
    are skipped."""
    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, dict] = {}

    def _clean(text: str) -> str | None:
        text = " ".join(text.split())
        if text in ("", "-"):
            return None
        return text

    def _as_float(text: str | None) -> float | None:
        if text is None:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    for table in soup.select("table"):
        for tr in table.select("tbody tr"):
            cells = tr.find_all("td")
            if len(cells) < 3:
                continue
            label = _clean(cells[0].get_text())
            if label is None:
                continue
            value_text = _clean(cells[1].get_text())
            rank_text = _clean(cells[2].get_text())
            detail: dict[str, str | None] = {}
            rest = cells[3:]
            for i in range(0, len(rest) - 1, 2):
                sublabel = _clean(rest[i].get_text())
                subvalue = _clean(rest[i + 1].get_text())
                if sublabel is not None:
                    detail[sublabel] = subvalue
            result[label] = {"value": _as_float(value_text), "rank": rank_text, "detail": detail}
    return result
