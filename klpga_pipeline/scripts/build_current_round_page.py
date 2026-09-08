"""Add a verified current leaderboard to an existing round forecast page."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.tournament_atomic_promotion import atomic_promote  # noqa: E402
from klpga.tournament_context import load_active_tournament_context  # noqa: E402
from klpga.website_v2.player_identity import render_player_identity, verified_sponsor  # noqa: E402


def _sponsor_by_id(context) -> dict[str, str]:
    """Same official, identity-validated player master every other
    sponsor lookup in this pipeline uses -- see
    klpga.website_v2.player_identity.verified_sponsor()."""
    path = context.artifact_path("current_player_master")
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out = {}
    for row in data.get("records") or []:
        sponsor = verified_sponsor(row)
        player_id = row.get("player_id")
        if sponsor and player_id is not None:
            out[str(player_id)] = sponsor
    return out


_CONTEXT = load_active_tournament_context()


def build(snapshot, template, *, tournament_name, factual_sha256, context=None):
    context = context or _CONTEXT
    sponsor_by_id = _sponsor_by_id(context)
    # NEO TOURNAMENT PIPELINE: tournament name and stage labels are no
    # longer hardcoded here -- tournament_name is an explicit caller-
    # supplied argument (run_tournament.py passes TournamentContext.
    # tournament_name), and the stage labels are derived from the
    # snapshot's own "stage"/"round" fields
    # (collect_current_round_evidence.py already computes
    # "FINAL_LIVE" vs "R{n}_LIVE" from the official totalRound, never a
    # literal), never a separate literal string.
    # Two forms are needed to match the original page copy exactly:
    # round_label ("R3") is used almost everywhere, while heading_label
    # ("R3 (FINAL)") is reserved for the <h1> and the two template
    # splice targets, which is what the page originally hardcoded.
    round_label = f"R{snapshot['round']}"
    heading_label = f"{round_label} (FINAL)" if str(snapshot.get("stage", "")).startswith("FINAL") else round_label
    players = snapshot["player_table"]
    assert len(players) == snapshot["row_count"] == len({r["player_code"] for r in players})
    stamp = datetime.fromisoformat(snapshot["collected_at"]).astimezone(
        timezone(timedelta(hours=9))
    ).strftime("%Y-%m-%d %H:%M:%S KST")
    sg_stamp = datetime.fromisoformat(snapshot["sg_retrieved_at"]).astimezone(
        timezone(timedelta(hours=9))
    ).strftime("%H:%M:%S KST")
    rows = []
    for r in players:
        assert 0 <= r["holes_completed"] <= 18
        other_cells = [r["rank_display"], r["total_under_par_display"],
                       r["today_under_par_display"], str(r["holes_completed"]),
                       "종료" if r["progress_display"] == "F" else f'{r["raw_inghole"]}번 홀',
                       "OUT (1번)" if r["starting_tee"] == 1 else "IN (10번)"]
        # PUBLIC UI correction (GLOBAL SPONSOR RULE): the 선수 cell is a
        # genuine identity display -- name-slot + sponsor-slot, both
        # always present, sponsor filled only when verified.
        name_cell = f"<td>{render_player_identity(r['player_name'], sponsor_by_id.get(str(r['player_code'])))}</td>"
        rows.append(
            f'<tr data-current-player="{escape(r["player_code"])}">'
            f"<td>{escape(str(other_cells[0]))}</td>" + name_cell +
            "".join(f"<td>{escape(str(x))}</td>" for x in other_cells[1:]) + "</tr>"
        )
    sg_rows = []
    for r in snapshot["sg"]:
        assert all(r["validation"][k] for k in ("total_within_tolerance", "t2g_within_tolerance"))
        sg_name_cell = f"<td>{render_player_identity(r['player'], sponsor_by_id.get(str(r['player_id'])))}</td>"
        sg_rows.append(f'<tr data-sg-player="{escape(r["player_id"])}">' + sg_name_cell +
                       "".join(f'<td>{r[k]:+.2f}</td>' for k in ("total", "tee_to_green", "off_the_tee", "approach", "around_green", "putting")) + "</tr>")
    finished = sum(r["holes_completed"] == 18 for r in players)
    leader = players[0]
    current = f'''<!-- NEO CURRENT ROUND START -->
<section class="panel neo-current-round" id="current-round" data-current-round="{snapshot['round']}" data-collected-at="{escape(snapshot['collected_at'])}">
<p class="eyebrow">{escape(tournament_name)} · 공식 {round_label} 현재 상황</p>
<h1>{heading_label} 현재 리더보드</h1>
<p class="note">공식 데이터 확인: <time>{stamp}</time> · {len(players)}명 · 라운드 완료 {finished}명</p>
<p><strong>현재 선두 {render_player_identity(leader['player_name'], sponsor_by_id.get(str(leader['player_code'])))} · 합계 {escape(leader['total_under_par_display'])}</strong></p>
<p class="note">완료 홀은 공식 홀별 스코어가 기록된 개수입니다. 진행 홀은 코스의 홀 번호이며, IN 출발은 10번 홀부터 시작합니다.</p>
<div class="table-wrap"><table class="data"><caption>{round_label} 공식 성적</caption><thead><tr><th>순위</th><th>선수</th><th>합계</th><th>오늘</th><th>완료 홀</th><th>진행 홀</th><th>출발</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p class="note"><a href="https://klpga.co.kr/web/leaderboard/leaderboard?gameCode={snapshot['game_code']}">KLPGA 공식 리더보드</a> · 원본에 별도 갱신 시각이 없어 NEO가 확인한 시각을 표시합니다.</p>
<details><summary>공식 {round_label} SG 경기력 보기</summary>
<p class="note">{round_label} 단일 라운드 공식 SG · 확인 {sg_stamp}. 진행 중인 라운드의 잠정 기록입니다. 성적과 SG는 공식 제공 시차가 있을 수 있습니다.</p>
<div class="table-wrap"><table class="data"><thead><tr><th>선수</th><th>SG 전체</th><th>티→그린</th><th>티샷</th><th>어프로치</th><th>그린주변</th><th>퍼팅</th></tr></thead><tbody>{''.join(sg_rows)}</tbody></table></div></details>
<p class="note">아래 NEO 확률은 R2 종료 기준 사전예측입니다. 현재 {round_label} 성적을 반영한 실시간 확률은 제공하지 않습니다.</p>
</section>
<!-- NEO CURRENT ROUND END -->
'''
    template = re.sub(r'<!-- NEO CURRENT ROUND START -->.*?<!-- NEO CURRENT ROUND END -->\s*', '', template, flags=re.S)
    template = template.replace(f'<h1>{heading_label} NEO 예측</h1>', f'<h2>R2 종료 기준 · {heading_label} NEO 사전예측</h2>')
    template = template.replace(f'NEO GOLF DATA · {heading_label} 예측</title>', f'NEO GOLF DATA · {heading_label} 현재 상황</title>')
    template = re.sub(r'(<meta name="neo-build-id" content=")[^"]+', r'\g<1>' + snapshot['collected_at'], template)
    # NEO TOURNAMENT PIPELINE (item 3): binding meta tags required by
    # klpga.tournament_atomic_promotion.validate_candidate_for_promotion
    # -- this is the same generic candidate->validate->promote gate
    # every other stage uses, not a page-specific bypass. The sha256 is
    # bound to the source official evidence snapshot (the --snapshot
    # file), never to this rendered HTML file itself, so it can be
    # computed before the page exists.
    binding_meta = (
        '<meta name="neo-publication-mode" content="factual-only">\n'
        f'<meta name="neo-game-code" content="{escape(str(snapshot["game_code"]))}">\n'
        f'<meta name="neo-round-number" content="{snapshot["round"]}">\n'
        f'<meta name="neo-factual-sha256" content="{factual_sha256}">'
    )
    template = re.sub(r'(<meta name="neo-build-id" content="[^"]+">)', r'\g<1>\n' + binding_meta, template, count=1)
    assert '<section class="panel">' in template
    return template.replace('<section class="panel">', current + '\n<section class="panel">', 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--snapshot', type=Path, required=True)
    ap.add_argument('--template', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True,
                     help='candidate path -- never a production docs/ path directly (see --promote).')
    ap.add_argument('--tournament-name', required=True)
    ap.add_argument('--promote', action='store_true',
                     help='NEO TOURNAMENT PIPELINE item 3: after writing the candidate, run it '
                          'through klpga.tournament_atomic_promotion.atomic_promote() into the '
                          "production route for this stage (TournamentContext.url_base + the "
                          'snapshot round), instead of the old direct docs/ write.')
    args = ap.parse_args()
    snapshot_bytes = args.snapshot.read_bytes()
    snapshot = json.loads(snapshot_bytes.decode('utf-8'))
    factual_sha256 = sha256(snapshot_bytes).hexdigest()
    template_bytes = args.template.read_bytes()
    result = build(snapshot, template_bytes.decode('utf-8').replace('\r\n', '\n'),
                    tournament_name=args.tournament_name, factual_sha256=factual_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    newline = '\r\n' if b'\r\n' in template_bytes else '\n'
    args.output.write_bytes(result.replace('\n', newline).encode('utf-8'))
    print(args.output)

    if args.promote:
        context = load_active_tournament_context()
        if str(snapshot['game_code']) != context.game_code:
            raise SystemExit(f"HARD STOP: snapshot game_code {snapshot['game_code']!r} != active {context.game_code!r}")
        # This is always the live per-round page ("r{N}"), never the
        # site's separate "final" wrap-up route -- snapshot["stage"]
        # starting with "FINAL" means "this is the tournament's last
        # round of play", a fact about the round, not about which site
        # route serves it (see tournament_context.py's module docstring
        # on why OK Open's r3 and final are two distinct pages).
        stage_key = f"r{snapshot['round']}"
        repo_root = Path(__file__).resolve().parents[2]
        target = repo_root / 'docs' / context.url_base.strip('/') / stage_key / 'index.html'
        result_promotion = atomic_promote(
            args.output, target,
            expected_game_code=context.game_code,
            expected_round_number=snapshot['round'],
            expected_factual_sha256=factual_sha256,
        )
        print(f"PROMOTED: {target} (changed={result_promotion.changed})")


if __name__ == '__main__':
    main()
