"""Assemble the final self-contained player/caddie product HTML for
유해란/이재윤/박서현 x Hole 1/Hole 12. Pulls real geometry (tee/green/zone
pixel positions, already-verified transform) and real per-shot data
(already-built DATA3 blocks) plus the player_deliverables_data.json
produced by build_player_deliverables_data.py. Strategy card text below
is hand-authored FROM the already-verified real numbers in the
committed reports -- every number traces back to a source file, nothing
is invented.
"""
from __future__ import annotations
import json
from pathlib import Path

HERE = Path(__file__).parent
ADIR = HERE / "artifact_data"

# ---- pull real geometry ----
h12_html = (ADIR / "hole12_map_final.html").read_text(encoding="utf-8")
i = h12_html.index("const DATA = ") + len("const DATA = ")
j = h12_html.index(";\n", i)
h12_data = json.loads(h12_html[i:j])
i3 = h12_html.index("const DATA3 = ") + len("const DATA3 = ")
j3 = h12_html.index(";\n", i3)
h12_data3 = json.loads(h12_html[i3:j3])

h1_data = json.loads((ADIR / "hole1_DATA.json").read_text())
h1_data3 = json.loads((ADIR / "hole1_DATA3.json").read_text())

PLAYER_DATA = json.loads((HERE / "player_deliverables_data.json").read_text())

GEOM = {
    "hole12": {"tee": h12_data["tee"], "green": h12_data["green"], "zone_centers": h12_data["zone_centers"], "image": "hole_12.png"},
    "hole1": {"tee": h1_data["tee"], "green": h1_data["green"], "zone_centers": h1_data["zone_centers"], "image": "hole_1.png"},
}
SHOTS = {"hole12": h12_data3, "hole1": h1_data3}

PLAYERS = {"9115": "유해란", "9708": "이재윤", "9111": "박서현"}

# zone-name translation: old coordinate SHORT/MID/LONG-LAT1/2/3 -> human Korean,
# distance range filled in per hole below (no internal LAT/STP/QUAD exposed to the UI)
ZONE_HUMAN_H12 = {
    "SHORT-LAT1": {"dist": "127~246yd", "corridor": "사이드 코리도 A"},
    "SHORT-LAT2": {"dist": "127~246yd", "corridor": "센터 코리도"},
    "SHORT-LAT3": {"dist": "127~246yd", "corridor": "사이드 코리도 B"},
    "MID-LAT1": {"dist": "246~261yd", "corridor": "사이드 코리도 A"},
    "MID-LAT2": {"dist": "246~261yd", "corridor": "센터 코리도"},
    "MID-LAT3": {"dist": "246~261yd", "corridor": "사이드 코리도 B"},
    "LONG-LAT1": {"dist": "261~296yd", "corridor": "사이드 코리도 A"},
    "LONG-LAT2": {"dist": "261~296yd", "corridor": "센터 코리도"},
    "LONG-LAT3": {"dist": "261~296yd", "corridor": "사이드 코리도 B"},
}
ZONE_HUMAN_H1 = {
    "SHORT-LAT1": {"dist": "181~228yd", "corridor": "사이드 코리도 A"},
    "SHORT-LAT2": {"dist": "181~228yd", "corridor": "센터 코리도"},
    "SHORT-LAT3": {"dist": "181~228yd", "corridor": "사이드 코리도 B"},
    "MID-LAT1": {"dist": "228~240yd", "corridor": "사이드 코리도 A"},
    "MID-LAT2": {"dist": "228~240yd", "corridor": "센터 코리도"},
    "MID-LAT3": {"dist": "228~240yd", "corridor": "사이드 코리도 B"},
    "LONG-LAT1": {"dist": "240~272yd", "corridor": "사이드 코리도 A"},
    "LONG-LAT2": {"dist": "240~272yd", "corridor": "센터 코리도"},
    "LONG-LAT3": {"dist": "240~272yd", "corridor": "사이드 코리도 B"},
}

# ---- hand-authored strategy content, every number traced to a committed report ----
# source: NEO_HOLE12_DISTANCE_CALIBRATED_REPORT.md, NEO_HOLE12_MASTER_TEMPLATE.md
# source: NEO_HOLE1_FULL_ANALYSIS.md
CONTENT = {
    "9115": {
        "hole12": {
            "headline": "페어웨이만 지키면 스코어가 방어됨 — 실제 사고는 티+어프로치가 연속으로 러프였던 단 한 번뿐",
            "send_distance": "246~280yd",
            "allowed": "센터 코리도(246~296yd 구간) — 자신의 실제 사거리 안에서 가장 넓게 걸쳐있는 코리도",
            "avoid": "짧은 거리(127~246yd) + 사이드 코리도 B 조합 — 코스 전체에서 관찰된 최악 조합(실제 벙커 포함)",
            "next_distance": "약 115~155yd",
            "miss_priority": "러프에 가더라도 1타로 전진만 하면 방어 가능 — 그린까지 직접 안 가도 된다",
            "big_number_trigger": "티샷과 다음 샷이 연속으로 러프에 들어갈 때만 큰 숫자가 나왔다(실제 4라운드 중 1회, 더블보기)",
            "primary_zones": ["LONG-LAT2", "MID-LAT2"], "acceptable_zones": ["LONG-LAT3", "MID-LAT1"],
            "nogo_zones": ["SHORT-LAT3"],
            "tier": {
                "ideal": "센터 코리도, 246~296yd — 관찰상 GIR 70%대, 보기 이상 20%대",
                "acceptable": "사이드 코리도 B의 먼 거리권(261~296yd) — 센터와 점수 차이가 크지 않음",
                "damage_control": "짧은 러프라도 전진 위주로 한 타씩 — 실제로 이렇게 파를 지킨 사례 있음",
                "nogo": "짧은 거리(127~246yd) + 사이드 코리도 B — 실제 벙커가 섞인 코스 최악 구간",
            },
        },
        "hole1": {
            "headline": "이 홀에서는 자신의 실제 평소 사거리가 '긴 공' 쪽에 속한다 — 실제 4라운드 전부 파 이상",
            "send_distance": "246~280yd (Hole 1 자체 분포상 긴 편)",
            "allowed": "먼 거리권(240~272yd), 사이드/센터 코리도 모두 큰 차이 없음",
            "avoid": "짧은 거리(181~228yd) + 사이드 코리도 A 조합 — 코스 전체 최악 구역(페어웨이 적중률 15%, 보기 이상 80%)",
            "next_distance": "약 150~160yd",
            "miss_priority": "실제로 벙커에서 2번 쳤어도(4라운드 중 2회) 전부 파를 지킴 — 짧은 회복보다 전진이 더 중요했던 패턴",
            "big_number_trigger": "실제 4라운드 동안 보기 이상 기록 없음 — 현재 표본에서는 위험 조건 관찰되지 않음(표본 4개, 근거 제한적)",
            "primary_zones": ["LONG-LAT1", "LONG-LAT2"], "acceptable_zones": ["LONG-LAT3"],
            "nogo_zones": ["SHORT-LAT1"],
            "tier": {
                "ideal": "먼 거리권 전체 — 관찰상 단조롭게 좋아지는 구간",
                "acceptable": "짧은 벙커라도 먼 거리권이면 실제로 파를 지킴(실제 사례 2회)",
                "damage_control": "DATA INSUFFICIENT — 실제 4라운드에 손상 사례 없음",
                "nogo": "짧은 거리(181~228yd) + 사이드 코리도 A — 코스 전체 최악 구역",
            },
        },
    },
    "9708": {
        "hole12": {
            "headline": "이 홀 단독 표본이 적어 개인 패턴 확정은 어려움 — 필드 관찰만 근거로 적용",
            "send_distance": "240~283yd (자신의 실제 사거리 범위)",
            "allowed": "센터 코리도(필드 관찰 근거, 개인 확인은 표본 부족)",
            "avoid": "짧은 거리(127~246yd) + 사이드 코리도 B — 실제로 이 조합에서 보기 이상을 기록한 적 있음(4라운드 중 1회)",
            "next_distance": "약 140~156yd (필드 기준)",
            "miss_priority": "UNKNOWN — 표본 4개로는 확정 불가",
            "big_number_trigger": "DATA INSUFFICIENT — 개인 사고 사례 1건뿐(짧은 거리+사이드 코리도 B)",
            "primary_zones": ["LONG-LAT2"], "acceptable_zones": ["LONG-LAT3", "LONG-LAT1"],
            "nogo_zones": ["SHORT-LAT3"],
            "tier": {
                "ideal": "센터 코리도 — 필드 관찰 근거(개인 검증 제한적)",
                "acceptable": "먼 거리권 전체 — 실제로 3/4라운드가 이 구간",
                "damage_control": "UNKNOWN",
                "nogo": "짧은 거리 + 사이드 코리도 B — 실제 보기 이상 기록(1회)",
            },
        },
        "hole1": {
            "headline": "실제 유일한 보기는 그린을 맞히고도 발생(3퍼트) — 티샷 자체는 전 라운드 안정적",
            "send_distance": "240~283yd (Hole 1 긴 거리권)",
            "allowed": "먼 거리권 전체 — 실제 4라운드 전부 이 구간",
            "avoid": "짧은 거리(181~228yd) + 사이드 코리도 A",
            "next_distance": "약 151~159yd",
            "miss_priority": "그린을 맞혀도 끝이 아니다 — 실제 보기가 그린적중 후 3퍼트에서 나옴(세컨샷 거리/방향보다 퍼팅이 변수)",
            "big_number_trigger": "DATA INSUFFICIENT — 더블보기 이상 사례 없음, 유일한 실수는 3퍼트",
            "primary_zones": ["LONG-LAT1", "LONG-LAT3"], "acceptable_zones": ["LONG-LAT2"],
            "nogo_zones": ["SHORT-LAT1"],
            "tier": {
                "ideal": "먼 거리권 전체 — 실제 4라운드 전부 이 구간, 단조 개선 관찰",
                "acceptable": "그린 주변 벙커 미스도 실제로 파 유지(1회)",
                "damage_control": "그린을 맞혀도 긴 퍼트면 3퍼트 위험 — 세컨샷에서 핀 방향 거리 관리 필요(추정, 표본 적음)",
                "nogo": "짧은 거리(181~228yd) + 사이드 코리도 A",
            },
        },
    },
    "9111": {
        "hole12": {
            "headline": "필드가 관찰한 최적 구역에 거리가 거의 닿지 않는다 — 실제 4라운드 전부 사이드 코리도 A에서만 플레이",
            "send_distance": "227~258yd (실제 현실적 사거리, 짧은 구간)",
            "allowed": "짧은 거리권 안의 센터 코리도 — 실제로는 아직 한 번도 안 가봤지만, 짧은 구간 안에서는 가장 안전한 관찰값",
            "avoid": "짧은 거리(127~246yd) + 사이드 코리도 B — 본인 사거리 안에서도 나올 수 있는 코스 최악 조합",
            "next_distance": "약 175yd 전후 — 본인 데이터에서는 이 거리에서 오히려 그린적중률이 가장 높았음",
            "miss_priority": "그린을 놓쳤을 때 회복력이 세 선수 중 가장 약함(러프에서 파 세이브 43%) — 짧게라도 확실한 위치로 보내는 것이 우선",
            "big_number_trigger": "긴 세컨샷(177yd 이상) + 러프 조합에서 실제 더블보기 발생(4라운드 중 1회)",
            "primary_zones": ["SHORT-LAT2"], "acceptable_zones": ["SHORT-LAT1"],
            "nogo_zones": ["SHORT-LAT3"],
            "actual_zones_note": "실제 4라운드 착지: 사이드 코리도 A 4/4 — 센터 코리도는 관찰 근거이지 본인이 실제로 가본 곳이 아님",
            "tier": {
                "ideal": "짧은 거리권의 센터 코리도 — 관찰값(본인 미검증)",
                "acceptable": "짧은 거리권의 사이드 코리도 A — 실제로 이 구간에서 파를 지킨 사례 다수",
                "damage_control": "러프에서도 짧게라도 전진 — 실제로 1타 만에 그린 근처까지 보내 파 세이브한 사례 있음",
                "nogo": "짧은 거리 + 사이드 코리도 B — 본인 사거리 안에서도 나올 수 있는 최악 조합(실제 벙커)",
            },
        },
        "hole1": {
            "headline": "Hole 12와 반대 상황 — 이 홀에서는 본인 사거리가 필드 관찰 최적 구역과 실제로 겹친다",
            "send_distance": "227~258yd (Hole 1 자체 분포상 중간~긴 편)",
            "allowed": "중간~먼 거리권의 센터 코리도 — 실제 4라운드 중 3회가 이 코리도",
            "avoid": "짧은 거리(181~228yd) + 사이드 코리도 A — 코스 전체 최악 구역",
            "next_distance": "약 171~183yd",
            "miss_priority": "실제 4라운드 전부 파 이상(1버디 포함) — 현재 패턴 유지가 최우선",
            "big_number_trigger": "DATA INSUFFICIENT — 실제 4라운드에 보기 이상 기록 없음",
            "primary_zones": ["MID-LAT2", "SHORT-LAT2"], "acceptable_zones": ["MID-LAT1"],
            "nogo_zones": ["SHORT-LAT1"],
            "actual_zones_note": "실제 4라운드 착지: 센터 코리도 3/4 — Hole 12와 달리 본인이 실제로 자주 가는 코리도가 관찰 최적 구역과 겹침",
            "tier": {
                "ideal": "중간 거리권의 센터 코리도 — 실제 4라운드 중 2회, 전부 파 이상",
                "acceptable": "짧은 거리권의 센터 코리도 — 실제 1버디 포함",
                "damage_control": "DATA INSUFFICIENT — 손상 사례 없음",
                "nogo": "짧은 거리(181~228yd) + 사이드 코리도 A",
            },
        },
    },
}

FIELD = {
    "hole12": {
        "best_label": "246~261yd · 센터 코리도", "best_zone": "MID-LAT2",
        "best_stat": "평균 +0.05타, 그린적중 72%, 보기 이상 20%",
        "worst_label": "127~246yd · 사이드 코리도 B", "worst_zone": "SHORT-LAT3",
        "worst_stat": "평균 +0.89타, 보기 이상 66%, 실제 벙커 28.6%",
        "note": "센터 코리도 효과의 상당 부분은 페어웨이 적중 자체와 겹쳐 있다는 것이 별도로 확인됨 — '그냥 센터를 노려라'가 아니라 '페어웨이 유지'에 더 가까운 결론.",
    },
    "hole1": {
        "best_label": "228~240yd · 센터 코리도", "best_zone": "MID-LAT2",
        "best_stat": "평균 +0.10타, 그린적중 66%, 보기 이상 17%",
        "worst_label": "181~228yd · 사이드 코리도 A", "worst_zone": "SHORT-LAT1",
        "worst_stat": "평균 +0.95타, 페어웨이 적중 15%, 보기 이상 80%(표본 20개)",
        "note": "사이드 코리도 B에서는 페어웨이 적중 자체가 독립적인 효과(+0.25타, 그린적중 -31%p)로 확인됨 — 이 홀은 위치보다 페어웨이 적중 자체가 더 분명한 변수.",
    },
}


def main():
    out = {"geom": GEOM, "shots": SHOTS, "player_data": PLAYER_DATA, "content": CONTENT, "field": FIELD,
           "zone_human": {"hole12": ZONE_HUMAN_H12, "hole1": ZONE_HUMAN_H1}, "players": PLAYERS}
    (HERE / "player_product_data.json").write_text(json.dumps(out, ensure_ascii=False, default=str), encoding="utf-8")
    print("wrote player_product_data.json, size", (HERE / "player_product_data.json").stat().st_size)


if __name__ == "__main__":
    main()
