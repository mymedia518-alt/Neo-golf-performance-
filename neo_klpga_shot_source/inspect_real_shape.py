"""Read-only structural inspection of already-captured REAL raw bytes.
Never guesses the shape -- reports exactly what is present. Takes raw
response files saved verbatim by fetch()/_dump_raw() (never modified
after capture) and prints the requested structural facts without any
interpretive normalization.
"""
from __future__ import annotations
import json, sys


def describe_value(v, max_items=3):
    if isinstance(v, dict):
        return {"type": "dict", "keys": list(v.keys())}
    if isinstance(v, list):
        return {"type": "list", "len": len(v)}
    return {"type": type(v).__name__, "value_preview": (v[:200] if isinstance(v, str) else v)}


def contains_nested_json_string(v, path="$"):
    """Recursively check whether any string value in this structure is
    itself a parseable JSON document (object or array) -- reports the
    exact path and the raw string, never auto-decodes it."""
    found = []
    if isinstance(v, dict):
        for k, vv in v.items():
            found += contains_nested_json_string(vv, f"{path}.{k}")
    elif isinstance(v, list):
        for i, vv in enumerate(v):
            found += contains_nested_json_string(vv, f"{path}[{i}]")
    elif isinstance(v, str):
        s = v.strip()
        if s[:1] in "{[" and s[-1:] in "}]":
            try:
                json.loads(s)
                found.append({"path": path, "raw_string": v})
            except json.JSONDecodeError:
                pass
    return found


def inspect_group_response(raw_bytes, label):
    print(f"\n{'='*80}\nGROUP RESPONSE: {label}\n{'='*80}")
    text = raw_bytes.decode("utf-8-sig").strip()
    obj = json.loads(text)

    print("\n-- top-level keys and value types --")
    for k, v in obj.items():
        print(f"  {k}: {describe_value(v)}")

    gst = obj.get("groupShotTrackerList")
    print(f"\n-- groupShotTrackerList --")
    print(f"  type: {type(gst).__name__}")
    if isinstance(gst, dict):
        print(f"  length (number of keys): {len(gst)}")
        print(f"  keys: {list(gst.keys())}")
        for i, (k, v) in enumerate(gst.items()):
            if i >= 3:
                break
            print(f"  element[key={k!r}] type={type(v).__name__}")
            print(f"    raw value: {json.dumps(v, ensure_ascii=False)[:500]}")
    elif isinstance(gst, list):
        print(f"  length: {len(gst)}")
        for i, e in enumerate(gst[:3]):
            print(f"  element[{i}] type={type(e).__name__}")
            print(f"    raw value: {json.dumps(e, ensure_ascii=False) if not isinstance(e, str) else e[:500]}")
    else:
        print(f"  raw value: {gst!r}")

    gpl = obj.get("groupPlayerList")
    print(f"\n-- groupPlayerList --")
    print(f"  type: {type(gpl).__name__}")
    if isinstance(gpl, list):
        print(f"  length: {len(gpl)}")
        for i, e in enumerate(gpl[:3]):
            print(f"  element[{i}] (raw, verbatim): {json.dumps(e, ensure_ascii=False)}")
    else:
        print(f"  raw value: {gpl!r}")

    print(f"\n-- nested JSON-encoded strings anywhere in the response --")
    nested = contains_nested_json_string(obj)
    if nested:
        for n in nested:
            print(f"  FOUND at {n['path']}: {n['raw_string'][:300]}")
    else:
        print("  none found")

    return obj


def inspect_player_response(raw_bytes, label):
    print(f"\n{'='*80}\nPLAYER RESPONSE: {label}\n{'='*80}")
    text = raw_bytes.decode("utf-8-sig").strip()
    obj = json.loads(text)
    print("-- top-level keys and value types --")
    for k, v in obj.items():
        print(f"  {k}: {describe_value(v)}")
    stl = obj.get("shotTrackerList")
    print(f"-- shotTrackerList: type={type(stl).__name__}, len={len(stl) if hasattr(stl, '__len__') else 'n/a'}")
    for i, e in enumerate(stl[:3] if stl else []):
        print(f"  element[{i}] (raw, verbatim): {json.dumps(e, ensure_ascii=False)}")
    return obj


def cross_validate(player_objs, group_obj, group_no):
    print(f"\n{'='*80}\nCROSS-VALIDATION: per-player shotTrackerList vs group {group_no}'s groupShotTrackerList\n{'='*80}")
    gst = group_obj.get("groupShotTrackerList")
    # Flatten group shots by actual playerCode field, WITHOUT assuming
    # key order maps to any particular player -- read playerCode from
    # each shot dict itself.
    flat_group_shots = []
    if isinstance(gst, dict):
        for v in gst.values():
            if isinstance(v, list):
                flat_group_shots.extend(v)
    elif isinstance(gst, list):
        for v in gst:
            if isinstance(v, list):
                flat_group_shots.extend(v)
            elif isinstance(v, dict):
                flat_group_shots.append(v)
    group_by_player = {}
    for s in flat_group_shots:
        if isinstance(s, dict):
            group_by_player.setdefault(str(s.get("playerCode")), []).append(s)

    FIELDS = ["shot", "pp_state", "pp_x", "pp_y", "pp_greenx", "pp_greeny", "pp_distance", "pp_distanceLen", "pp_altitude"]
    all_pass = True
    for pc, pobj in player_objs.items():
        pshots = sorted(pobj.get("shotTrackerList") or [], key=lambda s: int(s["shot"]))
        gshots = sorted(group_by_player.get(str(pc), []), key=lambda s: int(s["shot"]))
        print(f"\nplayer {pc}: player_shots={len(pshots)} group_shots={len(gshots)}")
        if len(pshots) != len(gshots):
            print(f"  MISMATCH: shot count differs")
            all_pass = False
            continue
        mismatches = []
        for ps, gs in zip(pshots, gshots):
            for f in FIELDS:
                if str(ps.get(f)) != str(gs.get(f)):
                    mismatches.append(f"shot={ps.get('shot')} field={f} player={ps.get(f)!r} group={gs.get(f)!r}")
        if mismatches:
            print(f"  MISMATCHES ({len(mismatches)}):")
            for m in mismatches:
                print(f"    {m}")
            all_pass = False
        else:
            print(f"  IDENTICAL across all fields for all {len(pshots)} shots")
    print(f"\nCROSS-VALIDATION OVERALL: {'PASS' if all_pass else 'FAIL'}")
    return all_pass


if __name__ == "__main__":
    dump_dir = sys.argv[1]
    import pathlib
    d = pathlib.Path(dump_dir)

    group_raw = (d / "group_21_R4_H18.json").read_bytes()
    group_obj = inspect_group_response(group_raw, "group_21_R4_H18.json (REAL, captured verbatim)")

    player_objs = {}
    for pc, fname in [("9115", "player_9115_R4_H18.json"), ("11066", "player_11066_R4_H18.json"), ("9784", "player_9784_R4_H18.json")]:
        raw = (d / fname).read_bytes()
        player_objs[pc] = inspect_player_response(raw, f"{fname} (REAL, captured verbatim)")

    cross_validate(player_objs, group_obj, group_no="21")
