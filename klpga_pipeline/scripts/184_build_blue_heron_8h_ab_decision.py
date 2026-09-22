"""Build NEO Blue Heron 8H A/B decision card from official 2026 KLPGA baseline evidence.

This artifact is deliberately distance-state only. It does not invent a spatial
target, hazard geometry, club selection, or shot dispersion.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"data/player_baseline/ab_10097_9784_2026.json"
OUT=ROOT/"data/player_baseline/blue_heron_8h_ab_decision_v1.json"
MD=ROOT/"reports/BLUE_HERON_8H_AB_DECISION_V1.md"

TEE_BANDS={
    230:"010313", # 220-240
    250:"010312", # 240-260
    270:"010311", # 260-280
}
APPROACH_BIRDIE={
    230:"020707", # 140-160
    250:"020708", # 120-140
    270:"020709", # 100-120
}
APPROACH_FW_GIR={
    230:"020305",
    250:"020306",
    270:"020307",
}
PLAYERS={"10097":"김민선7","9784":"이예원"}
HOLE_YD=377

def rows_by_metric(data):
    return {r["menu3"]:r for r in data["requests"]}

def player(r, code):
    for x in r["selected"]:
        if x["player_code"]==code:
            return x
    raise KeyError((r["menu3"],code))

def pct(x): return float(x["values"]["record"])
def n(x): return int(x["values"]["record2"].replace(",",""))

def main():
    data=json.loads(SRC.read_text(encoding="utf-8"))
    m=rows_by_metric(data)
    out={
      "title":"NEO A/B PLAYER TEST #01 — Blue Heron 8H",
      "season":2026,
      "event":{"game_code":"2026100005","name":"제26회 하이트진로 챔피언십","course":"Blue Heron","hole":8,"par":4,"yardage":377},
      "scope":"distance-state evidence only",
      "players":{},
      "gate":{"distance_decision_layer":"PASS","spatial_target":"HOLD"},
      "limitations":[
        "티샷 거리에서 홀 전장 차감값은 명목상 남은 거리이며 공간 좌표가 아니다.",
        "실제 벙커·러프·좌우 분산·핀 위치·날씨·클럽 선택은 아직 결합하지 않았다.",
        "따라서 특정 지점을 BEST TARGET으로 확정하지 않는다."
      ]
    }
    for code,name in PLAYERS.items():
        candidates=[]
        for tee in (230,250,270):
            fw=player(m[TEE_BANDS[tee]],code)
            bird=player(m[APPROACH_BIRDIE[tee]],code)
            gir=player(m[APPROACH_FW_GIR[tee]],code)
            candidates.append({
              "tee_nominal_yd":tee,
              "remaining_nominal_yd":HOLE_YD-tee,
              "tee_fairway_pct":pct(fw),"tee_sample_n":n(fw),
              "approach_birdie_plus_pct":pct(bird),"approach_sample_n":n(bird),
              "fairway_gir_pct":pct(gir),"fairway_gir_sample_n":n(gir),
            })
        out["players"][code]={"name":name,"candidates":candidates}

    k=out["players"]["10097"]["candidates"]; l=out["players"]["9784"]["candidates"]
    out["observations"]=[
      f"김민선7: 230→270yd에서 FW {k[0]['tee_fairway_pct']:.2f}%→{k[2]['tee_fairway_pct']:.2f}%, Birdie+ {k[0]['approach_birdie_plus_pct']:.2f}%→{k[2]['approach_birdie_plus_pct']:.2f}%.",
      f"이예원: 230→270yd에서 FW {l[0]['tee_fairway_pct']:.2f}%→{l[2]['tee_fairway_pct']:.2f}%, Birdie+ {l[0]['approach_birdie_plus_pct']:.2f}%→{l[2]['approach_birdie_plus_pct']:.2f}%.",
      "같은 홀에서도 두 선수의 거리-정확도-어프로치 곡선이 동일하지 않다.",
    ]
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    MD.parent.mkdir(parents=True,exist_ok=True)
    lines=["# NEO A/B PLAYER TEST #01 — Blue Heron 8H","","**377yd · Par4 · Distance-state evidence only**","",
           "| 선수 | 티샷 | 명목 잔여 | FW | FW 표본 | Birdie+ | 접근 표본 | FW GIR | GIR 표본 |",
           "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for code in PLAYERS:
        for c in out["players"][code]["candidates"]:
            lines.append(f"| {PLAYERS[code]} | {c['tee_nominal_yd']} | {c['remaining_nominal_yd']} | {c['tee_fairway_pct']:.2f}% | {c['tee_sample_n']} | {c['approach_birdie_plus_pct']:.2f}% | {c['approach_sample_n']} | {c['fairway_gir_pct']:.2f}% | {c['fairway_gir_sample_n']} |")
    lines += ["","## 판정","- **Distance Decision Layer: PASS**","- **Spatial Target / GOOD MISS / BAD MISS: HOLD**","",
              "김민선7은 230→270yd로 갈수록 시즌 관측 FW 비율이 떨어지지 않으면서 남은 거리 구간의 Birdie+가 상승한다. 이예원은 230yd 구간에서 FW 유지력이 특히 높고, 거리를 늘릴수록 FW 비율이 소폭 낮아지는 대신 짧은 어프로치의 보상을 얻는다.",
              "","이 결과는 전략의 최종 정답이 아니다. 실제 8H 공간 좌표, 위험지역, 선수별 좌우 분산을 결합하기 전에는 특정 타깃을 확정하지 않는다."]
    MD.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(OUT); print(MD)

if __name__=="__main__": main()
