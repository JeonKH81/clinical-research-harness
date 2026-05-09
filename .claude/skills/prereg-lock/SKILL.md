---
name: prereg-lock
description: 임상연구 가설과 분석 계획을 SHA-256 해시로 기록하고 변경 사실을 자동 로깅한다 (Soft 기록 모델, informed-consent 기반). HARKing 방지를 위한 자동 감사 트레일 역할. Phase 2의 G2 게이트 및 Phase 5 진입 시 무결성 검증에 사용. hypothesis-refiner와 statistician agent가 호출.
license: MIT
---

# Pre-registration Lock Skill

## 목적
가설과 분석 계획을 비가역적으로 잠가 HARKing(Hypothesizing After Results are Known)을 구조적으로 방지합니다.

## 트리거
- Phase 2 종료 시 hypothesis-refiner가 G2 게이트에서 호출 (lock 명령 = 기록)
- Phase 5 진입 시 statistician가 무결성 검증으로 호출 (verify 명령)
- 사용자가 정식 변경 사유 기록을 원할 때 amendment 처리 (amend 명령, 선택)
- Phase 3(protocol-writer) 진입 시 prereg 해시 검증

---

## 작동 원칙 (5가지) — Soft 기록 모델

### 1. Hash recording (해시 기록, 봉인 아님)
prereg.json 생성 시 SHA-256 해시를 함께 기록한다. 다만 파일 권한 강제(chmod 444)는 하지 않으며, 변경 자체는 시스템 차원에서 차단되지 않는다 (informed-consent 모델).

### 2. Auto audit trail (자동 감사 트레일)
변경 시점·해시 드리프트·amendment 모두 evolution_log에 자동 기록. 사용자가 prereg.json을 직접 수정하면 다음 verify 시 경고 + PREREG_HASH_DRIFT 이벤트가 evolution_log에 자동 추가됨.

### 3. HARKing tracking via logging (HARKing은 차단이 아닌 기록)
HARKing 방지는 *기술적 차단*이 아닌 *자동 로깅*으로 처리. 가설을 자유롭게 다듬되, 변경 사실은 evolution_log에 자동 기록되어 사용자가 본인의 학술 무결성을 회고적으로 관리할 수 있다.

### 4. Optional formal amendment (선택적 정식 amendment)
정식 변경 사유 기록을 원하면 lock.py amend 명령으로 amendment_log에 명시적 트레일 생성. 선택 절차이며 강제 아님.

### 5. Deterministic hashing (결정론적 해싱)
JSON 정규화(canonical form, UTF-8, 정렬된 키)로 해싱. 같은 내용은 어느 컴퓨터에서 어느 시점에 해싱해도 같은 해시. 재현성 보장.

**진짜 비가역 사전등록 필요 시**: OSF·AsPredicted·ClinicalTrials.gov 같은 외부 timestamping 서비스 사용 권고. 본 하네스의 hash 기록은 *내부 감사 트레일* 용도이지 외부 사전등록 대체가 아님.

## prereg.json 스키마

```json
{
  "prereg_id": "PCI-MVD-2026-001",
  "version": 1,
  "locked_at": "2026-05-07T14:30:00+09:00",
  "hash": "sha256:a3f5c8...",
  "researcher": "{사용자 이름}",
  "project": "PCI-MVD-2026",

  "hypothesis": {
    "design": "retrospective cohort",
    "population": "≥60세 STEMI 환자 중 primary PCI 시행자",
    "exposure": "다혈관 질환 (≥2 epicardial stenosis ≥70%)",
    "comparator": "단일혈관 질환",
    "outcome_primary": {
      "name": "1년 MACE",
      "definition": "all-cause death + MI + revascularization",
      "timepoint": "365 days",
      "measure": "Kaplan-Meier + Cox HR"
    },
    "outcomes_secondary": [
      {"name": "1년 사망률", "definition": "all-cause mortality at 365 days"},
      {"name": "Stent thrombosis", "definition": "ARC-defined definite/probable ST"}
    ],
    "effect_size_assumption": {
      "HR": 1.30,
      "alpha": 0.05,
      "power": 0.80
    }
  },

  "analysis_plan": {
    "primary_method": "Cox PH with IPTW",
    "covariates": ["age", "sex", "DM", "HTN", "LVEF", "creatinine", "TIMI_flow_pre"],
    "missing_handling": "complete-case for primary, MI for sensitivity",
    "sensitivity": [
      "complete-case",
      "multiple imputation (m=20)",
      "PSM (1:1, caliper 0.2)",
      "subgroup: age≥75 vs <75"
    ],
    "multiple_comparisons": {
      "primary": "Bonferroni",
      "exploratory": "Benjamini-Hochberg FDR"
    },
    "random_seed": 42,
    "software": ["Python 3.11", "lifelines 0.27", "statsmodels 0.14"]
  },

  "data_provenance": {
    "data_file_hash": "sha256:b2e4...",
    "data_dictionary_path": "input/data_dictionary.md",
    "n_records": 1234,
    "source": "{기관 IRB 번호}"
  },

  "amendment_log": []
}
```

## 절차

### 1. 잠금 (Lock)

```bash
python scripts/lock.py lock \
  --project {project-name} \
  --hypothesis-input {hypothesis_draft.json} \
  --analysis-plan {analysis_plan.json}
```

수행 작업:
1. JSON 정규화 (canonical form, UTF-8, sorted keys)
2. SHA-256 해시 계산
3. `prereg.json`에 hash + locked_at 추가
4. 파일 권한을 read-only로 설정 (`chmod 444`)
5. evolution_log에 잠금 사실 기록

### 2. 검증 (Verify)

```bash
python scripts/lock.py verify \
  --project {project-name}
```

수행 작업:
1. prereg.json의 hash 필드를 제외하고 canonical form으로 재해시
2. 저장된 hash와 비교
3. 일치 시 무결성 OK, 불일치 시 alert + evolution_log 기록

Phase 5 진입 시 statistician가 항상 호출.

### 3. Amendment

잠금 후 가설/분석 변경 요청 시:

```bash
python scripts/lock.py amend \
  --project {project-name} \
  --reason "..." \
  --new-hypothesis-input {new_hypothesis.json}
```

수행 작업:
1. 현재 prereg.json을 prereg_v{N}.json으로 이름 변경 (보관)
2. 새 prereg.json 생성, version 증가, amendment_log에 다음 추가:
   ```json
   {
     "amended_at": "2026-05-15T10:00:00+09:00",
     "previous_hash": "sha256:a3f5c8...",
     "previous_version": 1,
     "reason": "Phase 4에서 LVEF 변수 결측률 60%로 확인되어 effect modifier로 변경",
     "amended_by": "{사용자}"
   }
   ```
3. 새 hash 계산 및 잠금
4. 이전 결과는 명시적으로 "amendment 이전"으로 라벨링

## 실패 모드 (Soft 기록 + informed-consent)

| 시나리오 | 처리 |
|---|---|
| 사용자가 prereg.json을 수동 편집 | verify에서 해시 드리프트 감지 → 경고 출력 + evolution_log에 PREREG_HASH_DRIFT 기록 → **차단 안 함, Phase 5 진행 가능** |
| 사용자가 가설 자유 변경 요청 | 자유 변경 허용. 정식 amendment 사유 기록을 원하면 amend 명령 안내 |
| amendment 명령 사용 시 사유 빈 문자열 | 거절 (정식 amendment는 사유 필수) |
| Phase 5에서 해시 드리프트 발견 | 경고 + 사용자에게 "변경된 가설로 진행할 것인지" 확인 + 진행 시 evolution_log에 사용자 동의 기록 |
| 같은 프로젝트에 prereg.json 존재 + lock 재실행 | 거절, "이미 기록됨 — 직접 수정하거나 amend를 사용하시오" 안내 |
| 데이터 파일 해시가 prereg와 다름 (Phase 5) | 경고 + 사용자 인지 확인 → 진행 가능 |
| 기록 시점에 data_file_hash가 null | 허용 (데이터 미준비 상태에서 사전 기록 가능). Phase 4에서 채움 |

## 핵심 정책

### 보안
- 해시 계산은 서버 시간 의존 없음 (재현 가능)
- amendment_log는 append-only (기존 항목 수정 불가)
- 잠긴 prereg.json은 읽기 전용 권한

### 투명성
- 모든 amendment는 영구 기록되며, 최종 보고 시 명시적으로 노출
- "v1 잠금 후 v2로 amendment, 사유: ..."를 STROBE 보고에 포함

## 한계 명시

- 본 잠금은 **소셜 약속**의 자동화 — 기술적으로 사용자가 prereg.json을 우회 편집할 수 있음. 이는 evolution_log의 시점 비교로 탐지 가능하나 완벽한 방어는 아님.
- 진정한 사전등록을 원한다면 OSF(osf.io), AsPredicted, ClinicalTrials.gov 등 외부 timestamping 서비스를 함께 사용 권장.
