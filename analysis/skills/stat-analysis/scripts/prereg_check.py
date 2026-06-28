#!/usr/bin/env python3
"""
prereg_check.py — 사전등록(prereg.json) 무결성 자체 검증 (분석 하네스 독립 유틸)

분석 하네스(clinical-research-analysis)는 계획 하네스의 prereg-lock 스킬에
의존하지 않습니다. 이 스크립트는 계획 하네스 lock.py의 verify 로직과 동일한
canonical-form SHA-256 해시 계산을 자체적으로 수행해, 핸드오프된 prereg.json이
기록 이후 변경되었는지(드리프트) 점검합니다.

정책 (Soft 기록 모델, lock.py와 동일):
- 해시 불일치는 차단하지 않고 경고 + evolution_log에 PREREG_HASH_DRIFT 기록
- prereg.json 부재 시: 분석은 가능하나 confirmatory/exploratory 구분 없이 모두
  exploratory로 처리됨을 알림 (반환 코드 0)

사용법:
    python prereg_check.py --project PCI-MVD-2026
    python prereg_check.py --prereg path/to/prereg.json --project PCI-MVD-2026
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone


def workspace_path(project, *parts):
    base = os.environ.get("HARNESS_WORKSPACE", "workspace")
    return os.path.join(base, project, *parts)


def canonical_json(obj):
    """재현 가능한 정규형 JSON (정렬, UTF-8, no whitespace 변동) — lock.py와 동일."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def compute_hash(prereg_dict):
    """hash 필드 제외하고 canonical form으로 SHA-256 — lock.py와 동일."""
    payload = {k: v for k, v in prereg_dict.items() if k != "hash"}
    h = hashlib.sha256(canonical_json(payload)).hexdigest()
    return f"sha256:{h}"


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat()


def _evolution_log(project, event, payload):
    log_path = workspace_path(project, "evolution_log.md")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a") as f:
        f.write(f"\n## {now_iso()} — {event}\n")
        f.write("```json\n")
        f.write(json.dumps(payload, ensure_ascii=False, indent=2))
        f.write("\n```\n")


def main():
    ap = argparse.ArgumentParser(description="Self-contained prereg integrity check (Soft model)")
    ap.add_argument("--project", required=True)
    ap.add_argument("--prereg", default=None,
                    help="prereg.json 경로 (기본: workspace/{project}/phase2_hypothesis/prereg.json)")
    args = ap.parse_args()

    prereg_path = args.prereg or workspace_path(args.project, "phase2_hypothesis", "prereg.json")

    if not os.path.exists(prereg_path):
        # Soft 모델: 부재는 차단이 아님. 모든 분석을 exploratory로 처리.
        print(f"[NOTE] prereg.json not found: {prereg_path}", file=sys.stderr)
        print("       사전등록이 없어 confirmatory/exploratory 구분 없이 모든 분석이 "
              "exploratory로 처리됩니다 (BH-FDR).", file=sys.stderr)
        _evolution_log(args.project, "PREREG_ABSENT", {
            "path": prereg_path,
            "note": "No pre-registration. All analyses treated as exploratory."
        })
        sys.exit(0)

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
        print("        Allowed (Soft recording model), but logged for audit trail.",
              file=sys.stderr)
        _evolution_log(args.project, "PREREG_HASH_DRIFT", {
            "stored": stored_hash, "computed": computed,
            "note": "Detected by analysis harness prereg_check.py. Allowed but recorded."
        })
        sys.exit(0)  # 경고만, 차단 안 함


if __name__ == "__main__":
    main()
