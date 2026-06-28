---
name: data-inspect
description: 사전등록된 가설이 주어진 데이터로 검정 가능한지 평가. EDA, 결측 패턴 분석, 검정력 계산, Peduzzi rule(EPV≥10) 점검을 수행하며 verdict(testable/partial/not testable)를 산출. PHI 보호 정책에 따라 행 단위 데이터는 LLM에 전달하지 않음. Phase 4 전용.
license: MIT
---

# Data-Inspect Skill

## 목적
잠긴 사전등록 가설이 주어진 데이터로 검정 가능한지 평가하고 verdict를 산출합니다.

## 트리거
- data-inspector agent가 호출
- 사용자가 "데이터 검정", "표본 크기", "검정력", "EDA"를 직접 언급

---

## 작동 원칙 (5가지)

### 1. PHI Local-only enforcement (PHI 로컬 한정 — 비타협)
행 단위 데이터(개별 환자 row)는 LLM 컨텍스트에 **절대 전달되지 않는다.** 컬럼명·요약 통계·결측 패턴만 LLM이 본다. 식별자 의심 컬럼은 자동 마스킹 후 분석에서 제외. **이 정책은 informed-consent로도 풀지 않는** Citation Grounding과 함께 본 하네스의 비타협 영역.

### 2. Auto-detection vs human review separation (자동 vs 사람 분리)
데이터로 자동 탐지 가능한 영역(결측 패턴, EPV, 검정력, 다중공선성, 이벤트율)과 자동 탐지 불가능한 영역(선택 편향, 측정 편향, 교란 누락, collider 위험)을 명시적으로 분리. 후자는 G4 게이트에서 사용자 검토 강제.

### 3. Verdict as recommendation, not gate (verdict는 권고)
testable / partial / not testable verdict는 사용자 결정의 *입력*일 뿐 *차단 게이트*가 아니다. not testable이라도 사용자가 informed-consent + 로깅으로 진행 가능 (다만 결과는 약한 근거임을 명시).

### 4. No auto-rewrite of hypothesis (가설 자동 재작성 금지)
verdict가 not testable이어도 LLM이 가설을 자동으로 다시 만들지 않는다. 후보 질문 *제안만* 하고 사용자가 직접 선택. 자동 재작성은 시스템적 HARKing.

### 5. Reproducible analysis context (재현 가능한 분석 컨텍스트)
Phase 5 분석을 위한 변수 매핑·결측 처리 방안·자료 정의를 Phase 4에서 고정. `variable_mapping.json` + `feasibility_report.md` + 데이터 SHA-256를 Phase 5의 입력으로 사용 (재현성 보장).

---

## 구동 과정 (8단계)

```
[1] prereg.json 무결성 확인 (prereg_check.py, 드리프트 시 경고만 — Soft 모델)
        ↓
[2] 데이터 파일 로드 + PHI 의심 컬럼 자동 마스킹
    (마스킹된 컬럼명을 사용자에게 보고)
        ↓
[3] 변수 매핑: prereg의 P/E/C/O를 데이터 컬럼에 매핑
    핵심 변수 누락 → 사용자 알림
        ↓
[4a] Feasibility 점검 (eda.py — 사전등록 특화)
     - 변수 매핑 (P/E/C/O + time_to_outcome)
     - 이벤트율 (< 5% 시 경고 — 희귀 결과)
     - EPV (Peduzzi) + 검정력
[4b] 전체 EDA 위임 → Skill: anthropic-skills:clinical-eda-report
     - 결측 패턴·Little's MCAR·VIF·이상치·분포 플롯·상관 heatmap (HTML 한 파일)
        ↓
[5] 검정력 계산 (Peduzzi rule + prereg 효과 크기 가정)
    - EPV (events per variable) ≥ 10 / < 10 / < 5
        ↓
[6] Verdict 산출 (testable / partially testable / not testable)
    + 데이터 SHA-256 계산 → prereg.data_provenance.data_file_hash 채움
        ↓
[7] 자동 탐지 불가 항목 → 사용자 검토 게이트
    - 선택 편향 (referral pattern)
    - 측정 편향 (비맹검 outcome)
    - 교란 누락 (데이터에 없는 공변량)
    - Collider 위험 (DAG 검토 — 사용자/도메인 지식 필요)
        ↓
[8] G4 게이트 — verdict + 사용자 검토 응답 + 진행 결정 4지선다
```

## 핵심 정책

### PHI 보호 (Soft 마스킹 + 행 비전송 비타협, v1.0)

**비타협 (행 단위 LLM 비전송)**: 데이터 파일은 로컬 코드 실행 환경에서만 처리. LLM 컨텍스트에는 컬럼명·요약 통계·결측 패턴만 전달. 개별 행(row) 데이터 절대 전달 금지.

**Soft 마스킹 — 자동 마스킹 대상은 직접 식별자에 한정**:

| 카테고리 | 컬럼명 키워드 | 처리 |
|---|---|---|
| **PHI_AUTOMASK** (자동 마스킹) | name, first_name, last_name, fullname, patient_name, dob, birth_date, birthdate, date_of_birth, ssn, national_id, rrn, jumin (주민번호) | 자동 마스킹 + 분석 자동 제외 |
| **PHI_WARN** (인지 확인) | mrn, chart_no, chart_number, patient_id, medical_record, address, addr, zip, postal_code, phone, tel, mobile, email, ip_address | 사용자에게 경고만 — 분석 포함 여부는 사용자 결정 (informed-consent) |

**자동 마스킹 정책 (실명·DOB·주민번호)**: 거의 항상 직접 식별자이므로 사용자 동의 없이 분석에서 제외하고 LLM 컨텍스트에 전달 안 함.

**WARN 정책 (차트번호·주소·전화·이메일 등)**: 후향 코호트에서 차트번호는 추적용으로 의도적으로 사용되는 경우가 많고, 주소(시·도 단위)는 지역 분석에 사용 가능. 따라서 자동 차단보다 사용자 인지 확인 후 본인 책임으로 진행. 행 단위 데이터는 LLM에 전달 안 되므로 LLM 노출 위험은 여전히 차단됨.

**사용자 책임 영역**: 본 하네스 출력물(.docx, .xlsx, HTML 리포트 등)을 외부에 공유 시 차트번호·주소 같은 컬럼이 포함되지 않도록 사용자가 명시적으로 점검 (특히 학회 발표·논문 보충자료).

## 입력
- `workspace/{project}/phase2_hypothesis/prereg.json` (잠긴 사전등록)
- `workspace/{project}/input/data.csv` (또는 .parquet, .xlsx)
- (선택) `workspace/{project}/input/data_dictionary.md`

## 출력
| 산출물 | 생성 주체 | 의미 |
|---|---|---|
| `phase4_data/feasibility_report.md` / `.json` | eda.py | verdict·매핑·EPV·이벤트율·PHI 보고 (주 보고서) |
| `phase4_data/variable_mapping.json` | eda.py | 가설 변수 ↔ 데이터 컬럼 매핑 (Phase 5 입력) |
| EDA 리포트 (HTML) | `anthropic-skills:clinical-eda-report` | 결측·MCAR·VIF·이상치·분포·상관 |

> 결측 패턴 시각화·VIF·이상치·MCAR 등 **전체 EDA는 clinical-eda-report에 위임**합니다. eda.py는 사전등록 대비 *feasibility 판정*에 집중합니다.

## 절차

### 1. 사전등록 무결성 확인
```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/stat-analysis/scripts/prereg_check.py --project {project}
```

### 2. 변수 매핑
prereg.json의 P, E, C, O 변수를 데이터 컬럼에 매핑. 누락된 핵심 변수는 명시적 경고.

### 3. Feasibility 점검 (eda.py)
```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/data-inspect/scripts/eda.py \
  --data workspace/{project}/input/data.csv \
  --prereg workspace/{project}/phase2_hypothesis/prereg.json \
  --out workspace/{project}/phase4_data/
```

### 4. 자동 탐지 항목

**eda.py (사전등록 특화 feasibility):**

| 항목 | 기준 | 결과 처리 |
|---|---|---|
| 이벤트율 | 결과 변수 발생률 | <5% 시 경고 (희귀 결과 — Firth/exact 고려) |
| Peduzzi rule | EPV = events / covariates | <10 시 경고, <5 시 not testable 후보 |
| 핵심 변수 매핑 | exposure·outcome·time_to_outcome 존재 | 누락 시 not testable 후보 |

**clinical-eda-report (위임 — 전체 EDA):**

| 항목 | 비고 |
|---|---|
| 결측 패턴·Little's MCAR | HTML 리포트 |
| 이상치 (IQR / z>3) | implausible value 감지 |
| 다중공선성 (VIF>10) | 상관 heatmap 동반 |
| 분포 플롯·변수별 요약 | n·타입별 |

```
Skill: anthropic-skills:clinical-eda-report   (data.csv 업로드)
```

### 5. Verdict 산출

```
testable:
  - 모든 핵심 변수 존재
  - 검정력 ≥ 0.8
  - EPV ≥ 10
  - 결측 < 20% (또는 사용자 정의)

partially testable:
  - 핵심 변수는 존재하나 일부 부수 변수 결측
  - 검정력 0.5–0.8
  - 1차 분석은 가능하나 일부 부수 분석 제한

not testable:
  - 핵심 변수 결측
  - 검정력 < 0.5
  - EPV < 5
  - 사실상 분석 불가능
```

### 6. (Verdict가 not testable인 경우) 대안 질문 제안

데이터에 존재하는 변수들로 답할 수 있는 질문 후보 3–5개를 제안만 합니다. **자동 재작성 금지** — 사용자가 직접 선택.

대안 질문 제안 시 명시:
> "원래 가설은 이 데이터로 검정 불가합니다. 아래는 데이터에 존재하는 변수들로 답할 수 있는 후보 질문입니다. 그러나 데이터를 본 후 가설을 변경하는 것은 HARKing 위험이 있으므로, 채택 시 prereg.json amendment에 사유가 영구 기록됩니다."

### 7. 자동 탐지 불가 항목 → 사용자 검토 강제

다음은 데이터만으로 자동 탐지 불가능 — feasibility_report.md에 명시적 섹션으로 분리하여 사용자 검토 요청:

- **선택 편향**: 등록 기준의 비기록 편향, referral pattern
- **측정 편향**: 결과 평가의 비맹검
- **교란 누락**: 데이터에 없는 중요 공변량 (예: 흡연력, 가족력)
- **Collider 위험**: DAG 검토 (M-bias, Cole IJE 2010)

DAG 후보를 자동 생성하여 사용자 검토 요청.

## 게이트 G4 인계

verdict와 4가지 선택지를 사용자에게 제시:
1. 진행 (testable 또는 partial)
2. 대안 질문 채택 → amendment 절차
3. 데이터 보완 후 재시도
4. 중단

## 실패 모드 (PHI 보호 비타협 + 나머지 informed-consent)

| 시나리오 | 처리 |
|---|---|
| 행 단위 데이터를 LLM 컨텍스트로 전달 시도 | **차단 (PHI Local-only 비타협)** — 어떤 사용자 요청도 우회 불가 |
| PHI 의심 컬럼 발견 | 자동 마스킹 + 사용자 알림. 사용자가 "그래도 사용" 요청 시 informed-consent + evolution_log 기록 (단 LLM 컨텍스트는 여전히 마스킹 유지) |
| prereg.json 없는 상태에서 Phase 4 진입 | 차단, Phase 2로 환원 |
| 데이터 파일 없음 | 사용자에게 경로 요청 |
| 데이터 파일이 Dropbox/iCloud 동기화 폴더 | Phase 0의 Dropbox 정책 재고지 + 사용자 인지 확인 |
| 핵심 변수 (E or O) 누락 | verdict=not_testable + 대안 질문 제안 (자동 재작성 금지) |
| 검정력 < 0.5 | verdict=not_testable + 명시적 사용자 override 요구 |
| EPV < 5 | verdict=not_testable (Peduzzi rule 위반) |
| 데이터 해시가 prereg와 다름 | 경고 + 사용자 인지 확인 (informed-consent: 데이터 추가됐을 수 있음) |
| 사용자가 verdict 결과 보고 가설 변경 시도 | Phase 2로 amendment 절차 안내 (Soft 모델) |

## 한계 명시

- HARKing 위험: 데이터 본 후 가설 변경은 amendment_log에 영구 기록.
- 선택 편향 자동 탐지는 사실상 불가능 — 항상 사용자 검토 필수.
- DAG 후보는 자동 생성 보조일 뿐, 도메인 지식 검토 대체 불가.
