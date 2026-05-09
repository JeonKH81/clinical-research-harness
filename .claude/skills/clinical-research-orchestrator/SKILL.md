---
name: clinical-research-orchestrator
description: 임상연구 자연어 요청의 진입점. Phase 0–4 라우팅, Human-in-the-loop 게이트(G0–G5) 검증, 사전등록 무결성 확인. 후향 코호트 연구를 안전하게 단계별로 진행. "임상연구", "PCI 코호트", "이런 연구를 시작하고 싶다", "분석 도와줘" 같은 자연어 요청에서 자동 호출.
license: MIT
---

# Clinical Research Orchestrator

이 스킬은 **Clinical Research Harness v1**의 진입점입니다. 사용자의 자연어 요청을 적절한 Phase로 라우팅하고, 각 Phase 사이의 Human-in-the-loop 게이트를 강제합니다.

## 핵심 책임

1. **요청 분류**: 자연어 입력을 Phase 1/2/3/4 또는 Phase 0(처음부터)로 라우팅
2. **게이트 검증**: 다음 Phase 진입 전 사용자 승인 확인
3. **사전등록 무결성**: prereg.json 해시를 매 Phase마다 검증
4. **위반 차단**: HARKing, citation 환각, p-hacking 시도 자동 차단

## Phase 라우팅 결정 트리

사용자 입력을 받으면 다음 순서로 분류합니다:

```
입력 발화
  │
  ▼
[1] 현재 프로젝트가 있는가? (workspace/{project}/ 존재 확인)
  ├─ NO → Phase 0 (Intake)으로 진입, 새 프로젝트 폴더 생성
  └─ YES → 다음 단계
  │
  ▼
[2] 입력의 키워드 분류
  ├─ "문헌", "검색", "gap", "선행연구",         → Phase 1 (literature-scout)
  │   "replication", "validation", "내 데이터로 검증"
  ├─ "가설", "PICO", "PECO", "research question" → Phase 2 (hypothesis-refiner)
  ├─ "연구계획서", "IRB", "프로토콜", "BRIA"     → Phase 3 (protocol-writer)
  ├─ "데이터 검정", "표본 크기", "검정력", "EDA" → Phase 4 (data-inspector)
  ├─ "분석", "Cox", "회귀", "생존", "Table 1"    → Phase 5 (statistician)
  ├─ "처음부터", "전체 진행"                     → Phase 0부터 순차
  ├─ "가설 바꾸자" (Phase 2 잠금 후)             → Amendment 절차 안내
  └─ 모호                                          → 명확화 질문
```

## Phase 0: Intake

### 작동 원칙 (5가지)

1. **No work without identity** — 프로젝트 이름·주제·환자군 정보가 모두 채워질 때까지 다른 Phase 진입을 차단한다. 사용자가 "그냥 분석부터" 또는 "처음부터 다 알아서"라고 해도 Phase 0으로 환원한다.

2. **Workspace as single source of truth** — 모든 산출물은 `workspace/{project-name}/` 아래에만 생성한다. 임시 위치(/tmp 등)나 다른 폴더로 흩어지면 학술적 추적성이 무너진다.

3. **Ethics first, technique second** — G0 3항목 확인이 끝나기 전에는 어떤 외부 도구도 호출하지 않는다 (PubMed 검색, 데이터 로딩, 통계 분석 모두 금지). 사용자의 명시적 "예" 응답이 모든 후속 작업의 전제 조건이다.

4. **Idempotency (멱등성)** — 같은 프로젝트 이름으로 재호출 시 기존 폴더를 인식하고 **덮어쓰지 않는다**. 잠긴 prereg.json, irb_metadata.json 등이 이미 있으면 그 위치를 인식해 적절한 Phase로 이어간다.

5. **Minimum information principle** — Phase 0에서 PHI(이름·주민번호·차트번호 등)를 절대 수집하지 않는다. "어떤 환자군인가"는 *기술적 정의*(예: ≥60세 STEMI 환자 중 primary PCI 시행자)이지 *환자 명단*이 아니다.

### 구동 과정 (단계별 흐름)

```
[1] 사용자 발화 의도 감지 ("새 연구 시작" 분류)
        ↓
[2] 5항목 정보 수집 (모자라면 차례로 질문, 모두 채워질 때까지 진행 보류)
    ├── 프로젝트 이름 (예: "PCI-MVD-2026")
    ├── 연구 주제 (자유 서술)
    ├── 대상 환자군 (기술적 정의)
    ├── 데이터 위치 (CSV/Parquet 경로 또는 "아직 없음")
    └── 기존 가설 초안 (선택)
        ↓
[3] 같은 이름의 프로젝트 폴더 존재 여부 확인
    ├── 이미 있음 → 어느 Phase까지 진행됐는지 점검 후 이어가기 안내, 덮어쓰지 않음
    └── 없음 → [4]로
        ↓
[4] 폴더 구조 생성
    workspace/{project-name}/
      ├── input/
      ├── phase1_lit/
      ├── phase2_hypothesis/
      ├── phase3_protocol/
      ├── phase4_data/
      ├── phase5_analysis/
      └── evolution_log.md
        ↓
[5] intake.md 생성 (5항목 정규화된 메타데이터, 아래 템플릿 참조)
        ↓
[6] evolution_log.md 첫 기록 ("Phase 0 진입, intake.md 생성")
        ↓
[7] G0 게이트 — 3항목 명시적 확인
        ↓
[8] 모두 "예" → Phase 1 안내 (사용자가 다른 Phase 선택도 가능)
    어느 한 항목 거절/모름 → 차단 + evolution_log 기록
```

### 출력 명세

| 산출물 | 위치 | 비고 |
|---|---|---|
| 프로젝트 폴더 구조 | `workspace/{project}/` | 6개 하위 폴더 |
| intake.md | `workspace/{project}/intake.md` | 정규화된 5항목 메타데이터 |
| evolution_log.md | `workspace/{project}/evolution_log.md` | Phase 0 진입 + G0 응답 기록 |

### intake.md 템플릿

```markdown
# Intake — {project-name}

**작성일**: {ISO 8601}
**연구자**: {사용자 이름}

## 연구 주제
{자유 서술}

## 대상 환자군 (기술적 정의)
{예: 60세 이상 STEMI 환자 중 primary PCI 시행자, 2018–2024년 기간}

## 데이터 위치
- 경로: {파일 경로 또는 "아직 없음"}
- 형식: CSV / Parquet / Excel / 미정
- (선택) 데이터 사전 위치: {경로}
- 클라우드 동기화 폴더 여부: { 예 / 아니오 }
- (예인 경우) PHI 클라우드 업로드 위험 인지함: { 예 / 아니오 / N/A (익명화 완료 데이터) }

## 기존 가설 초안 (선택)
{있으면 자유 서술, 없으면 "Phase 2에서 정제 예정"}

## G0 게이트 응답
- IRB 승인 범위 내: { 예 / 아니오 / 모름 }
- PHI 외부 전송 차단 정책 동의: { 예 / 아니오 }
- 학술적 책임 본인 귀속 인지: { 예 / 아니오 }
```

### 실패 모드 (시뮬레이션 시 점검 항목)

| 시나리오 | 기대 동작 |
|---|---|
| 같은 프로젝트 이름으로 재호출 | 기존 폴더 인식 → 덮어쓰지 않음, 어느 Phase부터 이어갈지 안내 |
| 사용자가 정보를 모호하게 줌 ("심장 연구") | 명확화 질문, 5항목이 다 채워질 때까지 G0 진행 안 함 |
| 데이터 위치가 Dropbox/iCloud 동기화 폴더 | 위험 안내 (PHI가 클라우드로 업로드됨) → 사용자 인지 여부 확인 → 인지하면 진행, evolution_log에 기록 |
| 데이터 컬럼명에 PHI 의심 단어(name, mrn 등) 포함 | 본 단계에서는 경고만, 실제 처리는 Phase 4 |
| 사용자가 G0 항목 1에 "모름" | Phase 1 차단, 사유를 evolution_log에 기록, IRB 신청 권고 |
| 사용자가 G0 우회 요청 ("그냥 진행해") | 거절, 무결성 정책 안내, evolution_log에 시도 기록 |

### 한계 명시

- IRB 시스템(분당서울대 BRIA 등)에 자동 연동 없음 — 사용자 응답을 그대로 신뢰
- 데이터 파일의 PHI 포함 여부 자동 검사 없음 (Phase 4의 data-inspector 역할)
- 동시 협업 시나리오(두 명이 같은 프로젝트 작업) v1 범위 밖

## 게이트 G0 — IRB · 데이터 윤리 확인

다음 3항목을 사용자가 명시적으로 확인해야 다음 Phase 진행:

1. 본 데이터의 사용은 IRB 승인 범위 내에 있다.
2. 본 하네스의 PHI 외부 전송 차단 정책에 동의한다.
3. 본 하네스의 산출물은 보조 자료이며, 최종 학술적 책임은 본인에게 있다.

각 항목에 대해 사용자가 명시적으로 "예"라고 답해야 다음 단계로 진행합니다. 자세한 실패 처리는 `references/phase_gates.md` G0 섹션 참조.

## 게이트 G1 — Gap 선택

Phase 1 종료 시 literature-scout가 제시한 9가지 카테고리(A1-A4 gap, B1-B4 replication/validation, C1 update) 후보 중 하나 이상을 사용자가 선택합니다.
**자동 선택 금지**.

## 게이트 G2 — 사전등록 잠금 (LOCK · 비가역)

Phase 2 종료 시 hypothesis-refiner가 제시한 가설 후보 중 하나를 사용자가 확정하면, prereg.json을 SHA-256 해시로 잠급니다.

다음을 사용자에게 명시적으로 확인:
> "이 가설과 분석 계획을 사전등록(prereg.json)으로 잠그시겠습니까? 잠금 후 변경은 amendment 절차가 필요하며 변경 사유와 시점이 영구 기록됩니다."

## 게이트 G3 — 연구계획서 검토 + IRB 상태 입력

Phase 3 종료 시 protocol-writer가 생성한 `research_protocol.docx`를 사용자가 검토 후 다음 4가지 선택:

1. **승인 + IRB 제출 완료** → IRB 번호와 승인 일자 입력 (`irb_status: approved`)
2. **수정 필요** → 사용자가 .docx 직접 수정 후 재호출
3. **면제** → 면제 사유 입력 (`irb_status: exempt`, 후향적 익명화 자료 등)
4. **중단** → Phase 4 진입 차단

`irb_metadata.json`에 사용자 입력이 영구 기록되며, Phase 5(Statistician)는 `irb_status`가 `approved`/`exempt`/`expedited` 중 하나일 때만 진행됩니다.

## 게이트 G4 — Feasibility Verdict 승인

Phase 4 종료 시 data-inspector의 verdict를 사용자가 검토하고 다음 중 선택:
1. 진행 (testable)
2. 대안 질문 채택 (not testable, 사용자가 직접 선택)
3. 데이터 보완 후 재시도
4. 중단

## 게이트 G5 — 분석 결과 승인

Phase 5 종료 시 사용자가 다음 검토:
1. 임상적 해석 적절성
2. 진단 플롯 (PH 가정, calibration 등)
3. 민감도 분석 일관성
4. 다음 단계 (추가 분석 / v2로 / 종료)

## 사전등록 무결성 검증 (Phase 5 진입 시)

Phase 5 진입 직전 항상 실행:

```bash
python .claude/skills/prereg-lock/scripts/lock.py --verify --project {project}
```

해시 불일치 시:
- 분석 중단
- evolution_log.md에 기록
- 사용자에게 amendment 절차 안내

## HARKing 차단 (Phase 2 잠금 이후 가설 변경 요청)

사용자가 잠금 후 "가설 바꾸자" 요청 시:

```
1. 현재 prereg.json 출력
2. 변경 요청 사유를 사용자에게 질문
3. amendment_log에 다음 기록:
   - 변경 시점 (timestamp)
   - 변경 전 가설 해시
   - 변경 사유 (사용자 입력)
   - 변경 후 가설
4. 새 prereg.json 생성, 이전 버전은 prereg_v{N}.json으로 보관
5. Phase 5 결과는 amendment 이전/이후를 명시적으로 분리 라벨링
```

## IRB 차단 정책 (Phase 5 진입 전)

Phase 5 진입 직전 항상 `phase3_protocol/irb_metadata.json`을 읽어 `irb_status`를 확인:

```python
# Pseudocode
irb_status = irb_metadata.get("irb_status")
if irb_status not in ("approved", "exempt", "expedited"):
    BLOCK("IRB 미승인/미면제 상태에서 분석 진행은 차단됩니다")
    OPTION_OVERRIDE(reason_required=True)  # 명시적 override + evolution_log 기록
```

`pending_submission` 또는 `submitted` 상태에서 사용자가 명시적 override를 요청하면, override 사유와 시점이 evolution_log에 영구 기록됩니다 (학술적 무결성 트레일).

## Citation 환각 방지

literature-scout 또는 manuscript-writer(v2)가 출력하는 모든 인용은 다음 검증:

```python
# Pseudocode
for citation in output_citations:
    if citation.pmid:
        verify_pmid(citation.pmid)  # PubMed resolve
    elif citation.doi:
        verify_doi(citation.doi)    # Crossref resolve
    else:
        REJECT(citation)  # 자유생성 인용 차단
```

## Evolution 로깅

각 게이트 결정, 자동 탐지된 이슈, 사용자 override는 `workspace/{project}/evolution_log.md`에 누적 기록.

## 한계 명시

- 본 Orchestrator는 v1에서 Phase 1–4만 라우팅합니다. Phase 5–7(논문 작성·peer review·수정)은 v2.
- "임상적 가치 판단"은 항상 사용자에게 위임됩니다.
- 본 스킬은 ICMJE 가이드라인 및 STROBE를 참조하나, 학술지별 정책은 별도 확인 필요.

## 참고 자료

- `references/STROBE_checklist.md`
- `references/phase_gates.md`
- `references/citation_policy.md`
