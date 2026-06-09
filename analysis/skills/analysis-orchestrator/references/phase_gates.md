# Phase Gates (분석 하네스) — Human-in-the-loop 체크포인트 정책

본 문서는 Clinical Research Harness **분석·집필 하네스**의 4개 게이트(G4–G7) 각각에 대한 검증 항목, 사용자 응답 형식, 통과/실패 처리를 정의합니다.

> 계획 하네스(Phase 0–3, 게이트 G0–G3)는 별도 `clinical-research-planning` 플러그인의 `references/phase_gates.md`를 참조하십시오.

> **IRB 정책**: 본 분석 하네스는 **IRB 상태와 무관하게 동작**합니다. 어떤 게이트도 `irb_status`를 분석 진입 차단·경고 조건으로 사용하지 않습니다. IRB 책임은 전적으로 사용자에게 있습니다. (구 v1의 Phase 5 IRB 게이트는 제거됨)

---

## G4 — Feasibility Verdict 승인

**위치**: Phase 4 (Data Inspector) 종료 시
**책임 스킬**: analysis-orchestrator (data-inspector가 verdict 산출)
**유형**: 4지선다 + 사용자 검토 4항목
**Phase 4 작동 원칙**: data-inspect/SKILL.md의 "작동 원칙 5가지" 참조 (PHI Local-only 비타협, Auto-detection vs human review separation, Verdict as recommendation 등).

### 검증 항목 1 — verdict 응답 (4지선다)

| 선택 | 의미 |
|---|---|
| 진행 (verdict=testable 또는 partial) | Phase 5 진입 + variable_mapping.json 확정 |
| 대안 질문 채택 (verdict=not testable) | data-inspector가 제안한 후보 질문 중 사용자 선택 → 계획 하네스 prereg amendment |
| 데이터 보완 후 재시도 | 데이터 추가 추출 (예: 결측 변수) |
| 중단 | 프로젝트 보류 |

**not testable이어도 사용자가 명시적으로 진행을 요청하면 informed-consent로 진행 가능** (단, 결과는 약한 근거임을 명시 + evolution_log 기록).

### 검증 항목 2 — 자동 탐지 불가 영역 사용자 검토 (필수 4항목)

| 항목 | 자동 탐지 불가 이유 | 응답 |
|---|---|---|
| 선택 편향 (selection bias) | referral pattern, 등록 기준의 비기록 편향 — 데이터 외 정보 필요 | 있음/없음/모름 |
| 측정 편향 (information bias) | 결과 평가의 비맹검 — 임상 컨텍스트 필요 | 있음/없음/모름 |
| 교란 누락 (unmeasured confounding) | 데이터에 없는 변수 (예: 흡연력, SES) — 도메인 지식 필요 | 있음/없음/모름 |
| Collider 위험 (M-bias) | DAG 기반 인과 구조 — 도메인 지식 필요 | 있음/없음/모름 |

"있음" 또는 "모름" 응답 → Phase 6 Limitations 섹션에 자동 기록.

### 통과 시 동작
- "진행" → Phase 5 진입 + variable_mapping.json + 사용자 검토 응답 확정
- "대안 질문 채택" → 계획 하네스의 prereg amendment 절차 (Soft 모델, 자유 변경)

> prereg.json이 없으면(사용자가 계획 하네스를 거치지 않은 경우) Phase 4는 prereg 없이도 EDA·검정력 점검을 수행할 수 있으나, 변수 매핑은 사용자 확인에 더 의존한다.

---

## G5 — 분석 결과 승인

**위치**: Phase 5 (Statistician) 종료 시 (1차 분석 후)
**책임 스킬**: analysis-orchestrator (statistician가 결과 산출)
**유형**: 3항목 검토 + 4지선다
**Phase 5 작동 원칙**: stat-analysis/SKILL.md의 "작동 원칙 5가지" 참조 (Pre-reg as analysis source, Confirmatory/Exploratory auto-separation, Effect size + 95% CI 비타협, Reproducibility by seed, Diagnostics mandatory).

### 사전 점검 (Phase 5 진입 시) — IRB 게이트 없음

- **사전등록 해시 검증만** 수행: `prereg_check.py` (분석 하네스 자체 유틸). 드리프트 시 차단 없이 경고 + evolution_log에 PREREG_HASH_DRIFT 기록 (Soft 모델).
- **IRB 점검 없음**: 분석 하네스는 IRB 무관 독립 실행. (구 v1의 irb_status 차단/경고 게이트 제거)
- prereg.json 부재 시: 모든 분석이 exploratory로 처리됨을 사용자에게 안내.

### 사용자 검토 필수 3항목

| 항목 | 점검 내용 |
|---|---|
| 임상적 해석 적절성 | effect size의 임상적 의미 (예: HR 1.30이 임상적으로 의미 있는 차이인가). 자동 생성된 해석 단락 검토 |
| 진단 플롯 | PH 가정 위반(Schoenfeld p<0.05), calibration, ROC, residuals. 위반 시 대안 모델(stratified Cox, time-varying coefficient, AFT) 제안 검토 |
| 민감도 분석 일관성 | Complete-case vs MI vs IPTW/PSM 결과의 robustness. 한 분석에서만 유의하면 limitation 명시 |

### 다음 단계 4지선다

| 선택 | 동작 |
|---|---|
| 추가 분석 요청 | Phase 5 재실행 또는 exploratory 추가 (BH-FDR 자동 적용) |
| Phase 6 진행 | 논문 초안 작성 |
| Amendment 절차 | 분석 계획 수정 필요 시 계획 하네스 prereg amendment (Soft 모델) |
| 종료 | 결과만 활용 |

---

## G6 — Manuscript Draft 검토

**위치**: Phase 6 (Manuscript Writer) 종료 시
**책임 스킬**: analysis-orchestrator (manuscript-writer가 .docx 생성)
**유형**: 8개 검토 항목 + 4지선다
**Phase 6 작동 원칙**: manuscript-writer/SKILL.md 참조 (Wrapper, All sections grounded, Citation Grounding 비타협, STROBE 22항목 자동, ICMJE AI disclosure).

### 검토 필수 8항목
1. Introduction의 임상 배경 적절성
2. Methods의 STROBE 22항목 충족 (누락 시 사용자 입력)
3. Results의 effect size · 95% CI 정확성
4. **Discussion 임상적 함의 — 사용자 직접 작성·재작성 권장 영역**
5. Limitations에 Phase 4 사용자 검토 4항목(선택편향·측정편향·교란·collider) 반영
6. ICMJE AI disclosure 동의
7. 저자 기여(CRediT) 정확성 — AI는 저자 아님
8. 학술지 후보별 형식 요구 반영

### 다음 단계 4지선다

| 선택 | 동작 |
|---|---|
| Phase 7 (자체 동료검토) 진행 | 투고 전 적대적 self-review 실행 (권장) |
| 수정 요청 | manuscript-writer 재호출 |
| Phase 5로 복귀 | 추가 분석 필요 시 |
| Finalize (검토 생략) | 자체 검토 없이 종료 (비권장) |

---

## G7 — 자체 동료검토 결과 검토 (신규)

**위치**: Phase 7 (Peer Reviewer) 종료 시
**책임 스킬**: analysis-orchestrator (peer-reviewer가 비판 보고서 생성)
**유형**: 보고서 검토 + 4지선다
**Phase 7 작동 원칙**: peer-review/SKILL.md 참조 (적대적 기본값, 근거 기반 비판, Citation Grounding 비타협, 건설적 종결, 리허설 명시).

### 검토 내용
- 5개 렌즈(R1 방법·통계 / R2 임상의의·외적타당도 / R3 STROBE 보고 / R4 인과·편향 / R5 인용근거)의 major/minor 코멘트
- 심각도 순 종합 + 투고 준비도(ready / minor / major revision 위험) 평가
- 수정 체크리스트 (각 항목에 담당 Phase 표시)

### 다음 단계 4지선다

| 선택 | 동작 |
|---|---|
| 수정 진행 | major 이슈를 Phase 5(재분석) 또는 Phase 6(재집필)로 환원 |
| 수용·반박 결정 | 각 코멘트에 반영/반박(근거 동반) 결정 기록 (evolution_log) |
| 투고 준비 완료 | 분석 하네스 종료 — 실제 학술지 투고는 사용자 직접 |
| 추가 검토 | 다른 렌즈·더 엄격한 패널로 재실행 |

### 의도된 한계
- **리허설이지 실제 동료심사가 아님** — 분야 전문성·주관적 선호 완전 재현 불가
- **투고 후 실제 reviewer 대응(rebuttal)·재투고는 본 하네스 범위 밖** — 사용자 직접 처리
- reviewer 코멘트가 모두 타당한 것은 아님 — 수용/반박은 사용자(저자) 판단
- 임상적 가치 판단은 LLM 약점 영역 — 사용자 검토 필수

---

## 게이트 공통 정책

### 모든 게이트에 적용
- 사용자 응답은 명시적이어야 함 ("아마", "그럴 것 같다" 등은 재질문)
- 모든 게이트 결정은 evolution_log에 기록
- 게이트 우회 시도(예: 직접 prereg.json 편집) 자동 탐지 시 alert

### 게이트 우회 탐지
- prereg.json 해시 불일치 (prereg_check.py)
- amendment_log 미경유 변경

### 우회 발견 시
1. 경고 출력 (Soft 모델 — 차단 아님)
2. 사용자에게 alert + 인지 확인
3. evolution_log에 기록 (학술적 무결성을 위해 영구 기록)
4. 진행 시 최종 산출물(분석 보고서·manuscript)에 amendment/drift 트레일 자동 노출
