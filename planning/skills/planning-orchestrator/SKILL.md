---
name: planning-orchestrator
description: 임상연구 "계획 하네스"의 진입점. Phase 0–3 (Intake → 문헌검색 → 가설 PICO 정제·사전등록 → IRB 연구계획서) 라우팅과 Human-in-the-loop 게이트 G0–G3를 강제한다. "임상연구 시작", "이 주제로 연구하고 싶다", "문헌 찾아줘", "가설 정리", "연구계획서", "IRB" 같은 자연어에서 자동 호출. 데이터 분석·논문은 별도 clinical-research-analysis 플러그인이 담당.
license: MIT
---

# Clinical Research — Planning Orchestrator

이 스킬은 **Clinical Research Harness의 계획 하네스(Planning)**의 진입점입니다. 연구의 *시작부터 IRB 제출용 연구계획서까지*(Phase 0–3)를 담당하며, 데이터를 보기 전 단계입니다.

> **두 하네스 구조**: 본 하네스는 두 플러그인으로 나뉩니다.
> - **계획 (이 플러그인)**: Phase 0–3 — Intake · 문헌 · 가설/사전등록 · IRB 연구계획서
> - **분석 (`clinical-research-analysis`)**: Phase 4–7 — 데이터 검정 · 통계분석 · 논문초안 · 투고 전 자체 동료검토
>
> 경계는 **IRB 승인 시점**입니다. 계획이 끝나고 IRB 승인/면제를 받은 뒤, 같은 `workspace/{project}/` 폴더에서 분석 하네스로 이어갑니다. 두 하네스는 이 공유 폴더와 `prereg.json`·`search_log.json`을 통해 연결됩니다.

## 핵심 책임

1. **요청 분류**: 자연어 입력을 Phase 0/1/2/3으로 라우팅
2. **게이트 검증**: 다음 Phase 진입 전 사용자 명시 승인 확인 (G0–G3)
3. **사전등록 무결성**: `prereg.json` 해시를 Phase 진입마다 검증
4. **위반 차단**: Citation 환각(비타협) 자동 차단, HARKing 자동 로깅
5. **핸드오프**: Phase 3 종료 후 분석 하네스로 인계 안내

## Phase 라우팅 결정 트리

```
입력 발화
  │
  ▼
[1] 현재 프로젝트가 있는가? (workspace/{project}/ 존재 확인)
  ├─ NO  → Phase 0 (Intake), 새 프로젝트 폴더 생성
  └─ YES → 다음 단계
  │
  ▼
[2] 키워드 분류
  ├─ "문헌", "검색", "gap", "선행연구", "replication", "validation" → Phase 1 (literature-scout)
  ├─ "가설", "PICO", "PECO", "research question"                  → Phase 2 (hypothesis-refiner → prereg-lock)
  ├─ "연구계획서", "IRB", "프로토콜", "BRIA"                       → Phase 3 (protocol-writer)
  ├─ "처음부터", "전체 진행"                                       → Phase 0부터 순차
  ├─ "데이터", "분석", "Cox", "생존", "Table 1", "논문", "draft"   → 분석 하네스 안내 (이 플러그인 범위 밖)
  ├─ "가설 바꾸자" (기록 후)                                       → amendment 절차 안내
  └─ 모호                                                          → 명확화 질문
```

데이터 분석·논문 관련 요청이 오면 **이 플러그인 범위 밖**임을 알리고 `clinical-research-analysis` 플러그인 사용을 안내합니다.

---

## Phase 0: Intake

### 작동 원칙 (5가지)

1. **No work without identity** — 프로젝트 이름·주제·환자군이 모두 채워지기 전에는 다른 Phase 진입을 차단한다. "그냥 분석부터"라 해도 Phase 0으로 환원.
2. **Workspace as single source of truth** — 모든 산출물은 `workspace/{project-name}/` 아래에만 생성한다.
3. **Ethics first, technique second** — G0 3항목 확인 전에는 어떤 외부 도구(PubMed 검색 등)도 호출하지 않는다.
4. **Idempotency** — 같은 프로젝트 이름 재호출 시 기존 폴더를 인식하고 덮어쓰지 않는다.
5. **Minimum information principle** — Phase 0에서 PHI(이름·주민번호·차트번호 등)를 절대 수집하지 않는다. "어떤 환자군인가"는 *기술적 정의*이지 *환자 명단*이 아니다.

### 구동 과정

```
[1] "새 연구 시작" 의도 감지
[2] 5항목 정보 수집 (모자라면 차례로 질문, 다 채워질 때까지 진행 보류)
    ├ 프로젝트 이름 (예: "PCI-MVD-2026")
    ├ 연구 주제 (자유 서술)
    ├ 대상 환자군 (기술적 정의)
    ├ 데이터 위치 (경로 또는 "아직 없음")
    └ 기존 가설 초안 (선택)
[3] 같은 이름 폴더 존재 확인 → 있으면 이어가기 안내(덮어쓰지 않음)
[4] 폴더 구조 생성 (아래)
[5] intake.md 생성 (5항목 정규화 메타데이터)
[6] evolution_log.md 첫 기록
[7] G0 게이트 — 3항목 명시 확인
[8] 모두 "예" → Phase 1 안내
```

### 생성 폴더 구조 (계획 + 분석 공용)

```
workspace/{project-name}/
  ├ input/                # 데이터 (PHI 포함 시 클라우드 동기화 제외)
  ├ phase1_lit/           # 계획 하네스
  ├ phase2_hypothesis/    # 계획 하네스
  ├ phase3_protocol/      # 계획 하네스
  ├ phase4_data/          # 분석 하네스
  ├ phase5_analysis/      # 분석 하네스
  ├ phase6_manuscript/    # 분석 하네스
  ├ phase7_review/        # 분석 하네스 (자체 동료검토)
  └ evolution_log.md      # 두 하네스 공통 누적 로그
```

계획 하네스는 phase1–3만 채우고, phase4–7은 분석 하네스가 채웁니다. (폴더는 미리 만들어 두어 핸드오프를 단순화)

### intake.md 템플릿

```markdown
# Intake — {project-name}
**작성일**: {ISO 8601}
**연구자**: {사용자 이름}

## 연구 주제
{자유 서술}

## 대상 환자군 (기술적 정의)
{예: 60세 이상 STEMI 환자 중 primary PCI 시행자, 2018–2024}

## 데이터 위치
- 경로: {파일 경로 또는 "아직 없음"}
- 형식: CSV / Parquet / Excel / 미정
- 클라우드 동기화 폴더 여부: { 예 / 아니오 }
- (예인 경우) PHI 업로드 위험 인지: { 예 / 아니오 / N/A (익명화 완료) }

## 기존 가설 초안 (선택)
{있으면 자유 서술, 없으면 "Phase 2에서 정제 예정"}

## G0 게이트 응답
- IRB 승인 범위 내: { 예 / 아니오 / 모름 }
- PHI 외부 전송 차단 정책 동의: { 예 / 아니오 }
- 학술적 책임 본인 귀속 인지: { 예 / 아니오 }
```

### 한계 명시
- IRB 시스템(BRIA 등) 자동 연동 없음 — 사용자 응답을 그대로 신뢰
- 데이터 PHI 포함 여부 자동 검사 없음 (분석 하네스 Phase 4의 역할)

## 게이트 G0 — IRB · 데이터 윤리 확인

다음 3항목을 사용자가 명시적으로 "예"라고 답해야 Phase 1 진행:

1. 본 데이터의 사용은 IRB 승인 범위 내에 있다.
2. 본 하네스의 PHI 외부 LLM API 전송 차단 정책에 동의한다.
3. 본 하네스의 산출물은 보조 자료이며, 최종 학술적 책임은 본인에게 있다.

실패 처리는 `references/phase_gates.md` G0 섹션 참조.

## 게이트 G1 — 연구 기회 선택

Phase 1 종료 시 literature-scout가 제시한 9가지 카테고리(A1–A4 gap, B1–B4 replication/validation, C1 update) 후보 중 하나 이상을 사용자가 선택. **자동 선택 금지**.

## 게이트 G2 — 사전등록 기록 (Soft 기록 모델)

Phase 2 종료 시 가설 후보를 확정하면 `prereg.json`을 SHA-256 해시로 기록:

> "이 가설과 분석 계획을 사전등록(prereg.json)으로 기록하시겠습니까? 기록 후 가설은 자유롭게 다듬을 수 있으며 변경 사실은 evolution_log에 자동 기록됩니다. 사전등록과 어긋나는 분석은 (분석 하네스에서) 자동으로 exploratory 라벨이 부여됩니다. 진짜 비가역 사전등록은 OSF·AsPredicted를 권고드립니다."

## 게이트 G3 — 연구계획서 검토 + IRB 상태 입력

Phase 3 종료 시 protocol-writer가 생성한 `research_protocol.docx`를 검토 후 `irb_metadata.json`에 IRB 상태 입력:

1. **승인** (`approved`) → IRB 번호·승인 일자 입력
2. **신속심사** (`expedited`) → IRB 번호 입력
3. **면제** (`exempt`) → 면제 사유 입력 (후향적 익명화 자료 등)
4. **제출됨/미제출** (`submitted`/`pending_submission`) → 분석 하네스 진입 시 사용자 책임으로 진행
5. **수정 필요** → 사용자가 .docx 직접 수정 후 재호출

> 본 계획 하네스는 IRB 상태를 *기록*만 합니다. 분석 하네스는 IRB 무관 독립 실행이며, IRB 책임은 전적으로 사용자에게 있습니다.

---

## 핸드오프 — 분석 하네스로 인계

Phase 3 종료(G3 통과) 후 사용자에게 안내:

> "계획 하네스가 완료되었습니다. 다음 산출물이 `workspace/{project}/`에 준비되었습니다:
> - `phase2_hypothesis/prereg.json` (사전등록 — 분석의 confirmatory/exploratory 기준)
> - `phase3_protocol/research_protocol.docx`, `irb_metadata.json`
> - `phase1_lit/search_log.json`, `research_opportunities.md` (논문 Introduction·References 근거)
>
> IRB 승인/면제를 받으신 뒤, **`clinical-research-analysis` 플러그인**으로 데이터 분석을 시작하십시오. 같은 프로젝트 폴더를 그대로 사용합니다."

## 사전등록 무결성 검증

각 Phase 진입 직전 prereg.json이 있으면 항상 검증:

```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/prereg-lock/scripts/lock.py verify --project {project}
```

해시 불일치(드리프트)는 **차단하지 않고** 경고 + evolution_log에 PREREG_HASH_DRIFT 자동 기록 (Soft 모델).

## Citation 환각 방지 (비타협)

literature-scout가 출력하는 모든 인용은 PMID/DOI를 동반해야 하며, 도구가 직접 반환했거나 사용자가 명시 입력한 것만 허용. 자유 생성 인용은 거절. 자세한 정책은 `references/citation_policy.md` 참조.

## Evolution 로깅

각 게이트 결정·자동 탐지 이슈·사용자 override는 `workspace/{project}/evolution_log.md`에 누적 기록.

## 참고 자료
- `references/phase_gates.md` (G0–G3)
- `references/citation_policy.md`
