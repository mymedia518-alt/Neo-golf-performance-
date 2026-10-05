from __future__ import annotations
import csv
from pathlib import Path

HERE = Path(__file__).parent

# ============================================================
# neo_asymmetric_findings.csv -- 12 real, non-manufactured findings,
# each red-teamed against the 10 alternative-explanation checks
# ============================================================
findings = [
    {"id": "AF01", "finding": "R1H16: 유해란 2nd샷과 박서현 1st샷이 동일 좌표(60,14), 핀까지 2.7yd에서 만남 — 박서현 1퍼트 vs 유해란 2퍼트",
     "category": "같은 위치, 다른 스코어", "n": 1, "repeat_count": 1,
     "alt_explanations_checked": "핀 다름?No(같은 라운드,같은 핀). lie 다름?No(둘 다 GREEN). 표본 작음?Yes(n=1, 단일 사례).",
     "confidence": "MEDIUM", "note": "좌표가 문자 그대로 일치하는 희귀 사례라 정성적 가치는 높지만 n=1, 일반화 금지"},
    {"id": "AF02", "finding": "R1H3: GREENSIDE_BUNKER 12.1yd(유해란)/12.5yd(박서현) — 유해란 Par, 박서현 Double. recovery 샷 자체가 10.1yd vs 5.1yd 이동(그린 도달 여부)",
     "category": "같은 미스, 다른 회복", "n": 1, "repeat_count": 1,
     "alt_explanations_checked": "핀 다름?No. lie 다름?No. 벙커 라이 품질?UNKNOWN(RAW 미기록). 표본?n=1",
     "confidence": "MEDIUM", "note": "RAW에 벙커 lie 품질(묻힘 여부)이 없어 실행 차이의 '원인'은 추정 금지, '결과'만 확인 가능"},
    {"id": "AF03", "finding": "Hole 9: 필드 전체 기준 par4 평균보다 쉬움(+0.127 vs +0.258) — 그런데 박서현은 R3H9(Double), R3(또다른 par4), R13(Bogey+)에서도 반복 '선수위험높음' 분류",
     "category": "코스위험↔선수위험 분리", "n": 331, "repeat_count": 3,
     "alt_explanations_checked": "표본?n=331(field), 반복 3홀. 핀 다름?통제됨(각 홀 field aggregate). 우연 1회?No(3개 다른 홀에서 반복).",
     "confidence": "HIGH", "note": "course_player_risk_matrix.csv에서 독립적으로 재확인, n도 충분하고 반복됨"},
    {"id": "AF04", "finding": "이재윤의 ROUGH(0-50yd) 회복: 필드 평균 +0.673 vs 이재윤 개인 +0.286 (n=14) — 필드 불리/선수 유리 유일한 구간",
     "category": "필드-선수 가치 역전", "n": 1064, "repeat_count": 14,
     "alt_explanations_checked": "표본?필드 n=1064(충분), 이재윤 n=14(중간). 퍼팅 변동성?일부 가능성 있음(최종 스코어 기준이라 퍼팅도 섞임).",
     "confidence": "MEDIUM", "note": "field_vs_player_location_value.csv에서 유일하게 역전된 구간 — 이재윤의 숨겨진 강점 후보"},
    {"id": "AF05", "finding": "FW MISS -> Par/Birdie+(49건) > FW HIT -> Bogey+(21건), 3선수 합산 168 non-par3 hole-play 중",
     "category": "FW% 역설", "n": 168, "repeat_count": 49,
     "alt_explanations_checked": "표본?n=168 충분. 과대해석 위험: 'FW는 중요하지 않다'는 결론 금지 — FW_HIT_GOOD(78건)이 가장 큰 범주임을 병기.",
     "confidence": "HIGH", "note": "neo_fairway_paradox_cases.csv. FW%가 설명 못하는 지점을 보여줄 뿐, FW 무의미론은 아님"},
    {"id": "AF06", "finding": "GIR 달성 홀(138건) 중 13건 Bogey, 1건 Double+ — GIR 미스 홀(78건) 중 45건은 오히려 Par로 끝남",
     "category": "GIR 역설", "n": 216, "repeat_count": 14,
     "alt_explanations_checked": "표본?충분. 퍼팅 변동성이 GIR-Bogey의 주 원인일 가능성 높음(별도 검증 필요, 본 파일에서는 현상만 확인).",
     "confidence": "HIGH", "note": "neo_gir_paradox_cases.csv. GIR 이진지표가 숨기는 정보를 정량적으로 보여줌"},
    {"id": "AF07", "finding": "GIR 후 첫퍼트 6-9yd/9-12yd/12yd+ 구간에서 이재윤의 버디 전환율이 필드 평균보다도 낮음(0% vs 필드 10.8%/5.7%/2.5%)",
     "category": "거리구간별 선수차", "n": 29, "repeat_count": 3,
     "alt_explanations_checked": "표본?구간별 n=7~13(작음, MEDIUM 이하로 제한). 거리 자체가 원인(A)인지 전환력(B)인지: 거리 통제 후에도 낮아 B 가능성 시사.",
     "confidence": "MEDIUM", "note": "approach_proximity_conversion.csv. n이 작아 HIGH로 격상하지 않음 — '이재윤 거리 통제해도 낮다'는 가설이지 확정 아님"},
    {"id": "AF08", "finding": "GREEN 0-3yd 구간이 필드 기준 '중립'(위험 아님)이지만 bogey+ 비율 34% — 직관적 기대(거의 자동 Par)보다 훨씬 높음",
     "category": "방법론적 발견", "n": 6038, "repeat_count": 1,
     "alt_explanations_checked": "이 구간은 '처음 도착' 위치와 '이미 놓친 후 남은 퍼트' 위치가 섞여 있음 — 순수 approach 품질 지표 아님. 방법론 한계로 명시.",
     "confidence": "HIGH(방법론 한계로서)", "note": "next-shot-quality 해석 시 GREEN 구간은 '그 결과로 가는 길'이 아니라 '그 지점에 섰을 때의 결과'로 읽어야 함"},
    {"id": "AF09", "finding": "ROUGH 200yd+ 필드 double+ 비율 60%, FAIRWAY 200yd+도 40% — 장거리 미스는 FW 여부와 무관하게 전 필드에게 치명적",
     "category": "코스위험(공통)", "n": 86, "repeat_count": 1,
     "alt_explanations_checked": "표본?ROUGH 200+ n=37, FAIRWAY 200+ n=43 — 작지만 방향 일관됨. 특정 홀 집중 여부는 미검증(추가 분석 가능).",
     "confidence": "MEDIUM", "note": "neo_next_shot_quality.csv 최하위 2개 구간 — 코스 전체의 공통 고위험 구간"},
    {"id": "AF10", "finding": "Hole 1(par4): 필드 기준 '코스위험높음'(+0.369)인데 박서현이 세 선수 중 유일하게 평균 이하(-0.25, 낮음) 기록",
     "category": "필드불리/선수유리", "n": 331, "repeat_count": 1,
     "alt_explanations_checked": "표본?박서현 개인 n=4(작음, 1라운드씩). 단 1회 좋은 결과가 평균을 끌어올렸을 가능성 있음 — 반복성 미검증.",
     "confidence": "LOW", "note": "n=4로 결론 내리기엔 이름. '약한 선수도 특정 코스위험 홀에서 예외적으로 강할 수 있다'는 가능성 제시 수준"},
    {"id": "AF11", "finding": "같은 GREEN ~3.4yd 지점에서 박서현(R4H9)이 유해란의 여러 다른 홀(R1H6,R2H1,R2H2,R2H6) 대비 반복적으로 strokes-to-finish가 더 걺(2 vs 4)",
     "category": "반복된 선수 패턴", "n": 4, "repeat_count": 4,
     "alt_explanations_checked": "같은 사건(R4H9)이 유해란의 여러 홀과 매칭된 것이라 '4번 반복'이 아니라 '1개 사건이 4번 비교된 것' — 실제 독립 반복 횟수는 1.",
     "confidence": "LOW(반복 아님, 재확인 결과 단일 사건)", "note": "same_location_player_execution.csv 재검토 결과 중복 비교였음을 확인 — 레드팀에서 신뢰도 하향"},
    {"id": "AF12", "finding": "0-3yd 버디 전환율에서 박서현 100%(n=1)로 표에 표시되지만 이는 통계적으로 무의미",
     "category": "레드팀 기각 후보", "n": 1, "repeat_count": 1,
     "alt_explanations_checked": "표본 극소(n=1) — 어떤 해석도 금지.",
     "confidence": "REJECTED(표본부족)", "note": "approach_proximity_conversion.csv의 0-3yd 박서현 행은 report에서 인용 금지"},
]

with open(HERE / "neo_asymmetric_findings.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(findings[0].keys()))
    w.writeheader()
    w.writerows(findings)
print(f"neo_asymmetric_findings.csv: {len(findings)} findings written (incl. 2 red-team-downgraded)")


# ============================================================
# three_player_decision_cards.csv -- 3-5 per player, NO RECOMMENDATION
# where evidence is insufficient
# ============================================================
cards = [
    # 유해란
    {"player": "유해란", "card_id": "RYU01", "홀_상황": "그린 적중 후 3~6yd 이내 첫 퍼트",
     "출발조건": "GIR 달성, 첫 퍼트 3~6yd", "권장위치후보": "해당없음(퍼팅 전략 카드)",
     "허용가능위치후보": "해당없음", "고위험위치후보": "해당없음",
     "예상다음샷조건": "본인 GIR-hole 평균 첫퍼트 7.06yd대에서 버디전환 28.3%(최고치)지만 3-putt 사례(R1H16 2.7yd, R1H10 3.4yd)가 반복 관찰됨",
     "필드근거": "GREEN 3-6yd 필드 전체 par+65%,bogey+35%(n=1195)", "선수개인근거": "n=17, par%=76.5%, bogey+%=5.9%(approach_proximity_conversion.csv)",
     "신뢰도": "MEDIUM(개인 n=17 중간)", "의사결정변화": "짧은 거리 makeable range에서의 루틴 점검 — '퍼팅 더 잘해라'가 아니라 특정 3~6yd 구간 루틴 점검"},
    {"player": "유해란", "card_id": "RYU02", "홀_상황": "티샷 미스 후 회복 국면(러프/벙커/페널티 발생 홀)",
     "출발조건": "비정상적 시작(러프, 벙커, 로스트볼 등)", "권장위치후보": "그린을 직접 노리기보다 페어웨이 복귀 우선(R3H6 사례 근거)",
     "허용가능위치후보": "그린 적중 실패해도 짧은 칩 거리 확보", "고위험위치후보": "UNKNOWN(표본 부족 — 그녀의 큰 손실 사례가 1건뿐이라 '고위험 위치'를 특정할 표본이 없음)",
     "예상다음샷조건": "R3H6(로스트볼+페널티)에서도 보기로 막은 사례가 유일 Double+ 외 그녀의 전형적 패턴",
     "필드근거": "ROUGH 0-50yd 필드 bogey+54%(n=1064)", "선수개인근거": "72홀 중 Double+ 1회뿐(그 자체가 근거)",
     "신뢰도": "MEDIUM(패턴 1회, 반복성 추가 토너먼트 필요)", "의사결정변화": "나쁜 시작에서도 '그린을 직접 노리지 않아도 된다'는 damage-control 지침은 실제 근거 있음"},
    {"player": "유해란", "card_id": "RYU03", "홀_상황": "일반 상황(해당 없음 — 표본 부족으로 추천 보류)",
     "출발조건": "NO RECOMMENDATION", "권장위치후보": "NO RECOMMENDATION",
     "허용가능위치후보": "NO RECOMMENDATION", "고위험위치후보": "NO RECOMMENDATION",
     "예상다음샷조건": "NO RECOMMENDATION", "필드근거": "NO RECOMMENDATION", "선수개인근거": "NO RECOMMENDATION",
     "신뢰도": "NO RECOMMENDATION", "의사결정변화": "그녀의 티샷 landing corridor별 세부 권장은 이번 분석(72홀, 4라운드)만으로는 홀별 n이 1~2에 불과해 특정 corridor를 권장할 근거 부족"},
    # 이재윤
    {"player": "이재윤", "card_id": "LEE01", "홀_상황": "그린 적중, 6~12yd 첫 퍼트권",
     "출발조건": "GIR 달성이지만 핀에서 6yd 이상", "권장위치후보": "approach club 선택 시 7yd 이내 진입을 목표 proximity로 설정",
     "허용가능위치후보": "9-12yd(필드도 버디율 낮은 구간, 열세가 field 수준)", "고위험위치후보": "해당없음(그의 Bogey+ 비율 자체는 낮음)",
     "예상다음샷조건": "6-9yd 버디 0%(n=13, 필드 10.8%), 9-12yd 버디 0%(n=9, 필드 5.7%) — 거리 통제해도 필드보다 낮음",
     "필드근거": "approach_proximity_conversion.csv 각 구간 FIELD 행", "선수개인근거": "같은 파일 이재윤 행, n=13/9(중간 표본)",
     "신뢰도": "MEDIUM(구간별 n 10 내외)", "의사결정변화": "'그린을 더 맞혀라'가 아니라 '맞힌 그린에서 더 가깝게' — 구체적으로 다른 지침"},
    {"player": "이재윤", "card_id": "LEE02", "홀_상황": "러프 미스, 50yd 이내 근거리 회복",
     "출발조건": "ROUGH, 50yd 이내", "권장위치후보": "해당없음(회복 실행 자체가 강점)",
     "허용가능위치후보": "이 구간은 그에게 필드보다 유리한 구간으로 확인됨", "고위험위치후보": "해당없음",
     "예상다음샷조건": "필드 평균 +0.673(bogey+54%) 대비 이재윤 개인 +0.286(n=14)",
     "필드근거": "field_vs_player_location_value.csv ROUGH 0-50yd 필드행(n=1064)", "선수개인근거": "같은 파일 이재윤행(n=14)",
     "신뢰도": "MEDIUM(개인 n=14)", "의사결정변화": "이 구간에서는 보수적 조정이 불필요 — 그의 실제 강점이므로 전략 변경 금지가 오히려 지침"},
    {"player": "이재윤", "card_id": "LEE03", "홀_상황": "일반 상황",
     "출발조건": "NO RECOMMENDATION", "권장위치후보": "NO RECOMMENDATION", "허용가능위치후보": "NO RECOMMENDATION",
     "고위험위치후보": "NO RECOMMENDATION", "예상다음샷조건": "NO RECOMMENDATION", "필드근거": "NO RECOMMENDATION",
     "선수개인근거": "NO RECOMMENDATION", "신뢰도": "NO RECOMMENDATION",
     "의사결정변화": "티샷 corridor별 세부 추천은 홀당 n=4로 근거 부족"},
    # 박서현
    {"player": "박서현", "card_id": "PARK01", "홀_상황": "Hole 8 공격 강도",
     "출발조건": "Hole 8 티잉 구역", "권장위치후보": "그린 중앙 타겟(핀 공략 지양)",
     "허용가능위치후보": "페어웨이 중앙~약간 짧은 지점", "고위험위치후보": "페널티 구역 인접 approach 라인(R3H8 실제 사례)",
     "예상다음샷조건": "필드 전체도 이 홀에서 평균보다 나쁨(+0.387, double+10.3%, n=331) — 코스 자체 위험",
     "필드근거": "course_player_risk_matrix.csv Hole 8행(field n=331)", "선수개인근거": "같은 파일 박서현 Hole8행(개인 n=4, avg+1.0, 고위험)",
     "신뢰도": "HIGH(코스위험은 필드 n=331로 확증, 선수위험은 n=4로 MEDIUM)", "의사결정변화": "이 홀은 전체 필드 근거로도 보수적 접근이 정당화됨 — 그녀만의 문제로 축소하지 말 것"},
    {"player": "박서현", "card_id": "PARK02", "홀_상황": "Hole 9 공격 강도",
     "출발조건": "Hole 9 티잉 구역", "권장위치후보": "UNKNOWN(이 홀은 필드 전체엔 쉬운 홀이라 '권장 위치'를 코스 위험으로 정당화할 수 없음)",
     "허용가능위치후보": "UNKNOWN", "고위험위치후보": "그녀 개인 반복 패턴(R3,R4에서 확인, R1은 정상)",
     "예상다음샷조건": "필드는 평균보다 쉬움(+0.127, n=331)인데 그녀는 R3/R4에서 반복 고위험",
     "필드근거": "course_player_risk_matrix.csv Hole9행(field n=331, 낮음)", "선수개인근거": "같은 파일(개인 n=4, avg+1.0, 높음) + 3,13번홀 유사 반복(AF03)",
     "신뢰도": "HIGH(반복 3개 홀 패턴)", "의사결정변화": "이건 코스 탓이 아니라 그녀 개인의 반복 패턴 — 코치/캐디가 '이 홀은 원래 어렵다'고 넘기면 안 됨"},
    {"player": "박서현", "card_id": "PARK03", "홀_상황": "그린사이드 벙커 미스(10~13yd권)",
     "출발조건": "GREENSIDE_BUNKER, 핀까지 10~13yd", "권장위치후보": "해당없음(미스 자체가 아니라 회복 실행이 핵심)",
     "허용가능위치후보": "이 거리의 벙커 미스 자체는 필드 전체에도 위험(R1H3 field n=16, avg+0.688)",
     "고위험위치후보": "회복샷이 그린에 도달하지 못하는 경우(R1H3 실제 사례, 5.1yd만 전진)",
     "예상다음샷조건": "유해란은 같은 거리에서 10.1yd 전진, 그린 직행 — 회복 '거리 자체'가 차이",
     "필드근거": "three_player_field_spatial_validation.csv r1h3_greenside_bunker_field(n=16)", "선수개인근거": "casebook Case 4, n=1(단일 사례)",
     "신뢰도": "MEDIUM(미스 자체는 필드 n=16으로 확증, 회복 차이는 n=1)", "의사결정변화": "벙커 회복 거리 컨트롤 특정 연습 — '벙커 연습해라'보다 구체적(10~13yd 그린 도달 목표)"},
    {"player": "박서현", "card_id": "PARK04", "홀_상황": "러프 미스 전반(홀 무관)",
     "출발조건": "ROUGH, 임의 거리", "권장위치후보": "해당없음", "허용가능위치후보": "해당없음",
     "고위험위치후보": "회복 후 par-save 전환 자체가 필드 평균보다 낮음",
     "예상다음샷조건": "그녀의 러프 par-save 38%는 그녀 자신의 상대 비교(이재윤61%,유해란64%)뿐 아니라 필드 전체 46.3%(n=1152)보다도 낮음",
     "필드근거": "three_player_field_spatial_validation.csv field_rough_miss_parsave(n=1152)", "선수개인근거": "Steps5-25 보고서 기존 수치(n=16, 재인용)",
     "신뢰도": "HIGH(필드 n=1152로 확증된 real gap)", "의사결정변화": "러프 회복 전담 연습이 세 선수 비교를 넘어 필드 기준으로도 정당화됨"},
    {"player": "박서현", "card_id": "PARK05", "홀_상황": "일반 티샷 corridor",
     "출발조건": "NO RECOMMENDATION", "권장위치후보": "NO RECOMMENDATION", "허용가능위치후보": "NO RECOMMENDATION",
     "고위험위치후보": "NO RECOMMENDATION", "예상다음샷조건": "NO RECOMMENDATION", "필드근거": "NO RECOMMENDATION",
     "선수개인근거": "NO RECOMMENDATION", "신뢰도": "NO RECOMMENDATION",
     "의사결정변화": "홀별 개인 n=4로는 세부 corridor 추천 불가 — 과신 방지"},
]

with open(HERE / "three_player_decision_cards.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(cards[0].keys()))
    w.writeheader()
    w.writerows(cards)
print(f"three_player_decision_cards.csv: {len(cards)} cards (incl. NO RECOMMENDATION cards where evidence insufficient)")
