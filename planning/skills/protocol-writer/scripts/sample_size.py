#!/usr/bin/env python3
"""
sample_size.py — prereg.json 기반 표본 수 자동 산출 + IRB 제출용 한국어 근거 문구 생성.

지원 설계(scipy만 사용, statsmodels 비의존 → 이식성 유지):
  - survival             : log-rank/Cox (Schoenfeld + Freedman event 공식)
  - two-proportion       : 두 군 비율 비교 (pooled normal approx)
  - two-mean             : 두 군 평균 비교
  - precision-proportion : 단일 비율 CI 정밀도 / 진단정확도(민감도·특이도) (Buderer 1996)
  - mcnemar              : 짝지은 이진 (Connor 1987)
  - anova                : 일원분산분석 (Cohen f, 비중심 F 탐색)
  - logistic             : 로지스틱 회귀 (Peduzzi EPV 규칙 / Hsieh 1989)
  - ni-proportion        : 비열등성 비율 (위험차, 단측)
  - ni-mean              : 비열등성 평균 (단측)

흔한 설계(survival/two-proportion/two-mean)는 build_protocol.py가 --from-prereg로 자동 호출.
그 밖의 복잡 설계(진단정확도·일치도·비열등성·로지스틱)는 본 스크립트로 직접 산출하거나,
선택적으로 medsci-skills의 calc-sample-size 스킬을 사용(설치 시).

출력: stdout에 JSON 1개 + 사람이 읽는 한국어 근거 문단(--text).
의존성: scipy (z·F 분포). 없으면 z는 내장 근사로 폴백, ANOVA는 scipy 필수.

사용:
  python sample_size.py --from-prereg prereg.json
  python sample_size.py --design survival --hr 0.75 --power 0.8 --p-event 0.12 --dropout 0.1
  python sample_size.py --design two-proportion --p1 0.12 --p2 0.09
  python sample_size.py --design two-mean --delta 5 --sd 12
  python sample_size.py --design precision-proportion --p 0.85 --w 0.05 --prevalence 0.3
  python sample_size.py --design mcnemar --p01 0.10 --p10 0.20
  python sample_size.py --design anova --k 3 --f 0.25
  python sample_size.py --design logistic --n-predictors 8 --event-rate 0.15      # Peduzzi
  python sample_size.py --design logistic --or 1.5 --exposure 0.3 --r2 0.2        # Hsieh
  python sample_size.py --design ni-proportion --p1 0.90 --margin 0.10            # 단측 α=0.025 기본
  python sample_size.py --design ni-mean --sd 10 --margin 5
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

def precision_proportion(p, w, alpha, prevalence, dropout):
    """단일 비율 CI 정밀도(Buderer 1996) — 진단정확도(민감도/특이도) 포함."""
    za=z(1-alpha/2)
    n_measure=math.ceil((za/w)**2*p*(1-p))
    out={"design":"precision (single proportion / diagnostic accuracy)","method":"Buderer 1996",
         "inputs":{"expected_proportion":p,"ci_half_width":w,"alpha":alpha,
                   "prevalence":prevalence,"dropout":dropout},
         "n_measured":n_measure}
    n_total=n_measure/prevalence if prevalence else n_measure
    out["required_n_total"]=inflate(n_total,dropout)
    return out

def mcnemar(p01, p10, alpha, power, dropout):
    """짝지은 이진(McNemar, Connor 1987)."""
    za=z(1-alpha/2); zb=z(power); s=p01+p10; d=p10-p01
    n=math.ceil((za*math.sqrt(s)+zb*math.sqrt(s-d**2))**2/d**2)
    return {"design":"mcnemar (paired proportions)","method":"Connor 1987",
            "inputs":{"p01":p01,"p10":p10,"alpha":alpha,"power":power,"dropout":dropout},
            "required_n_total":inflate(n,dropout)}

def anova(k, f, alpha, power, dropout):
    """일원분산분석(Cohen f) — 비중심 F로 자체 검정력 탐색(scipy만 사용)."""
    try:
        from scipy.stats import f as fdist, ncf
    except Exception:
        return {"error":"ANOVA 검정력 계산에 scipy 필요"}
    df1=k-1
    n=2
    while n<100000:
        N=n*k; df2=N-k
        if df2<=0: n+=1; continue
        crit=fdist.ppf(1-alpha,df1,df2)
        lam=f*f*N
        pw=1-ncf.cdf(crit,df1,df2,lam)
        if pw>=power: break
        n+=1
    return {"design":"one-way ANOVA","method":"Cohen f (noncentral F)",
            "inputs":{"k":k,"f":f,"alpha":alpha,"power":power,"dropout":dropout},
            "n_per_group":inflate(n,dropout),"required_n_total":inflate(n,dropout)*k}

def logistic(or_=None, exposure=None, r2=0.0, n_predictors=None, event_rate=None,
             epv=10, alpha=0.05, power=0.80, dropout=0.0):
    """로지스틱 회귀: OR 지정 시 Hsieh 1989(이진 예측변수), 아니면 Peduzzi EPV 규칙."""
    if or_ is not None and exposure is not None:
        za=z(1-alpha/2); zb=z(power)
        n_unadj=((za+zb)**2)/(exposure*(1-exposure)*math.log(or_)**2)
        n_adj=n_unadj/(1-(r2 or 0))
        return {"design":"logistic regression (Hsieh 1989, binary predictor)","method":"Hsieh 1989",
                "inputs":{"OR":or_,"exposed_fraction":exposure,"R2_with_covariates":r2,
                          "alpha":alpha,"power":power,"dropout":dropout},
                "required_n_total":inflate(n_adj,dropout)}
    if n_predictors and event_rate:
        n_events=epv*n_predictors
        n_total=n_events/event_rate
        return {"design":"logistic regression (Peduzzi EPV rule)","method":f"EPV>={epv}",
                "inputs":{"n_predictors":n_predictors,"event_rate":event_rate,"epv":epv,"dropout":dropout},
                "required_events":math.ceil(n_events),"required_n_total":inflate(n_total,dropout)}
    return {"error":"logistic: (--or & --exposure) 또는 (--n-predictors & --event-rate) 필요"}

def ni_proportion(p0, margin, alpha, power, delta, ratio, dropout):
    """비열등성 — 비율(위험차). alpha는 단측. delta=가정 진짜 차이(보통 0)."""
    za=z(1-alpha); zb=z(power)
    p1=p0; p2=p0+delta
    eff=margin-abs(delta)
    n1=math.ceil((1+1/ratio)*((za+zb)**2)*(p1*(1-p1)+p2*(1-p2))/2/eff**2)
    n2=math.ceil(n1*ratio)
    return {"design":"non-inferiority (proportion, risk difference)","method":"one-sided normal",
            "inputs":{"control_rate":p0,"NI_margin":margin,"assumed_true_diff":delta,
                      "alpha_one_sided":alpha,"power":power,"allocation_ratio":f"1:{ratio:g}","dropout":dropout},
            "per_group":{"group1":inflate(n1,dropout),"group2":inflate(n2,dropout)},
            "required_n_total":inflate(n1,dropout)+inflate(n2,dropout)}

def ni_mean(sd, margin, alpha, power, delta, ratio, dropout):
    """비열등성 — 평균. alpha 단측. delta=가정 진짜 차이(보통 0)."""
    za=z(1-alpha); zb=z(power); eff=margin-abs(delta)
    n1=math.ceil((1+1/ratio)*((za+zb)**2)*(sd**2)/eff**2)
    n2=math.ceil(n1*ratio)
    return {"design":"non-inferiority (mean)","method":"one-sided normal",
            "inputs":{"sd":sd,"NI_margin":margin,"assumed_true_diff":delta,
                      "alpha_one_sided":alpha,"power":power,"allocation_ratio":f"1:{ratio:g}","dropout":dropout},
            "per_group":{"group1":inflate(n1,dropout),"group2":inflate(n2,dropout)},
            "required_n_total":inflate(n1,dropout)+inflate(n2,dropout)}

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
    if r["design"].startswith("precision"):
        t=(f"표본 수 산출: 기대 비율 {i['expected_proportion']*100:.0f}%를 95% 신뢰구간 "
           f"반폭 ±{i['ci_half_width']} 이내로 추정하려면 측정 대상 {r['n_measured']}건이 필요하다(Buderer 1996).")
        if i.get("prevalence"):
            t+=f" 유병률 {i['prevalence']*100:.0f}% 및 탈락률 {int(i['dropout']*100)}% 반영 시 총 {r['required_n_total']}명."
        return t
    if r["design"].startswith("mcnemar"):
        return (f"표본 수 산출: 짝지은 이진 자료에서 불일치 비율 p01={i['p01']}, p10={i['p10']} 가정, "
                f"양측 α={i['alpha']}·검정력 {int(i['power']*100)}%, 탈락률 {int(i['dropout']*100)}% 반영 시 "
                f"총 {r['required_n_total']}쌍이 필요하다(McNemar, Connor 1987).")
    if r["design"].startswith("one-way ANOVA"):
        return (f"표본 수 산출: {i['k']}개 군, 효과크기 Cohen f={i['f']}, 양측 α={i['alpha']}·검정력 "
                f"{int(i['power']*100)}%에서 군당 {r['n_per_group']}명(총 {r['required_n_total']}명)이 필요하다.")
    if r["design"].startswith("logistic regression (Peduzzi"):
        return (f"표본 수 산출: 예측변수 {i['n_predictors']}개에 대해 EPV≥{i['epv']}(Peduzzi 규칙)를 충족하려면 "
                f"최소 {r['required_events']} 사건, 사건률 {i['event_rate']*100:.0f}%·탈락률 {int(i['dropout']*100)}% "
                f"반영 시 총 {r['required_n_total']}명이 필요하다.")
    if r["design"].startswith("logistic regression (Hsieh"):
        return (f"표본 수 산출: 이진 예측변수(노출 비율 {i['exposed_fraction']*100:.0f}%)의 OR={i['OR']} 검출, "
                f"공변량 보정 R²={i['R2_with_covariates']}, 양측 α={i['alpha']}·검정력 {int(i['power']*100)}% 기준 "
                f"총 {r['required_n_total']}명이 필요하다(Hsieh 1989).")
    if r["design"].startswith("non-inferiority"):
        unit="명"
        base=(f"표본 수 산출: 비열등성 마진 {i['NI_margin']}, 단측 α={i['alpha_one_sided']}·검정력 "
              f"{int(i['power']*100)}%, 배정비 {i['allocation_ratio']}, 탈락률 {int(i['dropout']*100)}% 반영 시 "
              f"총 {r['required_n_total']}{unit}(군당 {r['per_group']['group1']}/{r['per_group']['group2']})이 필요하다.")
        return base
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
    ap.add_argument("--design",choices=["survival","two-proportion","two-mean",
                    "precision-proportion","mcnemar","anova","logistic",
                    "ni-proportion","ni-mean"])
    ap.add_argument("--hr",type=float); ap.add_argument("--p-event",type=float,dest="p_event")
    ap.add_argument("--p1",type=float); ap.add_argument("--p2",type=float)
    ap.add_argument("--delta",type=float); ap.add_argument("--sd",type=float)
    ap.add_argument("--p",type=float,help="단일 비율(정밀도/진단정확도)"); ap.add_argument("--w",type=float,help="CI 반폭")
    ap.add_argument("--prevalence",type=float); ap.add_argument("--p01",type=float); ap.add_argument("--p10",type=float)
    ap.add_argument("--k",type=int,help="ANOVA 군 수"); ap.add_argument("--f",type=float,help="Cohen f")
    ap.add_argument("--or",type=float,dest="or_"); ap.add_argument("--exposure",type=float)
    ap.add_argument("--r2",type=float,default=0.0); ap.add_argument("--n-predictors",type=int,dest="n_predictors")
    ap.add_argument("--event-rate",type=float,dest="event_rate"); ap.add_argument("--epv",type=float,default=10)
    ap.add_argument("--margin",type=float,help="비열등성 마진")
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
    elif a.design=="precision-proportion":
        r=precision_proportion(a.p,a.w,a.alpha,a.prevalence,a.dropout)
    elif a.design=="mcnemar":
        r=mcnemar(a.p01,a.p10,a.alpha,a.power,a.dropout)
    elif a.design=="anova":
        r=anova(a.k,a.f,a.alpha,a.power,a.dropout)
    elif a.design=="logistic":
        r=logistic(a.or_,a.exposure,a.r2,a.n_predictors,a.event_rate,a.epv,a.alpha,a.power,a.dropout)
    elif a.design=="ni-proportion":
        r=ni_proportion(a.p1 if a.p1 is not None else a.p, a.margin, a.alpha if a.alpha!=0.05 else 0.025,
                        a.power, a.delta or 0.0, a.ratio, a.dropout)
    elif a.design=="ni-mean":
        r=ni_mean(a.sd, a.margin, a.alpha if a.alpha!=0.05 else 0.025, a.power, a.delta or 0.0, a.ratio, a.dropout)
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
