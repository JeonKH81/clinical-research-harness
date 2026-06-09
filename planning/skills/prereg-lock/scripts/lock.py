#!/usr/bin/env python3
"""
lock.py — Pre-registration 기록·검증·amendment (Soft 기록 모델)

본 하네스 v1의 정책: 사전등록 정보를 SHA-256 해시로 *기록*하되,
파일 권한 강제(chmod)나 변경 차단은 하지 않는다 (informed-consent 모델).
변경 시 evolution_log에 자동 기록되어 학술 무결성 트레일은 자연스럽게 유지된다.

진짜 비가역 사전등록을 원하면 OSF·AsPredicted·ClinicalTrials.gov 같은
외부 timestamping 서비스를 함께 사용하는 것을 권고.

사용법:
    # 기록 (record)
    python lock.py lock --project PCI-MVD-2026 --hypothesis-input draft.json

    # 무결성 검증 (해시 불일치 시 경고만, 차단 안 함)
    python lock.py verify --project PCI-MVD-2026

    # Amendment (선택 절차 — 정식 변경 사유 기록 원할 때)
    python lock.py amend --project PCI-MVD-2026 --reason "..." --new-input new.json
"""

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
from datetime import datetime, timezone


def workspace_path(project, *parts):
    base = os.environ.get("HARNESS_WORKSPACE", "workspace")
    return os.path.join(base, project, *parts)


def canonical_json(obj):
    """재현 가능한 정규형 JSON (정렬, UTF-8, no whitespace 변동)."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def compute_hash(prereg_dict):
    """hash 필드 제외하고 canonical form으로 SHA-256."""
    payload = {k: v for k, v in prereg_dict.items() if k != "hash"}
    h = hashlib.sha256(canonical_json(payload)).hexdigest()
    return f"sha256:{h}"


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat()


def load_input(path):
    with open(path) as f:
        return json.load(f)


def lock(args):
    prereg_path = workspace_path(args.project, "phase2_hypothesis", "prereg.json")
    if os.path.exists(prereg_path):
        print(f"[ERROR] prereg.json already exists at {prereg_path}", file=sys.stderr)
        print("        Use 'amend' to make changes after lock.", file=sys.stderr)
        sys.exit(2)

    user_input = load_input(args.hypothesis_input)
    prereg = {
        "prereg_id": user_input.get("prereg_id", f"{args.project}-001"),
        "version": 1,
        "locked_at": now_iso(),
        "researcher": user_input.get("researcher", os.environ.get("USER", "unknown")),
        "project": args.project,
        "hypothesis": user_input["hypothesis"],
        "analysis_plan": user_input["analysis_plan"],
        "data_provenance": user_input.get("data_provenance", {}),
        "amendment_log": []
    }
    prereg["hash"] = compute_hash(prereg)

    os.makedirs(os.path.dirname(prereg_path), exist_ok=True)
    with open(prereg_path, "w") as f:
        json.dump(prereg, f, ensure_ascii=False, indent=2)

    # Soft 기록 모델: chmod 444 제거 (옵션 B). 파일은 일반 권한 유지.
    # 변경 시 evolution_log에 자동 기록되지만 시스템 차원 차단은 안 함.

    print(f"[RECORDED] {prereg_path}")
    print(f"  hash: {prereg['hash']}")
    print(f"  locked_at: {prereg['locked_at']}")

    _evolution_log(args.project, "PREREG_RECORDED", {
        "version": 1, "hash": prereg["hash"]
    })


def verify(args):
    prereg_path = workspace_path(args.project, "phase2_hypothesis", "prereg.json")
    if not os.path.exists(prereg_path):
        print(f"[FAIL] prereg.json not found: {prereg_path}", file=sys.stderr)
        sys.exit(2)

    with open(prereg_path) as f:
        prereg = json.load(f)

    stored_hash = prereg.get("hash")
    computed = compute_hash(prereg)
    ok = stored_hash == computed

    print(f"  stored:   {stored_hash}")
    print(f"  computed: {computed}")
    if ok:
        print("[OK] Pre-registration integrity verified")
        sys.exit(0)
    else:
        print("[WARN] HASH MISMATCH — prereg.json was modified after recording.",
              file=sys.stderr)
        print("        This is allowed (Soft recording model), but logged for audit trail.",
              file=sys.stderr)
        _evolution_log(args.project, "PREREG_HASH_DRIFT", {
            "stored": stored_hash, "computed": computed,
            "note": "User modified prereg.json directly. Allowed but recorded."
        })
        sys.exit(0)  # 경고만, 차단 안 함


def amend(args):
    prereg_path = workspace_path(args.project, "phase2_hypothesis", "prereg.json")
    if not os.path.exists(prereg_path):
        print(f"[ERROR] prereg.json not found: {prereg_path}", file=sys.stderr)
        sys.exit(2)

    with open(prereg_path) as f:
        old = json.load(f)

    # 백업
    old_version = old["version"]
    backup_path = workspace_path(args.project, "phase2_hypothesis",
                                 f"prereg_v{old_version}.json")
    shutil.copy2(prereg_path, backup_path)
    # Soft 모델: 백업도 read-only 권한 강제 안 함

    # 새 prereg
    new_input = load_input(args.new_input)
    new_prereg = {
        "prereg_id": old["prereg_id"],
        "version": old_version + 1,
        "locked_at": now_iso(),
        "researcher": old["researcher"],
        "project": args.project,
        "hypothesis": new_input.get("hypothesis", old["hypothesis"]),
        "analysis_plan": new_input.get("analysis_plan", old["analysis_plan"]),
        "data_provenance": new_input.get("data_provenance", old.get("data_provenance", {})),
        "amendment_log": old["amendment_log"] + [{
            "amended_at": now_iso(),
            "previous_hash": old["hash"],
            "previous_version": old_version,
            "reason": args.reason,
            "amended_by": os.environ.get("USER", "unknown")
        }]
    }
    new_prereg["hash"] = compute_hash(new_prereg)

    # Soft 모델: 권한 조작 없음
    with open(prereg_path, "w") as f:
        json.dump(new_prereg, f, ensure_ascii=False, indent=2)

    print(f"[AMENDED] {prereg_path}")
    print(f"  previous version: {old_version} → {new_prereg['version']}")
    print(f"  previous hash: {old['hash']}")
    print(f"  new hash:      {new_prereg['hash']}")
    print(f"  reason: {args.reason}")

    _evolution_log(args.project, "PREREG_AMENDED", {
        "from_version": old_version, "to_version": new_prereg["version"],
        "reason": args.reason, "new_hash": new_prereg["hash"]
    })


def _evolution_log(project, event, payload):
    log_path = workspace_path(project, "evolution_log.md")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a") as f:
        f.write(f"\n## {now_iso()} — {event}\n")
        f.write("```json\n")
        f.write(json.dumps(payload, ensure_ascii=False, indent=2))
        f.write("\n```\n")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)

    pl = sp.add_parser("lock")
    pl.add_argument("--project", required=True)
    pl.add_argument("--hypothesis-input", required=True,
                    help="JSON with hypothesis + analysis_plan")
    pl.set_defaults(func=lock)

    pv = sp.add_parser("verify")
    pv.add_argument("--project", required=True)
    pv.set_defaults(func=verify)

    pa = sp.add_parser("amend")
    pa.add_argument("--project", required=True)
    pa.add_argument("--reason", required=True)
    pa.add_argument("--new-input", required=True)
    pa.set_defaults(func=amend)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
