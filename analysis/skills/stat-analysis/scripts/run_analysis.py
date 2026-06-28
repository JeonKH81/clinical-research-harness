#!/usr/bin/env python3
"""
run_analysis.py — 사전등록 기반 분석 *거버넌스* 헬퍼 (실제 모델링은 성숙 스킬에 위임)

설계 (wrapper 패턴, protocol-writer·manuscript-writer와 동일):
  실제 통계 모델링(Table 1, Cox/KM, 로지스틱, 진단, 플롯)은 아래 성숙한
  anthropic-skills 가 수행한다. 본 스크립트는 그것들이 하지 않는 *사전등록 거버넌스*만 책임진다.

    - Table 1            → anthropic-skills:clinical-table1
    - 생존분석(Cox/KM,
      Schoenfeld, VIF)   → anthropic-skills:survival-analysis
    - 로지스틱(OR/CI,
      Firth, TRIPOD)     → anthropic-skills:clinical-logistic-regression
    - 전체 EDA           → anthropic-skills:clinical-eda-report (Phase 4)

본 스크립트(거버넌스)가 책임지는 것:
  1) 사전등록·데이터 무결성 검증 (Soft 모델, 차단 안 함)
  2) 분석 엔진 라우팅 추천 (primary_method → 어느 성숙 스킬을 쓸지)
  3) confirmatory/exploratory 분류 + 다중비교 보정 (Bonferroni / BH-FDR)
  4) STROBE 22항목 스캐폴드 생성
  5) 재현성 메타데이터(seed, 해시) 기록

서브커맨드:
  route    사전등록을 읽어 governance.json + strobe_checklist.md 생성 (기본 흐름)
  correct  p-value 목록에 다중비교 보정 적용 (성숙 스킬 결과를 받은 뒤 호출)

사용법:
  python run_analysis.py route --prereg prereg.json --data data.csv --out phase5_analysis/
  python run_analysis.py correct --method bonferroni --alpha 0.05 \
      --pvalues primary=0.012,death=0.04,st=0.20
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone


# ---------- 무결성 (Soft 모델) ----------

def _canonical_json(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def compute_prereg_hash(prereg):
    payload = {k: v for k, v in prereg.items() if k != "hash"}
    return "sha256:" + hashlib.sha256(_canonical_json(payload)).hexdigest()


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def verify_integrity(prereg, prereg_present, data_path):
    """반환: (notes[list], data_hash 또는 None). 절대 차단하지 않는다 (informed-consent)."""
    notes = []
    if not prereg_present:
        notes.append("PREREG_ABSENT: 사전등록 없음 — 모든 분석을 exploratory로 처리 (BH-FDR).")
        return notes, None
    stored = prereg.get("hash")
    if stored is None:
        notes.append("PREREG_NO_HASH: hash 필드 없음 — 무결성 검증 불가.")
    elif stored != compute_prereg_hash(prereg):
        notes.append("PREREG_HASH_DRIFT: 기록 이후 변경됨 (허용·보고서에 노출).")
    data_hash = None
    if data_path and os.path.exists(data_path):
        data_hash = file_sha256(data_path)
        expected = (prereg.get("data_provenance") or {}).get("data_file_hash")
        if expected and expected != data_hash:
            notes.append(f"DATA_HASH_MISMATCH: expected {expected}, got {data_hash}.")
    return notes, data_hash


# ---------- 엔진 라우팅 ----------

def route_engine(primary_method):
    """primary_method 문자열 → 추천 성숙 스킬."""
    m = (primary_method or "").lower()
    if any(k in m for k in ("cox", "survival", "kaplan", "hazard", "time-to-event", "km")):
        return "anthropic-skills:survival-analysis"
    if any(k in m for k in ("logistic", "odds", "or ", "logit", "firth")):
        return "anthropic-skills:clinical-logistic-regression"
    if any(k in m for k in ("poisson", "modified poisson", "relative risk", "log-binomial")):
        return "anthropic-skills:clinical-logistic-regression (modified Poisson 안내)"
    return "MANUAL: primary_method에 맞는 성숙 스킬 없음 — 사용자/통계 확인 필요"


# ---------- confirmatory/exploratory + 다중비교 보정 ----------

def confirmatory_set(prereg):
    """사전등록 명시 가설 검정 목록 (primary + secondary)."""
    h = prereg.get("hypothesis", {}) if prereg else {}
    tests = []
    op = h.get("outcome_primary")
    if op:
        name = op.get("name") if isinstance(op, dict) else str(op)
        tests.append({"key": "primary", "outcome": name, "tier": "confirmatory"})
    for i, s in enumerate(h.get("outcomes_secondary", []) or []):
        name = s.get("name") if isinstance(s, dict) else str(s)
        tests.append({"key": f"secondary_{i+1}", "outcome": name, "tier": "confirmatory"})
    return tests


def bonferroni(pvals, alpha):
    m = len(pvals)
    out = {}
    for k, p in pvals.items():
        adj = min(1.0, p * m) if p is not None else None
        out[k] = {"p_raw": p, "p_adj": adj, "method": "bonferroni",
                  "m": m, "significant": (adj is not None and adj < alpha)}
    return out


def benjamini_hochberg(pvals, alpha):
    items = [(k, p) for k, p in pvals.items() if p is not None]
    m = len(items)
    items.sort(key=lambda kv: kv[1])
    adj = {}
    prev = 1.0
    # step-up: from largest rank to smallest, enforce monotonicity
    for rank in range(m, 0, -1):
        k, p = items[rank - 1]
        val = min(prev, p * m / rank)
        adj[k] = val
        prev = val
    out = {}
    for k, p in pvals.items():
        a = adj.get(k)
        out[k] = {"p_raw": p, "p_adj": a, "method": "benjamini-hochberg",
                  "m": m, "significant": (a is not None and a < alpha)}
    return out


def correct_pvalues(pvals, method, alpha):
    method = (method or "").lower()
    if method.startswith("bonf"):
        return bonferroni(pvals, alpha)
    if method.startswith("bh") or "benjamini" in method or "fdr" in method:
        return benjamini_hochberg(pvals, alpha)
    raise ValueError(f"Unknown correction method: {method} (use bonferroni | bh)")


# ---------- STROBE 스캐폴드 ----------

def strobe_scaffold(prereg):
    h = prereg.get("hypothesis", {}) if prereg else {}
    ap = prereg.get("analysis_plan", {}) if prereg else {}
    auto = lambda v: v if v else "todo"
    return {
        "1_title_abstract": "todo (manuscript)",
        "2_background": "todo (Phase 1 research_opportunities.md)",
        "3_objectives": auto(h.get("outcome_primary")),
        "4_study_design": auto(h.get("design")),
        "5_setting": "todo",
        "6_participants": auto(h.get("population")),
        "7_variables": "auto (variable_mapping.json)",
        "8_data_sources": "todo (data_dictionary)",
        "9_bias": "todo (Phase 4 feasibility_report.md 4항목)",
        "10_study_size": auto(h.get("effect_size_assumption")),
        "11_quantitative_vars": "auto (clinical-table1)",
        "12_statistical_methods": auto(ap.get("primary_method")),
        "13_participants_flow": "todo (manuscript flow diagram)",
        "14_descriptive_data": "auto (clinical-table1)",
        "15_outcome_data": "auto (성숙 스킬 결과)",
        "16_main_results": "auto (effect size + 95% CI 강제)",
        "17_other_analyses": "auto (secondary/sensitivity/exploratory)",
        "18_key_results": "todo (manuscript)",
        "19_limitations": "todo (Phase 4 feasibility 4항목 반영)",
        "20_interpretation": "todo (사용자 — 임상 가치 판단)",
        "21_generalisability": "todo (사용자)",
        "22_funding": "todo (사용자)",
    }


# ---------- 서브커맨드 ----------

def cmd_route(args):
    prereg_present = bool(args.prereg and os.path.exists(args.prereg))
    prereg = {}
    if prereg_present:
        with open(args.prereg) as f:
            prereg = json.load(f)

    notes, data_hash = verify_integrity(prereg, prereg_present, args.data)
    ap = prereg.get("analysis_plan", {})
    mc = ap.get("multiple_comparisons", {}) if isinstance(ap, dict) else {}

    governance = {
        "tool": "run_analysis.py (governance)",
        "version": "2.0",
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
        "project": prereg.get("project"),
        "prereg_present": prereg_present,
        "prereg_hash": prereg.get("hash"),
        "data_hash": data_hash,
        "integrity_notes": notes,
        "reproducibility": {
            "random_seed": ap.get("random_seed", 42),
            "software_note": "각 성숙 스킬이 자체 환경(requirements/renv)을 기록함.",
        },
        "engine_recommendation": route_engine(ap.get("primary_method")),
        "confirmatory_tests": confirmatory_set(prereg) if prereg_present else [],
        "multiple_comparisons": {
            "confirmatory": (mc.get("primary") or "Bonferroni"),
            "exploratory": (mc.get("exploratory") or "Benjamini-Hochberg FDR"),
            "note": "사전등록에 없는 모든 분석은 exploratory로 자동 분류.",
        },
        "policy": {
            "effect_size_ci": "모든 추정치는 effect size + 95% CI 동반 (p-value 단독 금지).",
            "irb": "분석 하네스는 IRB 무관 독립 실행 — IRB 책임은 사용자.",
        },
        "delegation": {
            "table1": "anthropic-skills:clinical-table1",
            "survival": "anthropic-skills:survival-analysis",
            "logistic": "anthropic-skills:clinical-logistic-regression",
            "eda": "anthropic-skills:clinical-eda-report (Phase 4)",
        },
    }

    out_dir = args.out
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "governance.json"), "w") as f:
        json.dump(governance, f, ensure_ascii=False, indent=2)

    strobe = strobe_scaffold(prereg)
    with open(os.path.join(out_dir, "strobe_checklist.md"), "w") as f:
        f.write("# STROBE 22-item checklist (scaffold)\n\n")
        f.write("> auto = 사전등록/성숙 스킬에서 자동 / todo = 사용자 입력 필요\n\n")
        for k, v in strobe.items():
            f.write(f"- **{k}**: {v}\n")

    for n in notes:
        print(f"[INTEGRITY] {n}", file=sys.stderr)
    print(f"[OK] governance.json + strobe_checklist.md → {out_dir}")
    print(f"     engine 추천: {governance['engine_recommendation']}")
    print(f"     confirmatory 검정 {len(governance['confirmatory_tests'])}건 "
          f"(보정: {governance['multiple_comparisons']['confirmatory']})")


def cmd_correct(args):
    pvals = {}
    for token in args.pvalues.split(","):
        if "=" not in token:
            continue
        k, v = token.split("=", 1)
        pvals[k.strip()] = float(v)
    result = correct_pvalues(pvals, args.method, args.alpha)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.out:
        with open(args.out, "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser(description="사전등록 분석 거버넌스 헬퍼 (모델링은 성숙 스킬 위임)")
    sp = ap.add_subparsers(dest="cmd", required=True)

    pr = sp.add_parser("route", help="governance.json + STROBE 스캐폴드 생성")
    pr.add_argument("--prereg", default=None)
    pr.add_argument("--data", default=None)
    pr.add_argument("--out", required=True)
    pr.set_defaults(func=cmd_route)

    pc = sp.add_parser("correct", help="다중비교 보정 (bonferroni | bh)")
    pc.add_argument("--pvalues", required=True, help="key=pval,key=pval,...")
    pc.add_argument("--method", required=True)
    pc.add_argument("--alpha", type=float, default=0.05)
    pc.add_argument("--out", default=None)
    pc.set_defaults(func=cmd_correct)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
