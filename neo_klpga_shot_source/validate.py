import argparse, json, sqlite3

KNOWN_STATE = {"1","2","3","4","5","6","7","8","9","10","12"}

ap = argparse.ArgumentParser()
ap.add_argument("db"); ap.add_argument("--game", required=True)
a = ap.parse_args()

con = sqlite3.connect(a.db)
rows = con.execute(
    "SELECT player_code,round,hole,shot,state_code,state_name_ko FROM klpga_player_shot WHERE game_code=? ORDER BY player_code,round,hole,shot",
    (a.game,),
).fetchall()

# An unmapped code is NOT a failure by itself -- it is explicitly tolerated as
# long as the collector preserved it as UNKNOWN_<code> (never guessed) and
# logged it. Only a code missing from the known table AND NOT tagged
# UNKNOWN_<code> in state_name_ko would indicate the collector silently
# dropped/mis-mapped it -- that is the real bug this check guards against.
unmapped_untagged = sorted({
    r[4] for r in rows
    if r[4] is not None and r[4] not in KNOWN_STATE and r[5] != f"UNKNOWN_{r[4]}"
})
unknown_codes_present = sorted({r[4] for r in rows if r[4] is not None and r[4] not in KNOWN_STATE})

dup = con.execute(
    "SELECT COUNT(*) FROM (SELECT player_code,round,hole,shot,COUNT(*) c FROM klpga_player_shot WHERE game_code=? GROUP BY 1,2,3,4 HAVING c>1)",
    (a.game,),
).fetchone()[0]

groups = {}
for p, r, h, s, st, _ in rows:
    groups.setdefault((p, r, h), []).append(s)
nonseq = sum(1 for shots in groups.values() if sorted(shots) != list(range(1, len(shots) + 1)))

holed = sum(1 for *_, st, _ in rows if st == "10")

report = {
    "game": a.game,
    "shots": len(rows),
    "player_round_holes": len(groups),
    "holed": holed,
    "duplicate_keys": dup,
    "nonsequential_holes": nonseq,
    "unknown_pp_state_values_preserved": unknown_codes_present,
    "codes_neither_known_nor_tagged_unknown": unmapped_untagged,
}
print(json.dumps(report, ensure_ascii=False, indent=2))

assert dup == 0, "duplicate shot keys found"
assert nonseq == 0, "non-sequential shot numbers within a hole found"
assert not unmapped_untagged, "a pp_state code was neither mapped nor tagged UNKNOWN_<code> -- collector bug"
print("VALIDATION: PASS")
