---
name: peer-review
description: 투고 전 자체 적대적 동료검토(self peer-review). 완성된 manuscript draft를 5개 렌즈의 가상 reviewer 패널이 비판하여 약점을 사전 발견하고 수정 체크리스트를 생성한다. 실제 학술지 심사가 아닌 투고 전 리허설. Phase 7 전용. "동료검토", "peer review", "투고 전 검토", "내 논문 약점", "reviewer가 뭐라 할까"를 언급할 때 사용. peer-reviewer agent가 호출.
license: MIT
---

# Peer-Review Skill (투고 전 자체 적대적 검토)

## 목적
완성된 manuscript draft를 학술지에 투고하기 **전에**, 가상 reviewer 패널이 적대적으로 비판하여 reject/major revision을 유발할 약점을 미리 찾아내고 수정 기회를 제공한다. 분석 하네스 Phase 7 (종료 단계).

## 트리거
- peer-reviewer agent가 호출
- 사용자가 "동료검토", "peer review", "투고 전 검토", "reviewer가 뭐라 할까", "약점 찾아줘"를 직접 언급

---

## 핵심 철학

이것은 **리허설**이다. 실제 학술지 동료심사를 대체하지 않으며, 실제 reviewer comment에 대한 rebuttal 작성(투고 후 revision)은 본 하네스 범위 밖이다.

- **적대적 기본값(adversarial by default)**: reviewer는 호의적으로 읽지 않는다. "이 논문을 reject할 이유"를 능동적으로 찾는다. 불확실하면 "약점 있음" 쪽으로 기운다.
- **근거 기반 비판(grounded critique)**: 모든 지적은 원고의 구체적 위치(섹션·표·문장)나 분석 산출물(results.json, feasibility_report.md)을 근거로 한다. 막연한 "더 잘 쓰라"는 금지.
- **건설적 종결(constructive close)**: 각 major 코멘트는 *구체적 수정 방향*을 함께 제시한다.
- **Citation Grounding 계승(비타협)**: reviewer가 비교·반론용으로 인용을 들 때도 PMID/DOI 없는 자유 생성 인용은 금지. search_log.json 또는 사용자 입력 인용만.

---

## 5개 reviewer 렌즈

각 렌즈는 독립적으로 원고를 읽고 major/minor 코멘트를 생성한다. (한 사람이 5개 역할을 순차 수행해도 되고, 5개 sub-pass로 나눠도 된다.)

### R1 — 방법론·통계 (Methods & Statistics)
- 1차 분석 방법이 가설·자료 구조에 적절한가? (생존자료에 로지스틱 쓰지 않았나 등)
- 검정력/표본 크기 정당화가 있는가? EPV(Peduzzi) 충족? (feasibility_report.md 대조)
- 다중비교 보정이 confirmatory/exploratory에 맞게 적용됐나?
- 결측 처리(complete-case vs MI)가 명시·정당화됐나?
- PH 가정·calibration 등 모델 진단이 보고됐나? 위반 시 대안은?
- effect size + 95% CI가 모든 추정치에 동반됐나? (p-value 단독 금지 위반 탐지)

### R2 — 임상적 의의·외적 타당도 (Clinical Significance & Generalisability)
- 연구 질문이 임상적으로 의미 있는가, 아니면 통계적으로만 유의한가?
- effect size가 임상적으로 의미 있는 크기인가? (예: HR 1.05가 유의해도 임상 의미?)
- 단일기관·후향 코호트의 일반화 한계가 충분히 논의됐나? (STROBE 21)
- 결과가 기존 가이드라인·landmark 연구와 어떻게 다른가/같은가?

### R3 — 보고 완전성 (Reporting / STROBE)
- STROBE 22항목 중 누락 항목은? (strobe checklist 대조)
- 참여자 흐름도(N 추적, item 13)가 있는가?
- 결측 자료 수(item 14b), 추적 기간(item 14c)이 보고됐나?
- Funding(item 22), 이해상충이 명시됐나?
- 초록이 본문 결과와 일치하는가?

### R4 — 인과·편향 (Causal Inference & Bias)
- 선택 편향(referral/등록 기준)이 논의됐나? (feasibility_report 4항목 대조)
- 교란 통제가 충분한가? 측정되지 않은 교란 가능성은?
- collider/M-bias 위험이 있는 보정은 없나?
- 인과적 주장("A가 B를 유발")을 관찰자료가 지지하지 못하는데 쓰지 않았나?

### R5 — 인용·주장 근거 (Citation & Claim Grounding)
- Introduction/Discussion의 모든 주장이 인용으로 뒷받침되나?
- 인용된 논문이 실제로 그 주장을 지지하는가? (과대 인용·오인용 의심 표시)
- 모든 인용에 PMID/DOI가 있는가? (없으면 환각 의심 — 비타협 거절)
- 자기 인용·인용 누락(중요 반대 근거 누락)은 없나?

---

## 구동 과정 (7단계)

```
[1] 입력 수집 — manuscript_draft.docx (또는 .md), prereg.json, results.json,
    feasibility_report.md, strobe checklist, search_log.json
        ↓
[2] 사전등록 무결성 자체 검증 (prereg_check.py, 드리프트 시 경고만)
        ↓
[3] 5개 렌즈(R1–R5) 각각 독립 비판 패스 실행
    각 코멘트: {severity: major/minor, 위치, 문제, 근거, 수정 방향}
        ↓
[4] 코멘트 통합 + 중복 제거 + 심각도 순 정렬
        ↓
[5] 투고 준비도(submission readiness) 평가
    - major 0건 → "ready (minor 반영 권장)"
    - major 1–2건 → "minor-to-major revision 예상"
    - major 3건+ → "major revision / reject 위험 — 수정 필수"
        ↓
[6] 수정 체크리스트 생성 (각 항목에 담당 Phase: 재분석=Phase5 / 재집필=Phase6)
        ↓
[7] G7 게이트 — 사용자에게 보고서 제시 + 다음 단계 4지선다
```

---

## 출력 명세

| 산출물 | 위치 | 의미 |
|---|---|---|
| `review_report.md` | `phase7_review/review_report.md` | 5개 렌즈 코멘트 + 심각도 정렬 + 투고 준비도 |
| `revision_checklist.md` | `phase7_review/revision_checklist.md` | 수정 항목별 체크리스트 (담당 Phase 표시) |
| evolution_log 추가 기록 | `workspace/{project}/evolution_log.md` | Phase 7 진입·완료, 준비도 평가 |

### review_report.md 템플릿

```markdown
# Self Peer-Review Report — {project-name}
**검토일**: {ISO 8601}
**원고**: phase6_manuscript/manuscript_draft.docx
**투고 준비도**: {ready / minor revision / major revision 위험}
**Major 코멘트 N건, Minor 코멘트 M건**

> ⚠️ 본 보고서는 투고 전 *자체 리허설*입니다. 실제 학술지 동료심사를 대체하지 않습니다.

---

## 심각도 순 종합 (Major 우선)

### [MAJOR-1] (R1 방법·통계) — Results 2절, Table 3
**문제**: Cox 모델 PH 가정 검정(Schoenfeld) 결과가 보고되지 않음.
**근거**: results.json에 schoenfeld 항목 없음; STROBE item 12 미충족.
**수정 방향**: PH 가정 검정 추가, 위반 시 stratified Cox 또는 time-varying coefficient. (→ Phase 5)

### [MAJOR-2] (R4 인과·편향) — Discussion 3문단
...

---

## 렌즈별 상세

### R1 — 방법론·통계
- [major] ...
- [minor] ...

### R2 — 임상적 의의·외적 타당도
...

### R3 — 보고 완전성 (STROBE)
...

### R4 — 인과·편향
...

### R5 — 인용·주장 근거
...

---

## 투고 준비도 평가
{ready / minor / major} — {한 문단 요약}
```

---

## 실패 모드

| 시나리오 | 처리 |
|---|---|
| manuscript draft 없음 (Phase 6 미완료) | 차단, Phase 6으로 안내 |
| reviewer가 PMID 없는 비교 인용 생성 | **거절 (Citation Grounding 비타협)** |
| reviewer가 막연한 비판("더 명확히") | 거절 — 구체적 위치·근거·수정 방향 강제 |
| 사용자가 "호의적으로 봐줘" 요청 | 거절 — 적대적 검토가 본 스킬의 가치. 호의적 검토는 약점을 놓침 |
| major 0건이지만 사용자가 더 엄격한 검토 원함 | 다른 렌즈·더 깐깐한 패널로 재실행 |

---

## 한계 명시 (의도된)
- 본 검토는 *리허설*이지 실제 동료심사가 아니다. 실제 학술지 reviewer의 분야 전문성·최신 문헌 지식·주관적 선호를 완전히 재현할 수 없다.
- 투고 후 실제 reviewer comment에 대한 rebuttal 작성·재투고(revision)는 본 하네스 범위 밖 — 사용자 직접 처리.
- 임상적 가치 판단(이 결과가 분야에 중요한가)은 여전히 LLM 약점 영역 — 사용자 검토 필수.
- reviewer 코멘트가 모두 타당한 것은 아니다. 각 코멘트의 수용·반박은 사용자(저자)의 학술적 판단 영역.
