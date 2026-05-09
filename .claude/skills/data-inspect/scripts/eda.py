#!/usr/bin/env python3
"""
eda.py — 사전등록 가설의 데이터 검정가능성 평가

PHI 보호 정책: 행 단위 데이터는 LLM 컨텍스트로 전송되지 않는다.
요약 통계, 결측 패턴, 변수 매핑만 출력.

사용법:
    python eda.py --data data.csv --prereg prereg.json --out phase3_data/
"""

import argparse
import json
import os
import sys
from pathlib import Path

# v1.0 정책 (Soft 마스킹 모델):
# - PHI_AUTOMASK: 자동 마스킹 (실명·생년월일·한국 주민번호) — 거의 항상 직접 식별자
# - PHI_WARN: 사용자에게 인지 확인만 (informed-consent), 분석 진행은 사용자 결정
PHI_AUTOMASK = {"name", "first_name", "last_name", "fullname", "patient_name",
                "dob", "birth_date", "birthdate", "date_of_birth",
                "ssn", "national_id", "rrn", "jumin"}  # rrn/jumin = 주민등록번호
PHI_WARN = {"mrn", "chart_no", "chart_number", "patient_id", "medical_record",
            "address", "addr", "zip", "postal_code",
            "phone", "tel", "mobile", "cell",
            "email", "e_mail",
            "ip_address"}
PHI_SUSPECT = PHI_AUTOMASK  # 하위 호환


def mask_phi_columns(df):
    """PHI 의심 컬럼 분리 식별 (Soft 모델).
    
    Returns: (masked, warn_only)
      masked: 자동 마스킹 (LLM 컨텍스트 비전송 + 분석 자동 제외)
      warn_only: 사용자 인지 확인만 (분석 포함 여부는 사용자 결정)
    """
    masked = []
    warn_only = []
    for col in df.columns:
        cl = col.lower()
        if cl in PHI_AUTOMASK:
            masked.append(col)
        elif cl in PHI_WARN:
            warn_only.append(col)
    if masked:
        print(f"[PHI AUTOMASK] 자동 마스킹 (실명·생년월일·주민번호): {masked}",
              file=sys.stderr)
    if warn_only:
        print(f"[PHI WARN] 사용자 인지 확인 필요 (informed-consent로 분석 포함 가능): {warn_only}",
              file=sys.stderr)
        print("            행 단위 데이터는 어떤 경우에도 LLM 컨텍스트로 전달되지 않음 (비타협).",
              file=sys.stderr)
    return masked, warn_only


def summarize_continuous(s):
    import pandas as pd
    s_clean = s.dropna()
    if len(s_clean) == 0:
        return {"n_valid": 0, "missing": int(s.isna().sum())}
    return {
        "n_valid": int(len(s_clean)),
        "missing": int(s.isna().sum()),
        "mean": float(s_clean.mean()),
        "std": float(s_clean.std()),
        "median": float(s_clean.median()),
        "q1": float(s_clean.quantile(0.25)),
        "q3": float(s_clean.quantile(0.75)),
        "min": float(s_clean.min()),
        "max": float(s_clean.max())
    }


def summarize_categorical(s):
    counts = s.value_counts(dropna=False).to_dict()
    return {
        "n_valid": int(s.notna().sum()),
        "missing": int(s.isna().sum()),
        "categories": {str(k): int(v) for k, v in counts.items()}
    }


def map_variables(prereg, columns):
    """prereg의 P/E/C/O 변수를 데이터 컬럼에 매핑."""
    h = prereg["hypothesis"]
    needed = {
        "exposure": h.get("exposure", "").lower(),
        "comparator": h.get("comparator", "").lower(),
        "outcome_primary": h.get("outcome_primary", {}).get("name", "").lower(),
    }
    cols_lower = {c.lower(): c for c in columns}
    mapping = {}
    for role, key in needed.items():
        # 단순 부분 일치 — 실제 운용에서는 사용자 확인 필요
        match = None
        for cl, c in cols_lower.items():
            if any(token in cl for token in key.split() if len(token) > 2):
                match = c
                break
        mapping[role] = match
    # 공변량
    cov = prereg.get("analysis_plan", {}).get("covariates", [])
    mapping["covariates"] = {v: cols_lower.get(v.lower()) for v in cov}
    return mapping


def power_check(n, events, n_covariates):
    """Peduzzi rule (EPV ≥ 10) 점검."""
    epv = events / max(n_covariates, 1)
    verdict = "ok" if epv >= 10 else ("warn" if epv >= 5 else "fail")
    return {
        "n": n,
        "events": events,
        "n_covariates": n_covariates,
        "epv": round(epv, 2),
        "verdict": verdict,
        "rule": "Peduzzi 1996 (EPV ≥ 10)"
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--prereg", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    try:
        import pandas as pd
        import numpy as np
    except ImportError:
        print("[ERROR] pandas/numpy required: pip install pandas numpy", file=sys.stderr)
        sys.exit(2)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load
    if args.data.endswith(".csv"):
        df = pd.read_csv(args.data)
    elif args.data.endswith(".parquet"):
        df = pd.read_parquet(args.data)
    elif args.data.endswith((".xlsx", ".xls")):
        df = pd.read_excel(args.data)
    else:
        print(f"[ERROR] Unsupported file format: {args.data}", file=sys.stderr)
        sys.exit(2)

    with open(args.prereg) as f:
        prereg = json.load(f)

    masked, warn_only = mask_phi_columns(df)
    df_safe = df.drop(columns=masked) if masked else df.copy()

    # Variable mapping
    mapping = map_variables(prereg, df_safe.columns.tolist())
    with open(out_dir / "variable_mapping.json", "w") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    # Per-variable summary
    summary = {}
    for col in df_safe.columns:
        s = df_safe[col]
        if pd.api.types.is_numeric_dtype(s):
            summary[col] = {"type": "continuous", **summarize_continuous(s)}
        else:
            summary[col] = {"type": "categorical", **summarize_categorical(s)}

    # Sample size + EPV
    outcome_col = mapping.get("outcome_primary")
    n = int(len(df_safe))
    events = None
    if outcome_col and outcome_col in df_safe.columns:
        try:
            events = int(df_safe[outcome_col].sum())
        except Exception:
            events = None
    n_cov = len(prereg.get("analysis_plan", {}).get("covariates", []))
    power = power_check(n, events or 0, n_cov) if events is not None else None

    # Verdict
    missing_critical = []
    for role in ("exposure", "outcome_primary"):
        if not mapping.get(role):
            missing_critical.append(role)
    if missing_critical:
        verdict = "not_testable"
        reason = f"Critical variables missing: {missing_critical}"
    elif power and power["verdict"] == "fail":
        verdict = "not_testable"
        reason = f"EPV {power['epv']} < 5 (Peduzzi rule)"
    elif power and power["verdict"] == "warn":
        verdict = "partially_testable"
        reason = f"EPV {power['epv']} < 10 (Peduzzi rule warning)"
    else:
        verdict = "testable"
        reason = "Critical variables present, EPV adequate"

    report = {
        "data_file": args.data,
        "n_records": n,
        "n_columns": len(df_safe.columns),
        "phi_columns_masked": masked,
        "phi_columns_warn": warn_only,
        "variable_mapping": mapping,
        "summary_statistics": summary,
        "power_check": power,
        "verdict": verdict,
        "verdict_reason": reason,
        "auto_undetectable_warnings": [
            "Selection bias (referral pattern, registry entry criteria)",
            "Information bias (unblinded outcome assessment)",
            "Unmeasured confounding (variables absent from data)",
            "Collider bias (DAG review needed — see data_dag.png)"
        ]
    }

    with open(out_dir / "feasibility_report.json", "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Markdown report
    md = []
    md.append(f"# Feasibility Report — {prereg['project']}\n")
    md.append(f"**Verdict**: `{verdict}`  \n**Reason**: {reason}\n")
    md.append(f"\n## 데이터 개요\n- Records (n): {n}\n- Columns: {len(df_safe.columns)}")
    if masked:
        md.append(f"- PHI 자동 마스킹: {masked}")
    if warn_only:
        md.append(f"- PHI 인지 확인 필요 (분석 포함 여부 사용자 결정): {warn_only}")
    md.append("\n## 변수 매핑\n")
    for role, col in mapping.items():
        if role == "covariates":
            continue
        md.append(f"- {role}: `{col}`")
    md.append("\n### 공변량\n")
    for v, c in (mapping.get("covariates") or {}).items():
        status = "✅" if c else "⚠️ MISSING"
        md.append(f"- {v}: `{c}` {status}")
    if power:
        md.append(f"\n## 검정력\n- N: {power['n']}, Events: {power['events']}, Covariates: {power['n_covariates']}\n- EPV: {power['epv']} ({power['verdict']})\n")
    md.append("\n## 자동 탐지 불가 — 사용자 검토 필수\n")
    for w in report["auto_undetectable_warnings"]:
        md.append(f"- [ ] {w}")
    md.append("\n*위 4항목 각각에 '있음/없음/모름' 응답이 필요합니다.*\n")

    with open(out_dir / "feasibility_report.md", "w") as f:
        f.write("\n".join(md))

    print(f"[OK] Verdict: {verdict}")
    print(f"     {reason}")
    print(f"     Report: {out_dir / 'feasibility_report.md'}")


if __name__ == "__main__":
    main()
