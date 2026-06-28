#!/usr/bin/env python3
"""
sample_size.py — prereg.json 기반 표본 수 자동 산출 + IRB 제출용 한국어 근거 문구 생성.

설계(hypothesis.design)와 effect_size_assumption에 따라 분기:
  - survival / cohort / time-to-event  : log-rank/Cox (Schoenfeld 1983 + Freedman event 공식)
  - two-proportion                     : 두 군 비율 비교 (연속성 보정 없음, normal approx)
  - two-mean                           : 두 군 평균 비교

출력: stdout에 JSON 1개 + 사람이 읽는 한국어 근거 문단(--text).
의존성: scipy (없으면 내장 z-값 근사로 폴백).

사용:
  python sample_size.py --from-prereg prereg.json
  python sample_size.py --design survival --hr 0.75 --alpha 0.05 --power 0.8 --p-event 0.12 --dropout 0.1 --ratio 1
  python sample_size.py --design two-proportion --p1 0.12 --p2 0.09 --alpha 0.05 --power 0.8 --dropout 0.1
  python sample_size.py --design two-mean --delta 5 --sd 12 --alpha 0.05 --power 0.8 --dropout 0.1
"""
import argparse, json, math, sys

def z(p):
    """표준정규 분위수. scipy 우선, 없으면 Acklam 근사."""
    try:
        from scipy.stats import norm
        return float(norm.ppf(p))
    except Exception:
        # Peter Acklam inverse-normal approximation
        a=[-3.969683028665376e+01,2.209460984245205e+02,-2.759285104469687e+02,
           1.383577518672690e+02,-3.066479806614716e+01,2.506628277459239e+00]
        b=[-5.447609879822406e+01,1.615858368580409e+02,-1.556989798598866e+02,
           6.680131188771972e+01,-1.328068155288572e+01]
        c=[-7.784894002430293e-03,-3.223964580411365e-01,-2.400758277161838e+00,
           -2.549732539343734e+00,4.374664141464968e+00,2.938163982698783e+00]
        d=[7.784695709041462e-03,3.224671290700398e-01,2.445134137142996e+00,
           3.754408661907416e+00]
        plow,phigh=0.02425,1-0.02425
        if p<plow:
            q=math.sqrt(-2*math.log(p))
            return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
        if p>phigh:
            q=math.sqrt(-2*math.log(1-p))
            return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
        q=p-0.5; r=q*q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q/(((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)

def inflate(n, dropout):
    if dropout and 0<dropout<1:
        return math.ceil(n/(1-dropout))
    return int(math.ceil(n))

def survival(hr, alpha, power, p_event, ratio, dropout):
    """Schoenfeld(이벤트 수) + Freedman(이벤트 확률→총 N)."""
    za=z(1-alpha/2); zb=z(power)
    k=ratio  # 실험군:대조군 = 1:k? 여기선 allocation proportion p=ratio/(1+ratio)
    p_alloc=ratio/(1+ratio)
    loghr=math.log(hr)
    events=((za+zb)**2)/(p_alloc*(1-p_alloc)*loghr**2)
    events=math.ceil(events)
    out={"design":"survival (log-rank / Cox PH)","method":"Schoenfeld 1983 + Freedman",
         "inputs":{"HR":hr,"alpha":alpha,"power":power,"allocation_ratio":f"1:{ratio:g}",
                   "assumed_event_probability":p_event,"dropout":dropout},
         "required_events":events}
    if p_event and p_event>0:
        n_total=events/p_event
        n_total=inflate(n_total, dropout)
        per=math.ceil(n_total*p_alloc), math.ceil(n_total*(1-p_alloc))
        out["required_n_total"]=n_total
        out["per_group_approx"]={"intervention":per[0],"control":per[1]}
    return out

def two_proportion(p1, p2, alpha, power, ratio, dropout):
    za=z(1-alpha/2); zb=z(power)
    pbar=(p1+ratio*p2)/(1+ratio)
    # 군당 n (대조군 기준), Fleiss 미보정 normal approx
    num=(za*math.sqrt((1+1/ratio)*pbar*(1-pbar))+zb*math.sqrt(p1*(1-p1)+p2*(1-p2)/ratio))**2
    den=(p1-p2)**2
    n1=math.ceil(num/den)
    n2=math.ceil(n1*ratio)
    n1i,n2i=inflate(n1,dropout),inflate(n2,dropout)
    return {"design":"two-proportion","method":"normal approximation (pooled)",
            "inputs":{"p1":p1,"p2":p2,"alpha":alpha,"power":power,"allocation_ratio":f"1:{ratio:g}","dropout":dropout},
            "per_group":{"group1":n1i,"group2":n2i},"required_n_total":n1i+n2i}

def two_mean(delta, sd, alpha, power, ratio, dropout):
    za=z(1-alpha/2); zb=z(power)
    n1=math.ceil((1+1/ratio)*((za+zb)**2)*(sd**2)/(delta**2))
    n2=math.ceil(n1*ratio)
    n1i,n2i=inflate(n1,dropout),inflate(n2,dropout)
    return {"design":"two-mean","method":"two-sample t (normal approx)",
            "inputs":{"delta":delta,"sd":sd,"alpha":alpha,"power":power,"allocation_ratio":f"1:{ratio:g}","dropout":dropout},
            "per_group":{"group1":n1i,"group2":n2i},"required_n_total":n1i+n2i}

def korean_text(r):
    i=r["inputs"]
    if r["design"].startswith("survival"):
        t=(f"표본 수 산출: 양측 유의수준 α={i['alpha']}, 검정력 {int(i['power']*100)}%, "
           f"가정 위험비(HR) {i['HR']}, 배정비 {i['allocation_ratio']} 조건에서 "
           f"Schoenfeld 공식에 따라 필요한 사건(event) 수는 {r['required_events']}건이다.")
        if "required_n_total" in r:
            t+=(f" 가정 사건 발생확률 {i['assumed_event_probability']*100:.0f}%와 "
                f"탈락률 {int(i['dropout']*100)}%를 반영하면 총 {r['required_n_total']}명"
                f"(중재군 약 {r['per_group_approx']['intervention']}명, 대조군 약 {r['per_group_approx']['control']}명)이 필요하다.")
        return t
    if r["design"]=="two-proportion":
        return (f"표본 수 산출: 양측 α={i['alpha']}, 검정력 {int(i['power']*100)}%에서 "
                f"두 군 사건율 {i['p1']*100:.0f}% vs {i['p2']*100:.0f}%를 검출하려면 "
                f"탈락률 {int(i['dropout']*100)}% 반영 시 총 {r['required_n_total']}명"
                f"(군당 {r['per_group']['group1']}/{r['per_group']['group2']}명)이 필요하다.")
    if r["design"]=="two-mean":
        return (f"표본 수 산출: 양측 α={i['alpha']}, 검정력 {int(i['power']*100)}%에서 "
                f"평균차 {i['delta']}(표준편차 {i['sd']})를 검출하려면 탈락률 "
                f"{int(i['dropout']*100)}% 반영 시 총 {r['required_n_total']}명이 필요하다.")
    return ""

def from_prereg(path):
    d=json.load(open(path,encoding="utf-8"))
    h=d.get("hypothesis",{}); esa=h.get("effect_size_assumption",{}) or {}
    design=(h.get("design") or "").lower()
    alpha=esa.get("alpha",0.05); power=esa.get("power",0.80)
    if "HR" in esa or "hr" in esa or "survival" in design or "cohort" in design or "cox" in (d.get("analysis_plan",{}).get("primary_method","").lower()):
        hr=esa.get("HR", esa.get("hr"))
        if hr is None:
            return {"error":"effect_size_assumption.HR 없음 — --hr 로 지정하거나 prereg 보완 필요","design_hint":design}
        return survival(hr, alpha, power, esa.get("p_event"), esa.get("allocation_ratio",1), esa.get("dropout",0.1))
    if "p1" in esa and "p2" in esa:
        return two_proportion(esa["p1"],esa["p2"],alpha,power,esa.get("allocation_ratio",1),esa.get("dropout",0.1))
    if "delta" in esa and "sd" in esa:
        return two_mean(esa["delta"],esa["sd"],alpha,power,esa.get("allocation_ratio",1),esa.get("dropout",0.1))
    return {"error":"effect_size_assumption에서 설계를 추론할 수 없음 (HR / p1,p2 / delta,sd 중 하나 필요)","effect_size_assumption":esa}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--from-prereg")
    ap.add_argument("--design",choices=["survival","two-proportion","two-mean"])
    ap.add_argument("--hr",type=float); ap.add_argument("--p-event",type=float,dest="p_event")
    ap.add_argument("--p1",type=float); ap.add_argument("--p2",type=float)
    ap.add_argument("--delta",type=float); ap.add_argument("--sd",type=float)
    ap.add_argument("--alpha",type=float,default=0.05); ap.add_argument("--power",type=float,default=0.80)
    ap.add_argument("--ratio",type=float,default=1.0); ap.add_argument("--dropout",type=float,default=0.10)
    ap.add_argument("--text",action="store_true",help="한국어 근거 문단만 출력")
    a=ap.parse_args()
    if a.from_prereg:
        r=from_prereg(a.from_prereg)
    elif a.design=="survival":
        r=survival(a.hr,a.alpha,a.power,a.p_event,a.ratio,a.dropout)
    elif a.design=="two-proportion":
        r=two_proportion(a.p1,a.p2,a.alpha,a.power,a.ratio,a.dropout)
    elif a.design=="two-mean":
        r=two_mean(a.delta,a.sd,a.alpha,a.power,a.ratio,a.dropout)
    else:
        ap.error("--from-prereg 또는 --design 필요")
    if "error" not in r:
        r["justification_ko"]=korean_text(r)
    if a.text:
        print(r.get("justification_ko") or r.get("error",""))
    else:
        print(json.dumps(r,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
