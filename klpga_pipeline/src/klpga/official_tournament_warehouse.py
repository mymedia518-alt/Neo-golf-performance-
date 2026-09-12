"""Provenance-first official KLPGA tournament evidence layer.

This is data infrastructure only; it never writes public outputs or NEO model
inputs.  Records are content addressed and missing values remain NULL.
"""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def sha256_bytes(b: bytes) -> str: return hashlib.sha256(b).hexdigest()
def _json(v): return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

def freeze_source(*, game_code: str, source_type: str, source_url: str, raw: bytes, parser_version: str = "1.0.0", out_dir: Path) -> dict:
    if not game_code or not raw: raise ValueError("SOURCE_PROVENANCE_HARD_STOP")
    h=sha256_bytes(raw); p=out_dir/f"{game_code}_{source_type}_{h}.html"
    out_dir.mkdir(parents=True, exist_ok=True)
    if p.exists() and p.read_bytes()!=raw: raise ValueError("RAW_SOURCE_CONFLICT_HARD_STOP")
    if not p.exists(): p.write_bytes(raw)
    return {"gameCode":game_code,"source_type":source_type,"source_url":source_url,"capture_timestamp":datetime.now(timezone.utc).isoformat(),"sha256":h,"parser_version":parser_version,"retrieval_status":"OK","path":str(p)}

def build_round_exposure(rows: list[dict], *, game_code: str, format: str|None=None) -> list[dict]:
    out=[]
    seen=set()
    for r in rows:
        key=(str(r.get("playerCode")),game_code,r.get("round"))
        if key in seen: raise ValueError("DUPLICATE_EXPOSURE_KEY_HARD_STOP")
        seen.add(key)
        if not r.get("playerCode") or not r.get("round"): raise ValueError("IDENTITY_OR_ROUND_HARD_STOP")
        out.append({"playerCode":str(r["playerCode"]),"gameCode":game_code,"round":r["round"],"round_played":r.get("round_played"),"round_score":r.get("round_score"),"completion_status":r.get("completion_status"),"tournament_format":format,"course":r.get("course"),"par":r.get("par"),"yardage":r.get("yardage")})
    return out

def freeze_tournament_snapshot(*, game_code: str, tournament: dict, entries: list[dict], rounds: list[dict], courses: list[dict], provenance: list[dict], out_dir: Path) -> tuple[Path, dict]:
    if not game_code: raise ValueError("MISSING_GAME_CODE_HARD_STOP")
    doc={"schema":"OFFICIAL_TOURNAMENT_WAREHOUSE_V1","gameCode":game_code,"tournament":tournament,"entries":entries,"rounds":rounds,"courses":courses,"source_manifest":provenance,"created_at":datetime.now(timezone.utc).isoformat()}
    sid=hashlib.sha256(_json(doc)).hexdigest(); doc["snapshot_id"]=sid
    out_dir.mkdir(parents=True,exist_ok=True); p=out_dir/f"{game_code}_{sid}.json"; data=json.dumps(doc,ensure_ascii=False,sort_keys=True,indent=2).encode()
    if p.exists() and p.read_bytes()!=data: raise ValueError("SNAPSHOT_CONFLICT_HARD_STOP")
    if not p.exists(): p.write_bytes(data)
    return p,doc
