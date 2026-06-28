---
name: analysis-orchestrator
description: 임상연구 "분석·집필 하네스"의 진입점. Phase 4–7 (데이터 검정가능성 → 통계분석 → IMRaD 논문초안 → 투고 전 자체 적대적 동료검토) 라우팅과 게이트 G4–G7을 강제한다. "데이터 받았다", "분석 돌려줘", "Cox", "생존분석", "Table 1", "논문 초안", "manuscript", "동료검토", "투고 전 검토", 그리고 "다시 분석", "재분석", "다시 돌려줘", "업데이트", "이전 결과 기반", "이어서" 같은 후속·재작업 요청을 포함한 자연어에서 자동 호출. IRB 무관 독립 실행. 계획·문헌·사전등록은 별도 clinical-research-planning 플러그인이 담당.
license: MIT
---

# Clinical Research — Analysis Orchestrator

이 스킬은 **Clinical Research Harness의 분석·집필 하네스(Analysis)**의 진입점입니다. *데이터를 받은 시점부터 투고 직전 자체 동료검토까지*(Phase 4–7)를 담당합니다.

> **두 하네스 구조**:
> - **계획 (`clinical-research-planning`)**: Phase 0–3 — Intake · 문헌 · 가설/사전등록 · IRB 연구계획서
> - **분석 (이 플러그인)**: Phase 4–7 — 데이터 검정 · 통계분석 · 논문초안 · 투고 전 자체 동료검토
>
> 본 하네스는 계획 하네스가 만든 `workspace/{project}/`를 **그대로 이어받아** 동작합니다. 핵심 입력은 `phase2_hypothesis/prereg.json`(사전등록)이며, 논문 단계에서 `phase1_lit/search_log.json`·`research_opportunities.md`를 인용 근거로 사용합니다.

## IRB 정책 — 무관 독립 실행 (중요)

본 분석 하네스는 **IRB 상태와 무관하게 동작**합니다. `irb_metadata.json`의 `irb_status`를 분석 진입 차단·경고 게이트로 사용하지 **않습니다**.

- 근거: 후향적 익명화 자료의 IRB 면제, 외부 협력 전 사전 분석 등 합법 시나리오가 다양하고, IRB 적격성 판단은 기관·연구자 영역입니다.
- **IRB 책임은 전적으로 사용자(연구자)에게 있습니다.** 본 하네스는 IRB 적합성을 판정하지 않습니다.
- prereg.json이 계획 하네스 없이 사용자가 직접 작성한 경우에도 동작합니다 (prereg가 confirmatory/exploratory 기준이므로 권장 입력).

## 핵심 책임

1. **요청 분류**: 자연어 입력을 Phase 4/5/6/7로 라우팅
2. **게이트 검증**: 다음 Phase 진입 전 사용자 명시 승인 (G4–G7)
3. **사전등록 무결성**: prereg.json 해시를 자체 검증 (HARKing 자동 트레일, 차단 아님)
4. **비타협 정책**: PHI 행 비전송 · effect size+95%CI 강제 · Citation Grounding(논문)
5. **자체 동료검토**: 투고 전 적대적 self-review로 약점 사전 발견

## Phase 라우팅 결정 트리

```
입력 발화
  │
  ▼
[1] workspace/{project}/phase2_hypothesis/prereg.json 존재?
  ├─ NO  → 안내: 계획 하네스(prereg)가 필요. 사용자가 prereg를 직접 제공할 수도 있음.
  └─ YES → 다음 단계
  │
  ▼
[2] 키워드 분류
  ├─ "데이터", "검정 가능", "표본 크기", "검정력", "EDA", "결측"  → Phase 4 (data-inspector)
  ├─ "분석", "Cox", "회귀", "생존", "Kaplan-Meier", "Table 1"     → Phase 5 (statistician)
  ├─ "논문", "manuscript", "IMRaD", "투고", "draft", "초안"        → Phase 6 (manuscript-writer)
  ├─ "동료검토", "peer review", "투고 전 검토", "reviewer", "약점" → Phase 7 (peer-reviewer)
  ├─ "문헌", "가설", "연구계획서", "IRB"                           → 계획 하네스 안내 (범위 밖)
  └─ 모호                                                          → 명확화 질문
```

문헌·가설·IRB 관련 요청이 오면 **이 플러그인 범위 밖**임을 알리고 `clinical-research-planning` 플러그인 사용을 안내합니다.

---

## Phase 4: Data Inspector (검정 가능성)

사전등록 가설이 주어진 데이터로 검정 가능한지 평가하고 verdict(testable / partially testable / not testable)를 산출. data-inspect 스킬이 담당.

**비타협**: 행 단위(개별 환자) 데이터는 어떤 경우에도 LLM 컨텍스트로 전달되지 않음. LLM은 컬럼명·요약 통계·결측 패턴만 본다. 직접 식별자(실명·생년월일·주민번호)는 자동 마스킹.

진입은 IRB 무관. 자세한 절차·PHI 정책은 data-inspect/SKILL.md 참조.

## Phase 5: Statistician (통계 분석)

사전등록 계획대로 Table 1 · 1차 · 부수 · 민감도 분석 + 진단 + STROBE 점검. stat-analysis 스킬이 담당.

**비타협**: 모든 효과 추정치는 effect size + 95% CI 동반 (p-value 단독 보고 거절). 사전등록에 없는 분석은 자동 `exploratory` 분리 + BH-FDR.

> Phase 5 진입 시 IRB 게이트 점검 **없음** (분석 하네스는 IRB 무관). 사전등록 해시 검증만 수행하며, 드리프트는 차단 없이 경고 + 자동 로깅 (Soft 모델).

## Phase 6: Manuscript Writer (논문 초안)

Phase 4–5 + 계획 하네스 산출물을 통합해 IMRaD .docx 생성. manuscript-writer 스킬이 담당.

**비타협**: 모든 인용은 search_log.json의 PMID/DOI 또는 사용자 명시 입력만. Results 수치는 분석 결과에서만(LLM 재작성 금지). ICMJE AI disclosure 자동 생성, AI는 저자 아님.

## Phase 7: Peer Review (투고 전 자체 적대적 검토 — 신규)

투고 *전에* 가상 reviewer 패널이 자기 원고를 적대적으로 비판해 약점을 사전 발견. peer-review 스킬이 담당.

- 5개 렌즈(방법·통계 / 임상 의의·외적 타당도 / STROBE 보고 / 인과·편향 / 인용 근거)로 major·minor 코멘트 생성
- 심각도 순 이슈 목록 + 수정 체크리스트 + "투고 준비도" 평가
- **이것은 실제 학술지 동료심사가 아니라 *리허설*입니다.** 실제 심사 대응(rebuttal)은 본 하네스 범위 밖.

---

## 게이트 G4 — Feasibility Verdict 승인

Phase 4 종료 시 verdict + 자동 탐지 불가 4항목(선택편향·측정편향·교란·collider) 사용자 검토 후 4지선다:
1. 진행 (testable/partial) → Phase 5 + variable_mapping.json 확정
2. 대안 질문 채택 (not testable) → 사용자 직접 선택 → 계획 하네스 amendment
3. 데이터 보완 후 재시도
4. 중단

not testable이어도 명시적 informed-consent + 로깅으로 진행 가능(결과는 약한 근거로 명시). 자세한 내용 `references/phase_gates.md` G4 참조.

## 게이트 G5 — 분석 결과 승인

Phase 5 종료 시 사용자 검토 3항목(임상 해석 적절성 · 진단 플롯(PH 가정 등) · 민감도 일관성) + 다음 단계 선택(추가 분석 / Phase 6 / 종료 / amendment). **IRB 점검 없음.**

## 게이트 G6 — Manuscript Draft 검토

Phase 6 종료 시 8항목 검토(Introduction · STROBE 22 · effect size·CI · Discussion 임상 함의(사용자 직접 작성 권장) · Limitations 4항목 반영 · ICMJE disclosure · CRediT · 학술지 형식) 후 finalize / 수정 / Phase 5 복귀 / Phase 7(자체 동료검토) 선택.

## 게이트 G7 — 자체 동료검토 결과 검토 (신규)

Phase 7 종료 시 peer-reviewer 패널의 비판 보고서를 검토 후:
1. **수정 진행** → 지적된 major 이슈를 Phase 5(재분석) 또는 Phase 6(재집필)로 환원
2. **수용·반박 결정** → 각 코멘트에 대해 반영/반박(근거 동반) 결정 기록
3. **투고 준비 완료** → 분석 하네스 종료. 실제 학술지 투고는 사용자 직접
4. **추가 검토** → 다른 렌즈·더 엄격한 패널로 재실행

자세한 내용 `references/phase_gates.md` G7 참조.

---

## 사전등록 무결성 검증 (자체 — 독립성 보장)

분석 하네스는 계획 하네스의 prereg-lock 스킬에 의존하지 않습니다. stat-analysis가 자체 검증 유틸을 포함합니다:

```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/stat-analysis/scripts/prereg_check.py --project {project}
```

해시 불일치(드리프트)는 **차단하지 않고** 경고 + evolution_log에 PREREG_HASH_DRIFT 자동 기록 (Soft 모델). prereg.json이 없으면 confirmatory/exploratory 구분 없이 모든 분석이 exploratory로 처리됨을 사용자에게 안내.

## 비타협 정책 요약 (분석 하네스)

1. **PHI 행 비전송** — 개별 환자 row는 절대 LLM 컨텍스트 비전송 (data-inspect)
2. **effect size + 95% CI 강제** — p-value 단독 보고 거절 (stat-analysis)
3. **Citation Grounding** — 논문 인용은 search_log.json/사용자 입력 PMID·DOI만 (manuscript-writer, peer-review)

IRB·HARKing은 informed-consent + 자동 로깅 모델 (차단 아님).

## Evolution 로깅

모든 게이트 결정·자동 탐지·override는 `workspace/{project}/evolution_log.md`에 누적 (계획 하네스 로그에 이어서 기록).

## 테스트 시나리오

오케스트레이터 동작이 깨지지 않았는지 점검하는 기준 흐름입니다. 코드 수정 후 아래대로 동작하는지 확인하십시오.

**정상 흐름 (happy path):**
1. prereg.json이 있는 `workspace/{project}/`에서 "데이터 받았다, 분석 가능한지 봐줘" → Phase 4 진입
2. data-inspector가 verdict(testable) 산출 → G4 승인 → variable_mapping.json 확정
3. "분석 돌려줘" → Phase 5 통계(Table 1·1차·민감도), 모든 추정치 effect size + 95% CI 동반 → G5 승인
4. "논문 초안 써줘" → Phase 6 IMRaD .docx(STROBE 22항목·ICMJE disclosure) → G6 검토
5. "투고 전 검토해줘" → Phase 7 가상 reviewer 5개 렌즈 비판 → G7 수정/투고 준비 결정

**에러 흐름 (반드시 이렇게 동작해야 함):**
- **prereg.json 없음**: 계획 하네스 산출물 또는 사용자 직접 prereg가 필요함을 안내. 그래도 진행 시 **모든 분석이 exploratory로 처리**됨을 명시
- **verdict = not testable**: G4에서 차단하지 않되 4지선다(대안 질문 / 데이터 보완 / 중단 / 강행) 제시. 강행 시 informed-consent + 로깅 + "약한 근거" 명시
- **사전등록 해시 드리프트**: prereg.json이 바뀜 → **차단하지 않고** 경고 + evolution_log에 PREREG_HASH_DRIFT 자동 기록(Soft 모델)
- **p-value 단독 보고 요청**: "p값만 보여줘" → 거절(effect size + 95% CI 비타협)
- **범위 밖 요청**: "문헌 찾아줘" / "연구계획서 써줘" / "IRB" → 이 플러그인 범위 밖 안내 + `clinical-research-planning` 플러그인 사용 권고

## 참고 자료
- `references/phase_gates.md` (G4–G7)
- `references/STROBE_checklist.md`
- `references/citation_policy.md`
