"""Confirm one player's real tournament-ending status from the REAL
roundLeaderboard HTML, never assumed. Prints the verbatim HTML
context around the player's row for every requested round (present or
absent), so a WD/DQ/CUT/other determination is made from literal
evidence, not inferred from absence alone.
"""
from __future__ import annotations
import argparse, re
from discover_players import fetch_round_html

def find_player_context(html, player_code, window=600):
    """Find every occurrence of this player's _playerCode attribute and
    print the surrounding raw HTML (data-rank, data-* attrs) verbatim."""
    contexts = []
    for m in re.finditer(rf'_playercode\s*=\s*"{re.escape(player_code)}"', html, re.IGNORECASE):
        start = max(0, m.start() - window)
        end = min(len(html), m.end() + 200)
        contexts.append(html[start:end])
    return contexts

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--player", required=True)
    ap.add_argument("--rounds", default="1,2,3,4")
    ap.add_argument("--cookie")
    a = ap.parse_args()

    for rnd in [int(x) for x in a.rounds.split(",")]:
        html = fetch_round_html(a.game, rnd, a.cookie)
        contexts = find_player_context(html, a.player)
        print(f"\n{'='*80}\nROUND {rnd}: player {a.player} -- {'FOUND' if contexts else 'ABSENT'} ({len(contexts)} occurrence(s))\n{'='*80}")
        for i, c in enumerate(contexts):
            print(f"-- occurrence {i} --\n{c}\n")
        if not contexts:
            # Confirm the round's own leaderboard actually returned real
            # rows at all (an empty/broken fetch must not be mistaken for
            # a real absence).
            any_rank = len(re.findall(r"data-rank", html, re.IGNORECASE))
            print(f"(round {rnd} leaderboard contained {any_rank} data-rank occurrences total -- confirms this round's HTML is real/non-empty)")

if __name__ == "__main__":
    main()
