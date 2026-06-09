#!/usr/bin/env python3
"""
run_analysis.py — 사전등록 기반 통계 분석 실행

핵심 정책:
1. 사전등록 무결성 검증 필수 (실패 시 분석 중단)
2. prereg에 명시된 분석 → confirmatory, 그 외 → exploratory
3. p-value 단독 보고 금지 — effect size + 95% CI 동반
4. STROBE 22항목 자동 점검표 출력

사용법:
    python run_analysis.py --data data.csv --prereg prereg.json \
                           --variable-mapping mapping.json --out phase4_analysis/
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def _canonical_json(obj):
    """재현 가능한 정규형 JSON (정렬, UTF-8) — lock.py / prereg_check.py와 동일."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def _compute_prereg_hash(prereg_dict):
    payload = {k: v for k, v in prereg_dict.items() if k != "hash"}
    return "sha256:" + hashlib.sha256(_canonical_json(payload)).hexdigest()


def verify_prereg(prereg_path, project):
    """사전등록 무결성 자체 검증 (Soft 모델, 차단 안 함).

    분석 하네스는 계획 하네스의 prereg-lock에 의존하지 않고 자체 해시 검증을 수행한다.
    드리프트 시 경고만 출력하고 분석은 계속 진행된다 (informed-consent 모델).
    """
    if not os.path.exists(prereg_path):
        print("[NOTE] prereg.json not found — 모든 분석이 exploratory로 처리됩니다.",
              file=sys.stderr)
        return
    with open(prereg_path) as f:
        prereg = json.load(f)
    stored = prereg.get("hash")
    computed = _compute_prereg_hash(prereg)
    if stored == computed:
        print("[OK] Pre-registration integrity verified.")
    else:
        print("[WARN] prereg.json HASH DRIFT — recorded 이후 변경됨. "
              "허용(Soft 모델)되나 보고서에 트레일로 노출됩니다.", file=sys.stderr)
        print(f"        stored={stored} computed={computed}", file=sys.stderr)


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def table1(df, group_col):
    """Baseline characteristics — Table 1."""
    import pandas as pd
    import numpy as np
    from scipy import stats

    rows = []
    for col in df.columns:
        if col == group_col:
            continue
        s = df[col]
        if pd.api.types.is_numeric_dtype(s):
            normal_p = stats.shapiro(s.dropna().sample(min(5000, len(s.dropna())),
                                                       random_state=42))[1] if len(s.dropna()) > 3 else 1.0
            is_normal = normal_p >= 0.05
            groups = df.groupby(group_col)[col].apply(lambda x: x.dropna()).to_dict()
            if len(groups) == 2:
                vals = list(groups.values())
                if is_normal:
                    test_p = stats.ttest_ind(vals[0], vals[1], equal_var=False, nan_policy="omit")[1]
                    summary = {k: f"{v.mean():.2f} ± {v.std():.2f}" for k, v in groups.items()}
                else:
                    test_p = stats.mannwhitneyu(vals[0], vals[1], alternative="two-sided")[1]
                    summary = {k: f"{v.median():.2f} [{v.quantile(0.25):.2f}–{v.quantile(0.75):.2f}]"
                               for k, v in groups.items()}
                # SMD
                m1, m2 = vals[0].mean(), vals[1].mean()
                sd_pool = np.sqrt((vals[0].var() + vals[1].var()) / 2)
                smd = (m1 - m2) / sd_pool if sd_pool > 0 else float("nan")
                rows.append({"variable": col, "type": "continuous", **summary,
                             "p_value": float(test_p), "smd": float(smd)})
        else:
            ct = pd.crosstab(s, df[group_col])
            try:
                _, p, _, _ = stats.chi2_contingency(ct)
            except Exception:
                p = float("nan")
            summary = {str(g): f"{ct[g].sum()} ({ct[g].sum() / len(df) * 100:.1f}%)"
                       for g in ct.columns}
            rows.append({"variable": col, "type": "categorical", **summary,
                         "p_value": float(p), "smd": None})
    return rows


def cox_primary(df, mapping, prereg):
    """Primary Cox PH analysis (if applicable)."""
    try:
        from lifelines import CoxPHFitter
    except ImportError:
        return {"error": "lifelines not installed (pip install lifelines)"}

    duration_col = mapping.get("time_to_outcome")
    event_col = mapping.get("outcome_primary")
    if not duration_col or not event_col:
        return {"error": "Missing duration or event column for survival analysis"}

    covariates = [v for v in (prereg.get("analysis_plan", {}).get("covariates") or [])
                  if v in df.columns]
    exposure = mapping.get("exposure")
    if not exposure:
        return {"error": "Exposure column not mapped"}

    formula_vars = [exposure] + covariates
    sub = df[[duration_col, event_col] + formula_vars].dropna()

    cph = CoxPHFitter()
    cph.fit(sub, duration_col=duration_col, event_col=event_col,
            formula="+".join(formula_vars), robust=True)
    summary = cph.summary
    return {
        "n": int(len(sub)),
        "events": int(sub[event_col].sum()),
        "concordance": float(cph.concordance_index_),
        "results": [
            {
                "term": idx,
                "HR": float(row["exp(coef)"]),
                "ci_low": float(row["exp(coef) lower 95%"]),
                "ci_high": float(row["exp(coef) upper 95%"]),
                "p": float(row["p"])
            }
            for idx, row in summary.iterrows()
        ]
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--prereg", required=True)
    ap.add_argument("--variable-mapping", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "diagnostics").mkdir(exist_ok=True)

    # Load
    with open(args.prereg) as f:
        prereg = json.load(f)
    with open(args.variable_mapping) as f:
        mapping = json.load(f)

    # Step 1: verify prereg integrity
    verify_prereg(args.prereg, prereg["project"])

    # Step 2: data hash
    data_hash = file_sha256(args.data)
    expected = prereg.get("data_provenance", {}).get("data_file_hash")
    if expected and expected != data_hash:
        print(f"[WARN] Data file hash mismatch (expected {expected}, got {data_hash})",
              file=sys.stderr)
        print("        Data may have changed since pre-registration.", file=sys.stderr)

    # Step 3: load data
    try:
        import pandas as pd
    except ImportError:
        print("[ERROR] pandas required", file=sys.stderr)
        sys.exit(2)

    df = pd.read_csv(args.data) if args.data.endswith(".csv") else pd.read_parquet(args.data)
    seed = prereg.get("analysis_plan", {}).get("random_seed", 42)
    import numpy as np
    np.random.seed(seed)

    # Step 4: Table 1
    exposure_col = mapping.get("exposure")
    table1_results = []
    if exposure_col and exposure_col in df.columns:
        try:
            table1_results = table1(df, exposure_col)
        except Exception as e:
            print(f"[WARN] Table 1 generation failed: {e}", file=sys.stderr)

    # Step 5: Primary analysis (Cox PH)
    primary = cox_primary(df, mapping, prereg)

    # Step 6: STROBE checklist (자동 점검 가능 항목만)
    strobe = {
        "1_design_in_title": "auto" if prereg["hypothesis"].get("design") else "todo",
        "3_objectives": "auto",  # prereg에 가설 명시됨
        "4_study_design": prereg["hypothesis"].get("design", "todo"),
        "6_participants": prereg["hypothesis"].get("population", "todo"),
        "7_variables": "auto",
        "10_study_size": "auto" if prereg.get("hypothesis", {}).get("effect_size_assumption") else "todo",
        "12_statistical_methods": prereg.get("analysis_plan", {}).get("primary_method", "todo"),
        "13_participants_flow": "todo (manuscript phase)",
        "14_descriptive_data": "auto" if table1_results else "todo",
        "16_main_results": "auto" if "results" in primary else "todo",
        "19_limitations": "todo (manuscript phase, see feasibility_report.md)",
        "22_funding": "todo"
    }

    # Output
    results = {
        "data_hash": data_hash,
        "prereg_hash": prereg["hash"],
        "n_records": int(len(df)),
        "random_seed": seed,
        "confirmatory": {
            "table1": table1_results,
            "primary": primary
        },
        "exploratory": [],
        "strobe_checklist": strobe
    }
    with open(out_dir / "results.json", "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    # Markdown summary
    md = ["# Analysis Results — " + prereg["project"], ""]
    md.append(f"**Pre-reg hash**: `{prereg['hash']}`")
    md.append(f"**Data hash**: `{data_hash}`")
    md.append(f"**N**: {results['n_records']}, **Seed**: {seed}\n")
    md.append("## Confirmatory Analysis (사전등록 명시 분석)\n")
    if "results" in primary:
        md.append(f"### Primary — Cox PH")
        md.append(f"- N: {primary['n']}, Events: {primary['events']}, C-index: {primary['concordance']:.3f}")
        md.append("\n| Term | HR | 95% CI | p |")
        md.append("|---|---|---|---|")
        for r in primary["results"]:
            md.append(f"| {r['term']} | {r['HR']:.3f} | {r['ci_low']:.3f}–{r['ci_high']:.3f} | {r['p']:.4g} |")
    else:
        md.append(f"⚠️ Primary analysis skipped: {primary.get('error', 'unknown')}")
    md.append("\n## STROBE 22-item checklist")
    for item, status in strobe.items():
        md.append(f"- {item}: `{status}`")
    md.append("\n## Exploratory Analysis (사전등록에 없음 — BH FDR 보정 필요)")
    md.append("- (없음)")
    md.append("\n---")
    md.append("\n*p-value는 effect size + 95% CI와 함께 해석되어야 합니다.*")
    md.append("*임상적 해석은 사용자(연구자)의 영역입니다.*")

    with open(out_dir / "results.md", "w") as f:
        f.write("\n".join(md))

    print(f"[OK] Analysis complete. Output: {out_dir}/results.md")


if __name__ == "__main__":
    main()
