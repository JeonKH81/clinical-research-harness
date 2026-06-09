---
name: stat-analysis
description: 잠긴 사전등록에 따라 통계 분석 실행. Table 1, primary, secondary, sensitivity 분석 + 진단 플롯 + STROBE 22항목 자동 점검. 사전등록과 어긋나는 분석은 자동으로 exploratory 라벨 부여하여 p-hacking을 방지. Phase 5 전용. statistician agent가 호출.
license: MIT
---

# Stat-Analysis Skill

## 목적
잠긴 사전등록 계획에 따라 통계 분석을 실행하고 STROBE 형식의 보고서를 자동 생성합니다.

## 트리거
- statistician agent가 호출
- 사용자가 "분석", "Cox", "회귀", "생존", "Table 1"을 직접 언급

---

## 작동 원칙 (5가지)

### 1. Pre-reg as analysis source (사전등록이 분석 출처)
prereg.json의 분석 계획을 그대로 따른다. 새 공변량 추가·하위군 분석 변경·다른 모델 사용은 모두 *exploratory* 섹션으로 자동 분리.

### 2. Confirmatory/Exploratory auto-separation (자동 분리)
사전등록 명시 분석 → confirmatory 섹션. 그 외 모든 분석 → exploratory 섹션. 두 섹션은 출력에서 명확히 분리되어 사용자(및 동료심사자)가 즉시 구분 가능.

### 3. Effect size + 95% CI (p-value 단독 보고 금지 — 비타협)
모든 효과 추정치는 effect size + 95% CI 동반. p-value 단독 보고는 **자동 거절**. p-hacking·잘못된 임상 해석을 구조적으로 방지.

### 4. Reproducibility by seed (시드 고정)
prereg.random_seed 사용 (default 42). requirements.txt(Python) 또는 renv.lock(R) 자동 생성하여 환경까지 고정.

### 5. Diagnostics mandatory (진단 필수)
모델별 진단 자동 출력:
- Cox PH → Schoenfeld residuals (PH 가정), log-log survival
- Logistic → Hosmer-Lemeshow, calibration plot
- Linear → residual plots, QQ plot
- 예측모델 → ROC, calibration curve, decision curve

가정 위반 자동 경고 + 대안 모델 제안 (예: PH 위반 시 stratified Cox / time-varying coefficient / AFT).

---

## 구동 과정 (9단계)

> **IRB 게이트 없음**: 분석 하네스는 IRB 무관 독립 실행입니다. 구 v1의 irb_status 점검/차단/override 단계는 제거되었습니다. IRB 책임은 전적으로 사용자에게 있습니다.

```
[1] prereg.json 무결성 검증 (prereg_check.py)
    드리프트 → 경고 + 사용자 인지 확인 (Soft 모델, 차단 아님)
    prereg.json 부재 → 모든 분석을 exploratory로 처리함을 안내
        ↓
[2] data_file_hash 검증 (Phase 4에서 기록된 것과 비교)
    불일치 → 경고 + informed-consent
        ↓
[3] Table 1 자동 생성 (baseline characteristics + SMD)
        ↓
[4] 1차 분석 (사전등록된 primary endpoint, primary_method 그대로)
        ↓
[5] 사전등록 부수 분석 (secondary outcomes)
        ↓
[6] 민감도 분석 (사전등록된 것: complete-case, MI, IPTW, PSM 등)
        ↓
[7] 진단 플롯 (PH, calibration, residuals, ROC 등)
    가정 위반 시 자동 경고 + 대안 모델 제안
        ↓
[8] Exploratory 분석 (있다면 별도 섹션, BH-FDR 자동 적용)
        ↓
[9] STROBE 22항목 자동 점검 + G5 게이트
```

## 입력
- `workspace/{project}/phase2_hypothesis/prereg.json` (잠긴, 해시 검증 통과)
- `workspace/{project}/input/data.csv`
- `workspace/{project}/phase4_data/variable_mapping.json`
- `workspace/{project}/phase4_data/feasibility_report.md`

## 출력
- `workspace/{project}/phase5_analysis/results.html` — 대화형 보고서
- `workspace/{project}/phase5_analysis/results.xlsx` — 표 데이터
- `workspace/{project}/phase5_analysis/strobe_checklist.md` — 22항목 점검
- `workspace/{project}/phase5_analysis/analysis.ipynb` — 재현 코드
- `workspace/{project}/phase5_analysis/figure_specs.json` — Phase 5(v2)용 메타
- `workspace/{project}/phase5_analysis/diagnostics/` — 진단 플롯

## 절대 규칙

### 1. 사전등록 무결성 검증 (필수 첫 단계)

```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/stat-analysis/scripts/prereg_check.py --project {project}
```

해시 불일치(드리프트) 시 **차단 없이 경고 + 사용자 인지 확인** (Soft 모델). 진행 시 분석 보고서에 drift 트레일 자동 노출. prereg.json 부재 시 모든 분석을 exploratory로 처리함을 안내.

### 2. Confirmatory vs Exploratory 분리

- prereg.analysis_plan에 명시된 분석 → `confirmatory` 섹션
- 그 외 모든 분석 → `exploratory` 섹션
- 두 섹션은 출력에서 명확히 분리

### 3. 다중비교 보정

- Confirmatory: prereg에 명시된 방법 (default Bonferroni)
- Exploratory: Benjamini–Hochberg FDR

### 4. 보고 규칙

- p-value 단독 보고 금지
- 항상 **effect size + 95% CI** 동반
- 임상적 해석 단락은 사용자가 검토 (자동 생성하되 최종 승인은 사용자)

## 실행 순서

### Step 1. 데이터 로드 + 사전등록 검증
```python
data_hash = sha256(data_file)
assert data_hash == prereg.data_provenance.data_file_hash, "데이터 변경 감지!"
```

### Step 2. Table 1 (Baseline characteristics)
- 연속변수: Shapiro-Wilk → 정규면 mean±SD, 비정규면 median[IQR]
- 범주변수: N (%)
- 군 간 비교: Welch's t / Mann–Whitney / chi-square / Fisher
- SMD (Cohen's d 또는 Cohen's h) 자동 계산
- SMD > 0.1은 강조 (PSM/IPTW 후 평가에 유용)

### Step 3. Primary Analysis
prereg.analysis_plan.primary_method대로 실행. 예시:

```python
from lifelines import CoxPHFitter
cph = CoxPHFitter()
cph.fit(df, duration_col="time_to_mace_days", event_col="mace",
        weights_col="iptw_weight", robust=True,
        formula="exposure + age + sex + DM + LVEF")
print(cph.summary)
```

출력:
- HR, 95% CI, p-value
- C-index (생존모델)
- Schoenfeld residuals (PH 가정 검정)

### Step 4. Pre-specified Secondary Analyses
prereg.outcomes_secondary 각각에 대해 실행.

### Step 5. Sensitivity Analyses
prereg.analysis_plan.sensitivity 명시된 것:
- Complete-case
- Multiple imputation (m=20 default)
- IPTW (overlap weights, ATT)
- PSM (1:1, caliper 0.2)
- Subgroup analyses (사전 명시된 것만)

### Step 6. Diagnostic Plots
- **Cox**: Schoenfeld residuals, log-log survival
- **Logistic**: Hosmer-Lemeshow, calibration plot
- **Linear**: residual plots, QQ plot
- **Predictive**: ROC, calibration, decision curve

PH 가정 위반 자동 경고 + 대안 모델 제안 (stratified Cox, time-varying coefficient, AFT).

### Step 7. Exploratory (있다면)
사용자가 prereg 외 분석을 요청한 경우:
- 별도 섹션, 명시적 라벨
- BH FDR 보정
- "이 결과는 hypothesis-generating으로 해석되어야 함" 자동 주석

### Step 8. STROBE 22항목 점검
`references/STROBE_checklist.md` 참조. 각 항목:
- ✅ 충족 (자동 또는 prereg에서 추출)
- ⚠️ 누락 (사용자 입력 필요)
- N/A (사유 명시)

## 도구

```bash
python scripts/run_analysis.py \
  --data workspace/{project}/input/data.csv \
  --prereg workspace/{project}/phase2_hypothesis/prereg.json \
  --variable-mapping workspace/{project}/phase4_data/variable_mapping.json \
  --out workspace/{project}/phase5_analysis/
```

기본 환경:
- Python 3.11+, pandas, numpy, scipy, statsmodels, lifelines, scikit-learn, matplotlib
- (선택) R 4.3+, survival, rms, MatchIt — renv.lock 자동 생성
- 난수 시드: prereg.analysis_plan.random_seed (default 42)

## 게이트 G5 인계

분석 완료 후 사용자 검토 요청:
1. 임상적 해석 적절성 — effect size의 임상적 의미
2. 진단 플롯 검토 — PH 가정 위반 시 대안 모델 검토
3. 민감도 분석 일관성 — 결과 robustness
4. 다음 단계 — 추가 분석 / Phase 5(v2)로 / 종료

## 실패 모드 (p-value 단독 비타협 + 나머지 informed-consent)

| 시나리오 | 처리 |
|---|---|
| LLM이 effect size 없이 p-value만 출력 시도 | **차단 (비타협)** — effect size + 95% CI 강제 |
| 사용자가 prereg에 없는 분석 요청 | exploratory 섹션 자동 분리 + BH-FDR 보정 자동 적용 (차단 안 함, 분리만) |
| prereg 무결성 실패 (해시 드리프트) | 경고 + 사용자 인지 확인 (Soft 모델). 진행 시 분석 보고서에 amendment 트레일 자동 노출 |
| data_file_hash 불일치 | 경고 + informed-consent. 데이터가 추가/변경된 경우 사용자 의도 확인 |
| Cox PH 가정 위반 (Schoenfeld p<0.05) | 자동 경고 + 대안 모델 제안. 사용자가 결정 |
| IPTW positivity 위반 | 자동 탐지 + 사용자 알림 (대안: trimming, overlap weights) |
| 사용자가 결과 보고 prereg 변경 시도 | Phase 2 amendment 절차 안내 (Soft 모델). 자유 변경 가능하되 amendment 사실 분석 보고서에 자동 노출 |
| Multiple imputation을 primary로 사용 | 권고 안 함 (complete-case가 primary, MI는 sensitivity). 사용자 명시적 요청 시 informed-consent로 진행 |

## 한계 명시

- PH 가정 위반 시 대안 제안하나 최종 선택은 사용자
- Multiple imputation은 default sensitivity, primary는 complete-case 권장
- IPTW positivity 위반은 자동 탐지하되 임상적 의미 부여는 사용자
- 인과추론은 항상 가정 의존 — 본 도구는 통계적 결론만 산출, 인과 주장은 사용자 책임
