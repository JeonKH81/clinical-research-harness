#!/usr/bin/env python3
"""
self_review.py — 생성된 연구계획서의 완성도/보고지침 자동 점검.

study_type에 따라 분기:
  - observational → STROBE 코호트/단면 핵심 항목
  - trial         → SPIRIT 프로토콜 핵심 항목
각 항목을 protocol_content.resolved.json의 해당 필드 충실도로 PRESENT/PARTIAL/MISSING 판정.
완성도 게이트(필수 항목 누락 시 NEEDS_WORK)와 함께 self_review.md를 출력.

사용:
  python self_review.py --resolved phase3_protocol/protocol_content.resolved.json \
    --out phase3_protocol/self_review.md
"""
import argparse, json, os, sys

def load(p): return json.load(open(p,encoding="utf-8"))

def nonempty(v):
    if v is None: return False
    if isinstance(v,str): return len(v.strip())>0
    if isinstance(v,(list,dict)): return len(v)>0
    return True

def status(v, min_len=0):
    if not nonempty(v): return "MISSING"
    if isinstance(v,str) and min_len and len(v.strip())<min_len: return "PARTIAL"
    if isinstance(v,list) and min_len and len(v)<min_len: return "PARTIAL"
    return "PRESENT"

# 공통 핵심 항목 (필수=required)
COMMON=[
    ("제목(국문/영문)", lambda c: status(c.get("title_ko")) , True),
    ("연구 배경·근거 서술", lambda c: status(c.get("background"),120), True),
    ("연구 목적/가설 명시", lambda c: status(c.get("objectives",{}).get("primary")), True),
    ("대상자 선정 기준", lambda c: status(c.get("subjects",{}).get("inclusion")), True),
    ("대상자 제외 기준", lambda c: status(c.get("subjects",{}).get("exclusion")), False),
    ("노출/중재 정의", lambda c: status(c.get("exposure")), True),
    ("비교군 정의", lambda c: status(c.get("comparator")), False),
    ("1차 결과변수 정의", lambda c: status(c.get("outcome_primary")), True),
    ("통계 분석 방법", lambda c: status(c.get("statistics",{}).get("primary")), True),
    ("표본 수 산출 근거", lambda c: status(c.get("sample_size"),20), True),
    ("결측치 처리", lambda c: status(c.get("statistics",{}).get("missing")), False),
    ("자료원/수집 방법", lambda c: status(c.get("data_collection") or c.get("data_provenance")), True),
    ("참고문헌(PMID 동반)", lambda c: status(c.get("references")), True),
    ("윤리/개인정보 보호", lambda c: status(c.get("ethics") or "default"), True),
]
STROBE_EXTRA=[
    ("교란변수(공변량) 명시", lambda c: status(c.get("statistics",{}).get("covariates")), True),
    ("민감도/하위군 분석", lambda c: status(c.get("statistics",{}).get("sensitivity")), False),
    ("연구 설계 유형 명시(STROBE 1)", lambda c: status(c.get("design")), True),
]
SPIRIT_EXTRA=[
    ("배정/무작위화 방법(SPIRIT)", lambda c: status(c.get("design_narrative"),40), True),
    ("결과 평가 시점/방법", lambda c: status(c.get("outcome_primary")), True),
    ("다중 검정 보정 계획", lambda c: status(c.get("statistics",{}).get("multiplicity")), False),
]

def run(content):
    items=list(COMMON)
    items += SPIRIT_EXTRA if content.get("study_type")=="trial" else STROBE_EXTRA
    rows=[]; missing_required=0
    for name,fn,req in items:
        s=fn(content)
        if req and s=="MISSING": missing_required+=1
        rows.append((name,s,req))
    gate="READY" if missing_required==0 else "NEEDS_WORK"
    return rows,gate,missing_required

def to_md(content,rows,gate,missing_required):
    guide="SPIRIT (임상시험 프로토콜)" if content.get("study_type")=="trial" else "STROBE (관찰연구)"
    icon={"PRESENT":"✅","PARTIAL":"🟡","MISSING":"❌"}
    L=[f"# 연구계획서 자기검증 (self-review)","",
       f"- 보고지침: **{guide}**",
       f"- 완성도 게이트: **{gate}** (필수 누락 {missing_required}건)","",
       "| 항목 | 상태 | 필수 |","|---|---|---|"]
    for name,s,req in rows:
        L.append(f"| {name} | {icon.get(s,s)} {s} | {'필수' if req else '권장'} |")
    L+=["",
        "## 판정",
        ("- READY: 필수 항목 충족. IRB 제출 가능 수준." if gate=="READY"
         else "- NEEDS_WORK: 필수 항목 누락. ❌ 항목을 narrative.json/prereg에 보완 후 재생성하십시오."),
        "","## 비고",
        "- 🟡 PARTIAL: 내용이 너무 짧거나 항목 수가 부족 — 보강 권장.",
        "- 본 점검은 형식/완성도 자동 점검이며, 과학적 타당성·IRB 적격성을 보증하지 않음."]
    return "\n".join(L)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--resolved",required=True)
    ap.add_argument("--out")
    a=ap.parse_args()
    if not os.path.exists(a.resolved): sys.exit(f"resolved 없음: {a.resolved}")
    content=load(a.resolved)
    rows,gate,mr=run(content)
    md=to_md(content,rows,gate,mr)
    if a.out:
        open(a.out,"w",encoding="utf-8").write(md)
    print(md)
    print(json.dumps({"gate":gate,"missing_required":mr},ensure_ascii=False))
    sys.exit(0 if gate=="READY" else 2)

if __name__=="__main__":
    main()
