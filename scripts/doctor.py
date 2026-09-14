#!/usr/bin/env python3
"""환경 진단 — 이 패키지에서 다이어그램을 그릴 때 선택될 렌더 경로를 알려준다.

Python 3.9+ 표준 라이브러리만 사용한다. 실행 예:

    python3 scripts/doctor.py               # 사람이 읽는 요약
    python3 scripts/doctor.py --json        # 기계 판독 출력
"""
from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
BUNDLED_FLOWMAP = SKILL_ROOT / "assets" / "repo-flowmap" / "scripts"

ARCHIFY_CANDIDATES = [
    os.environ.get("C4_ARCHIFY_ROOT", ""),
    SKILL_ROOT.parent / "archify",
    Path.home() / ".pi" / "agent" / "skills" / "archify",
    Path.home() / ".claude" / "skills" / "archify",
    Path.home() / ".agents" / "skills" / "archify",
]


def node_version() -> tuple[bool, str]:
    if not shutil.which("node"):
        return False, "node not found"
    try:
        out = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=15)
        version = out.stdout.strip()
        parts = version.lstrip("v").split(".")
        major = int(parts[0]) if parts and parts[0].isdigit() else -1
        return (out.returncode == 0 and major >= 18), version
    except (OSError, ValueError):
        return False, "node --version failed"


def archify_status(node_ok: bool) -> dict[str, object]:
    for candidate in ARCHIFY_CANDIDATES:
        if not candidate:
            continue
        root = Path(candidate).expanduser().resolve()
        entry = root / "bin" / "archify.mjs"
        if not entry.is_file():
            continue
        if not node_ok:
            return {"available": False, "root": str(root), "reason": "Node 18+ required"}
        try:
            out = subprocess.run(
                ["node", str(entry), "doctor"],
                capture_output=True, text=True, timeout=60,
            )
            ok = out.returncode == 0
            detail = "doctor ok" if ok else f"doctor exit {out.returncode}"
            return {"available": ok, "root": str(root), "reason": detail}
        except OSError as exc:
            return {"available": False, "root": str(root), "reason": str(exc)}
    return {"available": False, "root": None, "reason": "archify skill root not found (candidates: C4_ARCHIFY_ROOT, sibling skills dir, ~/.pi|~/.claude|~/.agents/skills/archify)"}


def flowmap_status(node_ok: bool) -> dict[str, object]:
    scripts = sorted(p.name for p in BUNDLED_FLOWMAP.glob("*.mjs"))
    present = {"validate_flowmap.mjs", "build_flowmap.mjs"}.issubset(set(scripts))
    return {
        "available": bool(present and node_ok),
        "root": str(BUNDLED_FLOWMAP.parent),
        "reason": "bundled" if present else "bundled scripts missing",
    }


def chosen_path(archify: dict, flowmap: dict, node_ok: bool) -> str:
    if archify["available"]:
        return "archify (기본 경로)"
    if flowmap["available"]:
        return "repo-flowmap (번들 폴백 — archify 미가용)" + ("" if node_ok else "")
    if node_ok:
        return "repo-flowmap 불가(번들 손상) → Structurizr → Mermaid/PlantUML → ASCII"
    return "Node 없음 → Structurizr → Mermaid/PlantUML → ASCII (텍스트 폴백)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    try:
        py = f"{sys.version_info.major}.{sys.version_info.minor}"
        py_ok = (sys.version_info.major, sys.version_info.minor) >= (3, 9)
    except Exception:  # pragma: no cover
        py, py_ok = "unknown", False
    node_ok, node_v = node_version()
    archify = archify_status(node_ok)
    flowmap = flowmap_status(node_ok)
    report = {
        "python": {"version": py, "ok": py_ok},
        "node": {"version": node_v, "ok": node_ok},
        "archify": archify,
        "repoFlowmap": flowmap,
        "chosenPath": chosen_path(archify, flowmap, node_ok),
    }
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("C4 skill doctor")
        print(f"  python        : {report['python']['version']} {'[ok]' if py_ok else '[!] 3.9+ 필요'}")
        print(f"  node          : {report['node']['version'] or '-'} {'[ok]' if node_ok else '[!] 18+ 필요'}")
        mark = "[ok]" if archify["available"] else "[--]"
        print(f"  archify       : {mark} {archify.get('root') or ''} ({archify['reason']})")
        mark = "[ok]" if flowmap["available"] else "[!]"
        print(f"  repo-flowmap  : {mark} 번들 ({flowmap['reason']})")
        print(f"  선택될 경로   : {report['chosenPath']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
