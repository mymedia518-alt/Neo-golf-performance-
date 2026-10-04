"""Fetch the REAL final-round leaderboard HTML and parse official rank
+ per-round scores for every player, independent of and before any
derived-metric analysis. Used to select case-study players by OFFICIAL
RESULT ONLY -- never by looking at derived Shot Tracker metrics.

Re-implements the same confirmed real attribute contract already
documented in klpga_pipeline/src/klpga/parsers/leaderboard_parser.py
(data-rank, data-score, data-round<N>score, _playerCode) but as its
own minimal, independent parser (regex-based, no bs4 dependency),
consistent with this tool's "independent collector" scope.
"""
from __future__ import annotations
import argparse, json, re
from discover_players import fetch_round_html

ROW_RE = re.compile(r"<[^>]*data-rank\s*=", re.IGNORECASE)
TAG_RE = re.compile(r"<[a-zA-Z][^>]*>")
ATTR_RE = re.compile(r'([a-zA-Z_][a-zA-Z0-9_-]*)\s*=\s*"([^"]*)"')


def _attrs(tag_text):
    return {k.lower(): v for k, v in ATTR_RE.findall(tag_text)}


def parse_final_rows(html):
    rows = []
    for m in ROW_RE.finditer(html):
        window = html[m.start(): m.start() + 4000]
        tags = TAG_RE.findall(window)
        merged = {}
        for t in tags[:12]:
            merged.update(_attrs(t))
            if "_playercode" in merged:
                break
        pc = merged.get("_playercode")
        if not pc:
            continue
        rows.append({
            "player_code": pc.strip(),
            "player_name": (merged.get("_playername") or merged.get("data-name") or "").strip() or None,
            "rank_display": (merged.get("data-rank") or "").strip() or None,
            "total_score": (merged.get("data-score") or "").strip() or None,
            "total_under_par": (merged.get("data-totunderpar") or "").strip() or None,
            "round1_score": (merged.get("data-round1score") or "").strip() or None,
            "round2_score": (merged.get("data-round2score") or "").strip() or None,
            "round3_score": (merged.get("data-round3score") or "").strip() or None,
            "round4_score": (merged.get("data-round4score") or "").strip() or None,
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--final-round", type=int, default=4)
    ap.add_argument("--cookie")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    html = fetch_round_html(a.game, a.final_round, a.cookie)
    rows = parse_final_rows(html)
    # Dedup by player_code (the real HTML carries each player's row
    # twice in some captures -- keep the first occurrence per code).
    seen = {}
    for r in rows:
        seen.setdefault(r["player_code"], r)
    result = {"game_code": a.game, "final_round": a.final_round, "rows": list(seen.values())}
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print(f"parsed {len(seen)} unique players from real round {a.final_round} leaderboard -> {a.out}")
    for r in sorted(seen.values(), key=lambda x: (x["rank_display"] is None, x["rank_display"])):
        print(r)


if __name__ == "__main__":
    main()
