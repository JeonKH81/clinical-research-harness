---
name: protocol-writer
description: Phase 2의 잠긴 사전등록을 IRB 제출용 한국어 연구계획서(.docx)로 자동 변환. anthropic-skills:research-protocol-writer 스킬의 wrapper로, 전기현 교수 표준 IRB 템플릿(분당서울대병원)을 따른다. Phase 3 전용. protocol-writer agent가 호출.
license: MIT
---

# Protocol-Writer Skill

## 목적
잠긴 사전등록(prereg.json) + Phase 1 문헌 결과를 통합해 IRB 제출용 한국어 .docx 연구계획서를 생성합니다.

## 트리거
- protocol-writer agent가 호출
- 사용자가 "연구계획서", "IRB 제출", "프로토콜 작성"을 직접 언급

## 핵심 정책

### 1. Single Source of Truth
가설·분석 계획은 prereg.json이 유일한 출처입니다. 사용자가 가설을 두 번 입력하지 않도록, prereg의 모든 필드를 IRB 계획서 섹션에 자동 매핑합니다.

### 2. Citation Grounding (계승)
연구계획서의 참고문헌은 Phase 1의 `search_log.json`에서 PMID 동반된 것만 사용합니다. 자유 생성 인용 금지.

### 3. Pre-reg Hash Linkage
생성된 protocol과 prereg가 한 쌍임을 보장하기 위해 `irb_metadata.json`의 `linked_prereg_hash` 필드에 prereg의 SHA-256를 기록합니다. Phase 5 진입 시 statistician가 두 해시의 일관성을 함께 검증합니다.

## 입력
- `workspace/{project}/phase2_hypothesis/prereg.json` (잠긴 상태)
- `workspace/{project}/phase1_lit/gap_map.md`
- `workspace/{project}/phase1_lit/search_log.json`
- (선택) 사용자 추가 입력: 책임 연구자, 공동 연구자, 연구 기간, 자금 출처

## 출력
- `workspace/{project}/phase3_protocol/research_protocol.docx`
- `workspace/{project}/phase3_protocol/irb_metadata.json`

## 절차

### Step 1. 사전등록 검증
```bash
python ../prereg-lock/scripts/lock.py verify --project {project}
```

### Step 2. anthropic-skills:research-protocol-writer 호출

이 스킬은 다른 스킬을 호출하는 wrapper입니다. 절차:

1. prereg.json + gap_map.md + search_log.json 내용을 읽음
2. 사용자에게 추가 메타데이터 질문 (책임연구자, 연구 기간 등)
3. `Skill` 도구로 `anthropic-skills:research-protocol-writer` 호출
4. 호출 시 prereg의 모든 필드 + 추가 메타데이터를 입력으로 전달
5. 생성된 .docx를 `workspace/{project}/phase3_protocol/research_protocol.docx`에 저장

### Step 3. IRB 메타데이터 생성

```json
{
  "protocol_version": 1,
  "generated_at": "ISO 8601",
  "linked_prereg_hash": "sha256:...",
  "linked_prereg_version": 1,
  "irb_status": "pending_submission",
  "irb_number": null,
  "irb_approval_date": null,
  "irb_type": null,
  "irb_exempt_reason": null,
  "submission_log": []
}
```

### Step 4. 사용자 검토 및 게이트 G3

생성된 .docx를 사용자가 검토 후 4가지 선택:

| 선택 | irb_status | 다음 단계 |
|---|---|---|
| 승인 + IRB 제출 완료 | `submitted` → `approved` | IRB 번호 입력 후 Phase 4 |
| 수정 필요 | 변동 없음 | 사용자가 .docx 직접 수정 후 재호출 |
| 면제 (exempt review 또는 IRB 불필요) | `exempt` | 사유 입력 후 Phase 4 |
| 중단 | `pending_submission` | Phase 4 진입 차단 |

## 차단 정책

다음 조건에서 Phase 5(Statistician)는 자동 차단:

- `irb_status`가 `pending_submission`인 채로 Phase 5 호출 시도
- `irb_status`가 `submitted`(심사 중)인 채로 분석 진행 시도
  - 이 경우 사용자에게 경고 후 명시적 override 가능 (IRB 승인 전 분석은 권고되지 않으나 후향연구의 일부 단계에서는 허용되는 경우 있음 — 사용자 책임)

`irb_status`가 `approved`, `exempt`, `expedited` 중 하나일 때만 정상 진행.

## prereg ↔ 계획서 매핑

| prereg.json | IRB 계획서 섹션 |
|---|---|
| `hypothesis.design` | 1. 연구 설계 |
| `hypothesis.population` | 2. 대상자 (포함·제외 기준) |
| `hypothesis.exposure`, `comparator` | 3. 노출 변수, 비교군 |
| `hypothesis.outcome_primary` | 4. 1차 결과변수 |
| `hypothesis.outcomes_secondary` | 5. 2차 결과변수 |
| `hypothesis.effect_size_assumption` | 6. 표본 크기 산출 |
| `analysis_plan.primary_method` | 7. 1차 분석 방법 |
| `analysis_plan.covariates` | 7.1 공변량 |
| `analysis_plan.sensitivity` | 7.2 민감도 분석 |
| `analysis_plan.missing_handling` | 7.3 결측치 처리 |
| `data_provenance` | 8. 자료원·자료수집 |
| Phase 1 `gap_map.md` | 9. 연구 배경 |
| Phase 1 `search_log.json` | 10. 참고문헌 (PMID 동반) |

## 실패 모드 (informed-consent + Citation Grounding 비타협)

| 시나리오 | 처리 |
|---|---|
| prereg.json 없는 상태에서 Phase 3 진입 | 차단, Phase 2로 환원 (No work without identity) |
| `anthropic-skills:research-protocol-writer` 호출 실패 (스킬 미설치 등) | 환경 오류 명시, fallback 안내 (수동 .docx 작성 + 본 하네스가 시작점·매핑만 제공) |
| LLM이 prereg 외 정보를 .docx에 자유 추가 | **차단** — prereg를 source of truth로 강제 |
| Citation 환각 (PMID 없는 인용) 시도 | **차단 (Citation Grounding 비타협)** — search_log.json 외 인용 거절 |
| 사용자가 prereg.json 변경 후 Phase 3 재호출 | irb_metadata에 새 linked_prereg_hash, 이전 protocol stale 표시, 새 .docx 생성 |
| irb_metadata.json 존재 + 사용자가 G3 응답 변경 | 자유 변경 허용 (informed-consent), submission_log에 변경 이력 추가 |
| `irb_status`가 pending/submitted인데 Phase 4 진입 | 허용 (Phase 4 = 데이터 검증, IRB 승인 전에도 가능). Phase 5만 informed-consent override 게이트 |

## 한계 명시 (의도된)

- 본 스킬은 .docx 생성까지만 담당. **IRB 시스템(BRIA 등)에 자동 제출하지 않음** — 사용자가 기관 시스템에서 직접 제출
- IRB 양식은 분당서울대병원 기준 (`anthropic-skills:research-protocol-writer` 시스템 스킬의 템플릿) — 다른 기관 사용 시 시스템 스킬 자체를 그 기관용으로 customize 필요
- IRB 면제 가능 여부는 기관 정책에 따름 — 본 하네스가 면제 자격을 판정하지 않음
- IRB 승인 후 가설/분석 변경 시 prereg amendment(선택 절차) + IRB 변경 신청 동반 필요 (이중 트레일)
- IRB 시스템과 자동 연동 없음 — 사용자가 BRIA 등에서 직접 제출
