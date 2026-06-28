---
name: stat-analysis
description: 사전등록에 따라 통계 분석을 거버넌스한다. 실제 모델링(Table 1·Cox/KM·로지스틱·진단)은 성숙한 anthropic-skills에 위임하고, 본 스킬은 confirmatory/exploratory 분류·다중비교 보정·effect size+95%CI 강제·STROBE·재현성만 책임진다. Phase 5 전용. IRB 무관. statistician agent가 호출. "분석", "Cox", "회귀", "생존", "Table 1" 발화에서 호출.
license: MIT
---

# Stat-Analysis Skill (사전등록 분석 거버넌스 — wrapper)

## 목적
잠긴 사전등록 계획에 따라 통계 분석을 **거버넌스**하고 STROBE 형식으로 정리한다. 실제 통계 모델링은 성숙한 시스템 스킬에 위임한다 (protocol-writer·manuscript-writer와 동일한 wrapper 패턴).

## 트리거
- statistician agent가 호출
- 사용자가 "분석", "Cox", "회귀", "생존", "Table 1"을 직접 언급

---

## 위임 대상 (실제 모델링은 이들이 수행)

| 분석 | 위임 스킬 | 본 스킬이 주는 것 |
|---|---|---|
| Table 1 (baseline + SMD) | `anthropic-skills:clinical-table1` | 군 변수 지정, confirmatory 맥락 |
| 생존분석 (Cox/KM, **Schoenfeld PH**, VIF, HR+CI) | `anthropic-skills:survival-analysis` | primary_method 라우팅, 다중비교 |
| 로지스틱 (OR+CI, Firth, calibration, TRIPOD) | `anthropic-skills:clinical-logistic-regression` | confirmatory/exploratory 태깅 |
| 전체 EDA (Phase 4) | `anthropic-skills:clinical-eda-report` | (data-inspect 참조) |

→ 본 스킬은 이들을 **다시 구현하지 않는다.** 사전등록 거버넌스만 책임진다.

---

## 작동 원칙 (5가지)

### 1. Pre-reg as analysis source (사전등록이 분석 출처)
prereg.json의 분석 계획을 그대로 따른다. 새 공변량·하위군·다른 모델은 모두 *exploratory*로 자동 분리.

### 2. Confirmatory/Exploratory auto-separation (자동 분리)
사전등록 명시 분석(primary + pre-specified secondary) → confirmatory. 그 외 → exploratory. `run_analysis.py route`가 confirmatory 검정 목록을 산출한다.

### 3. Effect size + 95% CI (p-value 단독 보고 금지 — 비타협)
모든 효과 추정치는 effect size + 95% CI 동반. p-value 단독 보고는 **자동 거절**. (위임 스킬은 기본적으로 OR/HR + 95% CI를 보고하므로, 본 스킬은 그 결과를 그대로 보존하고 p-value만 단독 노출되지 않도록 점검)

### 4. Reproducibility (재현성)
난수 시드는 prereg.analysis_plan.random_seed (default 42). 환경 고정(requirements.txt/renv.lock)은 각 위임 스킬이 자체 기록한다. governance.json에 prereg/data 해시·시드를 기록.

### 5. Diagnostics via delegation (진단은 위임)
모델 진단은 위임 스킬이 수행한다 — 특히 **Cox PH 가정(Schoenfeld)·VIF는 `survival-analysis`**, calibration/TRIPOD는 `clinical-logistic-regression`. 본 스킬은 위임 스킬의 진단 결과를 G5에서 사용자에게 검토 요청하고, 가정 위반 시 대안(stratified Cox 등)을 안내한다.

---

## 구동 과정

> **IRB 게이트 없음**: 분석 하네스는 IRB 무관 독립 실행. irb_status를 점검·차단하지 않는다. IRB 책임은 사용자.

```
[1] 거버넌스 라우팅 — run_analysis.py route
    - prereg/data 무결성 검증 (Soft, 차단 아님)
    - primary_method → 위임 스킬 추천 (engine_recommendation)
    - confirmatory 검정 목록 + 다중비교 계획 산출
    - governance.json + strobe_checklist.md 생성
        ↓
[2] Table 1 — Skill: anthropic-skills:clinical-table1 (군 = exposure)
        ↓
[3] 1차/부수 분석 — Skill: 추천 엔진(survival-analysis 또는 clinical-logistic-regression)
    primary + pre-specified secondary 를 confirmatory로 실행 (HR/OR + 95% CI)
        ↓
[4] 민감도 분석 — 사전등록 명시된 것 (위임 스킬의 옵션 활용:
    complete-case / MI / IPTW / PSM / subgroup)
        ↓
[5] 진단 — 위임 스킬 산출 (Schoenfeld PH, VIF, calibration 등)
    가정 위반 시 경고 + 대안 안내
        ↓
[6] 다중비교 보정 — run_analysis.py correct
    confirmatory=Bonferroni, exploratory=BH-FDR (위임 스킬이 준 p-value에 적용)
        ↓
[7] Exploratory 분석 (있으면) — 별도 라벨 + BH-FDR + "hypothesis-generating" 주석
        ↓
[8] STROBE 22항목 정리 (strobe_checklist.md) + G5 게이트
```

## 입력
- `workspace/{project}/phase2_hypothesis/prereg.json` (없으면 모두 exploratory)
- `workspace/{project}/input/data.csv` (PHI 정책은 data-inspect와 동일)
- `workspace/{project}/phase4_data/variable_mapping.json`
- `workspace/{project}/phase4_data/feasibility_report.md`

## 출력
| 산출물 | 생성 주체 | 의미 |
|---|---|---|
| `phase5_analysis/governance.json` | 본 스킬 | 무결성·엔진 라우팅·confirmatory 목록·다중비교·해시·시드 |
| `phase5_analysis/strobe_checklist.md` | 본 스킬 | STROBE 22항목 스캐폴드 |
| `phase5_analysis/corrected_pvalues.json` | 본 스킬 | 다중비교 보정 결과 |
| Table 1 (HTML/docx/xlsx) | clinical-table1 | baseline + SMD |
| 생존/로지스틱 결과·진단 플롯 | survival-analysis / clinical-logistic-regression | HR/OR+CI, Schoenfeld, calibration 등 |

> 위임 스킬의 산출물은 각 스킬의 출력 규약을 따르며, 본 스킬은 그 경로를 governance.json에 기록한다.

## 절대 규칙

### 1. 무결성 검증 (필수 첫 단계)
```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/stat-analysis/scripts/run_analysis.py route \
  --prereg workspace/{project}/phase2_hypothesis/prereg.json \
  --data   workspace/{project}/input/data.csv \
  --out    workspace/{project}/phase5_analysis/
```
해시 드리프트/부재는 **차단 없이 경고**(Soft 모델). prereg 부재 시 모든 분석을 exploratory로 처리.
(독립 검증만 원하면 `prereg_check.py --project {project}` 도 사용 가능)

### 2. Confirmatory vs Exploratory 분리
- prereg.analysis_plan 명시 분석 → `confirmatory` (governance.json의 confirmatory_tests)
- 그 외 모든 분석 → `exploratory` (별도 라벨)

### 3. 다중비교 보정
```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/stat-analysis/scripts/run_analysis.py correct \
  --method bonferroni --alpha 0.05 \
  --pvalues "primary=0.01,death=0.04,st=0.20" \
  --out workspace/{project}/phase5_analysis/corrected_pvalues.json
```
- Confirmatory: prereg 명시 방법 (default Bonferroni)
- Exploratory: Benjamini–Hochberg FDR (`--method bh`)

### 4. 보고 규칙
- p-value 단독 보고 금지 — 항상 effect size + 95% CI 동반 (위임 스킬 결과 그대로 보존)
- 임상적 해석은 자동 생성하되 최종 승인은 사용자

## 위임 호출 예시 (statistician agent)

```
# 1) 거버넌스 라우팅
Bash: run_analysis.py route ...   → governance.json (engine 추천: survival-analysis)

# 2) Table 1
Skill: anthropic-skills:clinical-table1   (data.csv, group = exposure 컬럼)

# 3) 1차/부수 (생존인 경우)
Skill: anthropic-skills:survival-analysis (Cox + Schoenfeld + VIF, covariates from prereg)

# 4) 다중비교 보정
Bash: run_analysis.py correct --method bonferroni --pvalues "primary=...,death=..."
```

## 게이트 G5 인계
1. 임상적 해석 적절성 — effect size의 임상적 의미
2. 진단 검토 — survival-analysis의 Schoenfeld(PH 가정)/VIF, 로지스틱 calibration. 위반 시 대안(stratified Cox·time-varying·AFT) 검토
3. 민감도 분석 일관성 — complete-case vs MI vs IPTW/PSM robustness
4. 다음 단계 — 추가 분석 / Phase 6(manuscript) / 종료

## 실패 모드 (p-value 단독 비타협 + 나머지 informed-consent)

| 시나리오 | 처리 |
|---|---|
| 위임 스킬 결과를 effect size 없이 p-value만 보고 시도 | **차단 (비타협)** — effect size + 95% CI 강제 |
| 사용자가 prereg에 없는 분석 요청 | exploratory 자동 분리 + BH-FDR (차단 아님) |
| prereg 무결성 실패 (해시 드리프트) | 경고 + 인지 확인 (Soft). 보고서에 drift 트레일 노출 |
| prereg 부재 | 모든 분석 exploratory 처리 (governance.json에 PREREG_ABSENT) |
| data_file_hash 불일치 | 경고 + informed-consent |
| 위임 스킬(예: survival-analysis) 미설치 | 환경 오류 명시 + 설치/대안 안내 (fallback: 사용자 직접) |
| Cox PH 가정 위반 (Schoenfeld p<0.05) | survival-analysis가 탐지 → 경고 + 대안 안내. 사용자 결정 |
| 사용자가 결과 보고 prereg 변경 시도 | 계획 하네스 amendment 절차 안내 (Soft) |

## 한계 명시
- 실제 모델 적합·진단은 위임 스킬 책임 — 본 스킬은 거버넌스(분류·보정·STROBE·무결성)만.
- 위임 스킬이 환경에 없으면 동작 불가 — 설치 또는 사용자 직접 분석 필요.
- 인과추론은 항상 가정 의존 — 통계적 결론만 산출, 인과 주장은 사용자 책임.
- 임상적 의미 부여(effect size 해석, positivity 위반의 임상 함의)는 사용자.
