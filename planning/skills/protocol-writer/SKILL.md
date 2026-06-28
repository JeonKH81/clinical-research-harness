---
name: protocol-writer
description: Phase 2의 잠긴 사전등록(prereg.json)을 IRB 제출용 한국어 연구계획서(.docx)로 자동 변환. 자체 결정론적 생성기(build_protocol.py)로 기관 표준 한국어 IRB 템플릿을 직접 렌더링하며(외부 시스템 스킬 비의존), 표본 수 자동 산출·STROBE/SPIRIT 자기검증·Citation Grounding 검증을 내장. Phase 3 전용. protocol-writer agent가 호출.
license: MIT
---

# Protocol-Writer Skill (자체 생성 + 자동 검증)

## 목적
잠긴 사전등록(prereg.json) + Phase 1 문헌 결과를 통합해 IRB 제출용 한국어 .docx 연구계획서를 **외부 시스템 스킬 의존 없이** 자체 생성하고, 생성물의 완성도·인용 무결성을 **자동 검증**합니다.

## v2 고도화 요약 (이전 wrapper 대비)
- **자체화**: `anthropic-skills:research-protocol-writer`(앱 내장 시스템 스킬) 위임을 제거. `scripts/build_protocol.py`가 python-docx만으로 동일 템플릿을 직접 렌더링 → 시스템 스킬 미설치 환경에서도 단독 동작.
- **표본 수 자동 산출**: `scripts/sample_size.py`가 9개 설계(생존·두비율·두평균·단일비율정밀도/진단정확도·McNemar·ANOVA·로지스틱·비열등성 비율/평균)를 scipy만으로 자체 산출 + IRB 문구 생성. 흔한 3종은 prereg에서 자동 삽입. 번들이라 외부 스킬 없이 동작하며, 범위 밖 설계는 선택적으로 `calc-sample-size` 위임(아래 참조).
- **자기검증 게이트**: `scripts/self_review.py`가 study_type에 따라 STROBE(관찰)/SPIRIT(시험) 핵심 항목을 PRESENT/PARTIAL/MISSING으로 점검, 필수 누락 시 NEEDS_WORK.
- **Citation Grounding 강제(코드)**: `scripts/verify_citations.py`가 모든 참고문헌·in-text [n]을 search_log.json과 대조, 미실재 시 exit 2(BLOCK).
- **질문 최소화**: `references/researcher_profile.example.json`로 PI/기관 메타를 재사용 — 프로젝트마다 책임연구자를 다시 묻지 않음.

## 트리거
- protocol-writer agent가 호출
- 사용자가 "연구계획서", "IRB 제출", "프로토콜 작성"을 직접 언급

## 입출력

### 입력
- `workspace/{project}/phase2_hypothesis/prereg.json` (잠긴 상태, SSOT)
- `workspace/{project}/phase1_lit/search_log.json` (Citation Grounding 출처)
- (선택) `workspace/{project}/phase1_lit/research_opportunities.md` (배경 prose 근거)
- (선택) `~/.clinical-research-harness/researcher_profile.json` 또는 프로젝트 profile (PI 메타 재사용)
- 에이전트가 작성하는 `narrative.json` (prose 오버레이 — 스키마: `references/narrative.schema.json`)

### 출력 (`workspace/{project}/phase3_protocol/`)
- `research_protocol.docx` — IRB 제출용 한국어 계획서
- `protocol_content.resolved.json` — 병합 결과(검증 입력)
- `irb_metadata.json` — IRB 추적 메타(linked_prereg_hash 포함)
- `self_review.md` — STROBE/SPIRIT 자기검증 결과
- `citation_audit.json` — 인용 무결성 검증 결과

## 절차

### Step 1. 사전등록 무결성 확인
```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/prereg-lock/scripts/lock.py verify --project {project}
```
실패 시 즉시 중단 (No work without identity).

### Step 2. narrative.json 작성 (에이전트의 유일한 창작 영역)
prereg의 구조 필드는 건드리지 않고, prose만 작성:
- `background` (2장, in-text [n] 인용 — search_log의 PMID 문헌만)
- `objectives`, `design_narrative`, `subjects.inclusion/exclusion`, `data_collection`, (해당 시) `ai_algorithm`
- `title_ko/en`, `study_period`, `references` (search_log에서)

스키마는 `references/narrative.schema.json` 참조. 구조 필드를 narrative에 중복 기입하면 무시됨(prereg 우선).

### Step 3. .docx 생성 (자체 렌더링)
```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/protocol-writer/scripts/build_protocol.py \
  --prereg   workspace/{project}/phase2_hypothesis/prereg.json \
  --narrative workspace/{project}/phase3_protocol/narrative.json \
  --refs     workspace/{project}/phase1_lit/search_log.json \
  --profile  ~/.clinical-research-harness/researcher_profile.json \
  --outdir   workspace/{project}/phase3_protocol \
  --auto-sample-size
```
→ `research_protocol.docx` + `protocol_content.resolved.json` + `irb_metadata.json` 생성.

### Step 4. 자동 검증 (게이트 G3 진입 전 필수)
```bash
# 4a. 인용 무결성 — exit 2면 차단, narrative.references 수정 후 재생성
python ${CLAUDE_PLUGIN_ROOT}/skills/protocol-writer/scripts/verify_citations.py \
  --resolved workspace/{project}/phase3_protocol/protocol_content.resolved.json \
  --refs     workspace/{project}/phase1_lit/search_log.json \
  > workspace/{project}/phase3_protocol/citation_audit.json

# 4b. 완성도 — NEEDS_WORK면 ❌ 항목 보완 후 재생성
python ${CLAUDE_PLUGIN_ROOT}/skills/protocol-writer/scripts/self_review.py \
  --resolved workspace/{project}/phase3_protocol/protocol_content.resolved.json \
  --out      workspace/{project}/phase3_protocol/self_review.md
```
두 검증 모두 통과(PASS / READY)해야 사용자 검토로 진행. 실패 시 해당 항목 보완 후 Step 3 재실행.

### Step 5. 사용자 검토 및 게이트 G3
self_review.md 요약과 함께 .docx를 제시. 4지선다로 irb_status 갱신:

| 선택 | irb_status | 기록 후 |
|---|---|---|
| 승인 + IRB 통과 | `approved` | IRB 번호·승인일 입력. 계획 하네스 종료, 분석 하네스로 인계 |
| 신속심사 통과 | `expedited` | IRB 번호 입력. 인계 |
| 면제(exempt/IRB 불필요) | `exempt` | 면제 사유 입력. 인계 |
| 제출됨/미제출 | `submitted`/`pending_submission` | 상태 기록. 분석은 IRB 무관·사용자 책임 |
| 수정 필요 | 변동 없음 | narrative/prereg 보완 후 재호출 |

## 표본 수 산출 — 번들 우선 + 선택적 위임 (이식성 보장)

`sample_size.py`는 harness에 **번들**돼 있어 medsci-skills 설치 여부와 무관하게 누구에게나 동작합니다(공개 배포 안전).

**번들로 자체 처리되는 설계** (scipy만 사용):
survival(log-rank/Cox), two-proportion, two-mean, precision-proportion(단일비율 CI·진단정확도 Buderer), mcnemar(짝지은 이진), anova(일원), logistic(Peduzzi EPV / Hsieh), ni-proportion, ni-mean(비열등성).

**번들 범위를 벗어나는 설계** (ICC/κ 일치도, TOST 동등성 등):
1. **`calc-sample-size` 스킬이 available-skills 목록에 있으면** 그것으로 산출 후 결과 문구를 `narrative.sample_size`에 주입.
2. **없으면** (= harness만 설치한 외부 사용자): ① 사용자가 표본수 문구를 `narrative.sample_size`에 직접 입력하도록 안내, 또는 ② "medsci-skills 설치 시 자동 지원" 안내.

> **비-의존 원칙**: `calc-sample-size`는 hard dependency가 **아님**. 에이전트는 호출 **전에** available-skills 목록으로 존재를 확인하고 분기한다(호출 실패에 의존하지 않음). 외부 스킬 부재로 protocol-writer가 깨지지 않는다.

## 핵심 정책

### 1. Single Source of Truth (코드로 강제)
가설·분석은 prereg.json이 유일 출처. `build_protocol.py`가 구조 필드를 prereg에서만 읽고 narrative의 중복 구조 필드는 무시 → 가설 이중 입력·드리프트 구조적 차단.

### 2. Citation Grounding (코드로 강제)
참고문헌은 search_log.json의 PMID/DOI 실재 항목만 허용. `verify_citations.py`가 미실재 인용·범위 초과 in-text [n]을 BLOCK. 자유 생성 인용 불가.

### 3. Pre-reg Hash Linkage
`irb_metadata.json`의 `linked_prereg_hash`에 prereg의 SHA-256을 기록 → protocol↔prereg 버전 추적(감사 트레일). prereg 변경 시 해시 불일치로 stale 감지.

### 4. 기록만, 분석 차단 없음
본 스킬은 IRB 상태를 **기록**만 함. 분석 하네스(`clinical-research-analysis`)는 IRB 무관 독립 실행이며 `irb_status`를 차단 조건으로 쓰지 않음. IRB 책임은 전적으로 사용자에게 있음. `irb_status`는 manuscript Methods 윤리 섹션 보고용.

## 실패 모드

| 시나리오 | 처리 |
|---|---|
| prereg.json 없이 Phase 3 진입 | 차단, Phase 2로 환원 |
| python-docx 미설치 | `pip install python-docx` 안내 후 중단 |
| Citation 환각(PMID 없는 인용) | verify_citations exit 2 → **BLOCK**, narrative.references 수정 요구 |
| in-text [n]이 references 범위 초과 | dangling_intext로 **BLOCK** |
| 필수 항목 누락 | self_review NEEDS_WORK → ❌ 항목 보완 후 재생성 |
| effect_size_assumption 부족(HR/p1·p2/delta·sd 없음) | 표본 수 자동산출 skip + 경고. 수동 sample_size 기입 |
| LLM이 prereg 외 구조 정보를 .docx에 주입 | build_protocol이 prereg만 읽으므로 구조적으로 무시 |
| prereg 변경 후 재호출 | 새 linked_prereg_hash 기록, 새 .docx 생성 |

## 한계 명시 (의도된)
- .docx 생성까지만 담당. **기관 IRB 시스템에 자동 제출하지 않음** — 사용자가 직접 제출.
- 기본 템플릿/윤리 문구는 일반적인 한국어 IRB 양식 기준. 기관별 차이는 `build_protocol.py`의 `render_ethics`·라벨·섹션 제목만 교체(구조 로직은 기관 독립). 상세는 `references/template_spec.md`.
- self_review는 **형식·완성도** 자동 점검이며 과학적 타당성·IRB 적격성을 보증하지 않음.
- IRB 면제 자격은 기관 정책에 따름 — 본 하네스가 판정하지 않음.
