# Phase Gates — Human-in-the-loop 체크포인트 정책

본 문서는 Clinical Research Harness **계획 하네스**의 4개 게이트(G0–G3) 각각에 대한 검증 항목, 사용자 응답 형식, 통과/실패 처리를 정의합니다.

> 분석 하네스(Phase 4–7, 게이트 G4–G7)는 별도 `clinical-research-analysis` 플러그인의 `references/phase_gates.md`를 참조하십시오.

---

## G0 — IRB · 데이터 윤리 확인

**위치**: Phase 0 (Intake) 종료 시
**책임 스킬**: planning-orchestrator
**유형**: 명시적 다항 확인 (3항목)
**Phase 0 작동 원칙**: 본 게이트 통과 전에는 외부 도구(PubMed, 데이터 로딩, LLM 추론) 호출 금지 — 자세한 작동 원칙은 orchestrator SKILL.md의 "Phase 0 작동 원칙" 섹션 참조.

### 검증 항목

다음 3항목 모두 사용자가 명시적으로 "예"로 답해야 통과:

| # | 질문 | 응답 처리 |
|---|---|---|
| 1 | 본 데이터의 사용은 IRB 승인 범위 내에 있는가? | 예 → 진행 / 아니오 → 차단 + IRB 신청 권고 / 모름 → 보류 |
| 2 | 본 하네스의 PHI 외부 LLM API 전송 차단 정책에 동의하는가? | 예 → 진행 / 아니오 → 차단 (기술적 정책 동의 없으면 데이터 처리 불가) |
| 3 | 본 하네스의 산출물은 보조 자료이며 최종 학술적 책임이 본인에게 있음을 이해하는가? | 예 → 진행 / 아니오 → 차단 |

### 실패 처리

- 어느 한 항목이라도 "아니오"면 Phase 1 진입 차단
- "1번이 미정"인 경우: IRB 신청 권고 + 진행 보류 (`irb_pending` 상태로 evolution_log에 기록)
- 모든 결정은 evolution_log.md에 기록 (학술적 무결성 트레일)

### Phase 0 단계의 추가 실패 모드 (G0 외)

| 시나리오 | 기대 동작 |
|---|---|
| 같은 프로젝트 이름으로 재호출 | 기존 폴더 인식 → 덮어쓰지 않음, 어느 Phase부터 이어갈지 안내 |
| 사용자가 정보를 모호하게 줌 ("심장 연구") | 명확화 질문, 5항목이 다 채워질 때까지 G0 진행 안 함 |
| 데이터 위치가 Dropbox/iCloud 동기화 폴더 | 위험 안내 → 사용자 인지 확인 (자동 차단 안 함, v1은 informed-consent 모델) |
| 데이터 컬럼명에 PHI 의심 단어 포함 | 경고만 (정밀 검사는 Phase 4에서) |
| 사용자가 G0 우회 요청 ("그냥 진행해") | 거절, 무결성 정책 안내, evolution_log에 시도 기록 |

### G0 통과 후 산출물

| 산출물 | 위치 | 의미 |
|---|---|---|
| `intake.md` | `workspace/{project}/intake.md` | 5항목 + G0 응답 기록 |
| `evolution_log.md` | `workspace/{project}/evolution_log.md` | Phase 0 진입 시점, G0 응답, 다음 Phase 안내 |

### 의도된 한계

- 기관 IRB 시스템에 자동 연동 없음 — 사용자 응답을 신뢰하는 *소셜 컨트롤*. 항목 1·3은 약속에 의존, 항목 2(PHI 차단)만 코드 레벨 강제 가능.
- 데이터 파일의 PHI 포함 여부 자동 검사는 Phase 4의 역할
- **v1 정책 철학**: 위험 자동 탐지 시 *차단*이 아닌 *informed consent*. 사용자에게 위험을 명시하고 동의를 받으면 진행, 동의 사실은 evolution_log에 기록. 자동 차단·강제 거절은 상품화 단계(v2 이후)에서 추가 검토.

---

## G1 — 연구 기회 선택 (Research Opportunity)

**위치**: Phase 1 (Literature Scout) 종료 시
**책임 스킬**: planning-orchestrator (literature-scout가 후보 제시)
**유형**: 단일 또는 다중 선택 (또는 사용자 직접 입력)

### 9가지 후보 카테고리

| 그룹 | ID | 유형 | 설명 |
|---|---|---|---|
| A. 새 영역 (Gap) | A1 | Population gap | 특정 환자군 검증 부재 |
| | A2 | Intervention gap | head-to-head 부재 |
| | A3 | Outcome gap | hard endpoint 부재 |
| | A4 | Methodological gap | 단일기관·소표본만 있음 |
| B. 기존 연구 재검토 | B1 | Replication study | landmark RCT를 본인 코호트로 재현 |
| | B2 | External validation | 예측 모델·위험 점수 외부 검증 |
| | B3 | Real-world evidence | RCT 결과의 실세계 일반화 검증 |
| | B4 | Subgroup deep-dive | 기존 연구 내 하위군 추가 분석 |
| C. 업데이트 | C1 | Updated analysis | 가이드라인·기술 변화 후 재평가 |

**Phase 1 작동 원칙**: lit-search/SKILL.md의 "작동 원칙 5가지" 참조 (Tool-grounded, Reproducibility, Structure over volume, Opportunities as candidates, Recency × Quality balance).

### 검증 항목
사용자가 다음 중 하나를 명시적으로 응답:
- 제시된 후보 중 하나 또는 다중 선택 (예: "B1", "A1+B1")
- 직접 작성한 연구 기회 기술 (PMID/DOI 근거 동반 권고) (단, PMID/DOI 근거 동반 권고)

### 자동 거절 조건 (비타협)
- **Citation Grounding 정책**: PMID/DOI 근거가 전혀 없는 gap은 거절. 이 부분은 informed-consent로 풀지 않음.

### informed-consent 처리 항목
다음은 자동 거절이 아닌 *경고 + 사용자 인지 확인* 으로 처리:
- 사용자가 "임상적 중요성"에 대한 자기 판단 없이 진행 시도 → 가치 판단을 사용자가 한다는 사실 재안내, 동의 시 진행 (evolution_log 기록)
- 사용자가 영어 외 문헌으로 보강하고 싶다고 하면 → v1 미지원 안내 + 사용자가 PMID/DOI 직접 입력 시 검증 후 사용

### 실패 처리
- 모든 후보가 부적절하면 → literature-scout 재호출 (다른 검색 전략, 다른 MeSH 용어)
- 사용자가 결정 보류 시 → 게이트 대기 상태 유지 (Phase 2 진입 차단)
- 가짜 PMID 입력 시 → post-hoc resolve로 자동 거절

### 의도된 한계
- "임상적 중요성" 가치 판단은 LLM 영역 밖 — 사용자 검토에 의존
- PubMed 비등재 문헌(KMBASE 등) v1 미지원

---

## G2 — 사전등록 기록 (Soft recording)

**위치**: Phase 2 (Hypothesis Refiner) 종료 시
**책임 스킬**: prereg-lock
**유형**: 명시적 기록 명령 (informed-consent 모델, 시스템 차원 잠금 아님)
**Phase 2 작동 원칙**: hypothesis-refiner.md + prereg-lock/SKILL.md의 "작동 원칙 5가지" 각각 참조.

**v1 정책 (Soft 기록 모델)**: prereg.json은 SHA-256 해시와 함께 *기록*되되 chmod 444 강제는 하지 않음. 변경 시 evolution_log에 자동 기록되며 Phase 5 진입 시 차단도 안 함 (informed-consent). Citation Grounding(Phase 1)만 비타협, HARKing 방지는 사용자 책임 + 자동 로깅으로 위임.

### 잠금 전 필수 입력 (모두 채워져 있어야 잠금 진행)

- [x] 가설 (PICO/PECO 형식)
- [x] 1차 결과변수 정의 + 측정 시점
- [x] 효과 크기 가정 (HR/OR/AR + α + power)
- [x] 1차 분석 방법 (예: Cox PH with IPTW)
- [x] 공변량 목록
- [x] 민감도 분석 계획
- [x] 다중비교 보정 방법
- [x] 난수 시드

하나라도 누락이면 잠금 거절 + 누락 항목 안내 + Phase 2로 복귀.

### 검증 항목 (사용자 응답)

```
다음 가설과 분석 계획을 사전등록(prereg.json)으로 기록하시겠습니까?

[hypothesis 요약]
[analysis_plan 요약]
[effect_size_assumption 요약]

잠금 후:
- 가설은 자유롭게 다듬을 수 있으며, 변경 사실은 evolution_log에 자동 기록됩니다.
- 사전등록과 어긋나는 분석은 자동으로 'exploratory' 라벨이 부여됩니다.
- 정식 변경 사유 기록을 원하시면 amendment 명령을 사용하실 수 있습니다 (선택).
- 진짜 비가역 사전등록은 OSF·AsPredicted 같은 외부 서비스를 권고드립니다.

기록하시겠습니까? (예 / 아니오 / 수정)
```

### 통과 시 동작 (lock.py 호출)

1. prereg.json 생성 + SHA-256 해시 (canonical JSON form)
2. 파일 권한 일반 유지 (chmod 444 강제 안 함)
3. evolution_log.md에 PREREG_RECORDED 이벤트 기록 + 해시
4. Phase 3 (protocol-writer) 진입 안내

### 실패 처리

| 응답 | 동작 |
|---|---|
| "아니오" | Phase 2로 복귀, 잠금 미실행 |
| "수정" | hypothesis-refiner 재호출 |
| 누락 항목 있음 | 잠금 거절 + 누락 항목 안내 |
| 모호한 응답 | 재질문 |

### 변경 처리 — 두 가지 경로

**(A) 자유 변경 (기본)**: prereg.json을 직접 수정하거나 hypothesis-refiner를 다시 호출. 변경 사실은 evolution_log에 PREREG_HASH_DRIFT로 자동 기록됨. 차단 없음.

**(B) 정식 amendment (선택)**: 정식 변경 사유 기록을 원하면 lock.py amend 명령 사용:

1. 사용자 변경 요청 → Orchestrator 차단
2. HARKing 위험 명시적 경고
3. 변경 사유 자유서술 입력 (빈 문자열 거절)
4. lock.py amend 호출
5. 새 prereg.json 생성 (version 증가) + 새 해시
6. amendment_log에 변경 시점·이전 해시·사유 영구 기록
7. 기존 prereg는 prereg_v{N}.json으로 보관 (영구)
8. Phase 5 진입 시 statistician가 amendment_log를 분석 보고서에 자동 노출

**중요**: amendment는 *선택* 절차. 자유 변경도 허용되며 자동 로깅으로 학술 무결성 트레일이 유지됨. 정식 사유가 필요한 경우(예: IRB 변경 신청 동반)에만 amendment 사용 권고.

### 의도된 한계

- 본 기록은 *자동 감사 트레일*이지 *비가역 사전등록*이 아님. 사용자가 prereg.json을 직접 편집해도 차단되지 않음 (Soft 모델). 다만 verify 시 해시 드리프트 경고 + evolution_log에 PREREG_HASH_DRIFT로 자동 기록됨.
- 진짜 비가역 사전등록 원하면 OSF (osf.io), AsPredicted, ClinicalTrials.gov 같은 외부 timestamping 서비스 사용 권고. prereg.json 해시를 외부에 함께 등록하면 학술적 신뢰도 최대화.
- HARKing 방지는 *연구자 본인의 학술 약속* 영역. 본 하네스는 그 약속을 회고적으로 검증할 자료(evolution_log)를 자동 생성할 뿐.


---

## G3 — 연구계획서 검토 + IRB 상태 입력

**위치**: Phase 3 (Protocol Writer) 종료 시
**책임 스킬**: protocol-writer (anthropic-skills:research-protocol-writer wrapper)
**유형**: 4지선다 + 메타데이터 입력

### 검증 항목

생성된 `research_protocol.docx`를 사용자가 검토 후 다음 정보를 `irb_metadata.json`에 기록:

| 선택 | irb_status | 추가 입력 |
|---|---|---|
| 승인 + IRB 통과 | `approved` | IRB 번호, 승인 일자 |
| 신속심사 통과 | `expedited` | IRB 번호, 신속심사 사유 |
| 면제 (후향적 익명화 등) | `exempt` | 면제 사유 (자유서술) |
| 제출됨 (심사 중) | `submitted` | 제출 일자 |
| 작성 완료, 미제출 | `pending_submission` | (없음) |
| 수정 필요 | (변동 없음) | 수정 사유 (사용자가 .docx 직접 수정 후 G3 재진입) |

### IRB 정책 — 계획 하네스는 *기록만*

계획 하네스의 G3는 IRB 상태를 `irb_metadata.json`에 **기록**할 뿐, 후속 분석을 차단하지 않습니다.

- **분석 하네스(`clinical-research-analysis`)는 IRB 무관 독립 실행**입니다 — `irb_status`를 분석 진입 차단·경고 조건으로 사용하지 않습니다.
- **IRB 책임은 전적으로 사용자(연구자)에게 있습니다.** 본 하네스는 IRB 적격성을 판정하지 않습니다.
- 철학: 후향적 익명화 자료의 IRB 면제, 외부 협력 전 사전 분석 등 합법 시나리오가 다양하고, IRB 적격성 판단은 기관·연구자 영역이므로 일률 차단은 부적절합니다.
- IRB 승인 후 prereg 변경 시 IRB 변경 신청도 동반되어야 함 (이중 트레일).

### prereg ↔ protocol 해시 연동

- `irb_metadata.linked_prereg_hash`는 G2에서 기록된 prereg.json의 SHA-256와 일치해야 한다.
- prereg가 변경되어 해시 드리프트가 발생하면 기존 protocol을 자동으로 stale로 표시하고 G3 재진행 권고 (차단은 안 함, Soft 모델).
- IRB 승인 후 prereg 변경 시 IRB 변경 신청도 동반되어야 함 (이중 트레일).

### 한계 명시

- 본 게이트는 기관 IRB 시스템에 자동 연동되지 않습니다 — IRB 번호·승인 여부는 사용자 입력에 의존.
- IRB 면제 자격 판정은 본 하네스가 수행하지 않습니다 — 기관 IRB 정책에 따름.

> **핸드오프**: G3 통과 후 계획 하네스는 종료됩니다. 데이터 분석(Phase 4–7)은 `clinical-research-analysis` 플러그인이 같은 `workspace/{project}/` 폴더를 이어받아 수행합니다. 분석 하네스는 IRB 무관 독립 실행입니다.

---

## 게이트 공통 정책

### 모든 게이트에 적용

- 사용자 응답은 명시적이어야 함 ("아마", "그럴 것 같다" 등은 재질문)
- 모든 게이트 결정은 evolution_log에 기록
- 게이트 우회 시도(예: 직접 prereg.json 편집) 자동 탐지 시 alert

### 게이트 우회 탐지

- prereg.json 해시 불일치
- 잠긴 파일의 mtime 변경
- amendment_log 미경유 변경

### 우회 발견 시
1. 분석 즉시 중단
2. 사용자에게 alert
3. evolution_log에 기록 (학술적 무결성을 위해 영구 기록)
