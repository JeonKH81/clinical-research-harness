# Clinical Research Harness v1

> 임상연구자의 인지부담을 분산시키는 AI 보조 골격
> Phase 1–6 (문헌검색 → 가설 정제 → 연구계획서 → 데이터 검정 → 통계 분석 → manuscript draft)

**버전**: v1.0 (Draft)
**대상**: 후향적 관찰 코호트 (1차: PCI · 심혈관)
**실행 환경**: Claude Code / Claude Desktop App (Cowork mode)

---

## 빠른 시작

### 1. 첫 사용 (이 폴더가 워크스페이스로 이미 열려 있다면)

채팅창에 자연어로 시작하면 됩니다:

```
이 PCI 코호트로 다혈관 vs 단일혈관의 1년 MACE 비교 연구를 시작하고 싶다
```

Orchestrator가 자동으로 Phase 0(intake) → Phase 1(literature search)로 진행하며, 각 게이트에서 사용자 승인을 요청합니다.

### 2. 새 프로젝트 시작

```
/skill clinical-research-orchestrator
```

또는 자연어로:

```
새 임상연구 프로젝트를 시작하자, 주제는 ...
```

---

## 폴더 구조

```
Clinical Research Harness/
├── CLAUDE.md                          # 라우팅 규칙 + 강제 정책
├── README.md                          # 이 파일
├── Clinical_Research_Harness_v1_Design.docx   # 설계 문서
│
├── .claude/
│   ├── agents/                        # Sub-agent 정의
│   │   ├── literature-scout.md
│   │   ├── hypothesis-refiner.md
│   │   ├── protocol-writer.md
│   │   ├── data-inspector.md
│   │   ├── statistician.md
│   │   └── manuscript-writer.md
│   └── skills/                        # 스킬 정의
│       ├── clinical-research-orchestrator/
│       │   ├── SKILL.md               # 진입점, Phase 라우팅
│       │   └── references/
│       │       ├── STROBE_checklist.md
│       │       ├── phase_gates.md
│       │       └── citation_policy.md
│       ├── lit-search/                # Phase 1
│       ├── prereg-lock/               # Phase 2 (사전등록 잠금)
│       ├── protocol-writer/           # Phase 3 (IRB 연구계획서)
│       ├── data-inspect/              # Phase 4
│       └── stat-analysis/             # Phase 5
│
└── workspace/                         # 프로젝트별 산출물
    └── (프로젝트 폴더들)
        └── (예) PCI-MVD-2026/
            ├── input/                 # 데이터, 데이터 사전
            ├── phase1_lit/
            ├── phase2_hypothesis/
            │   └── prereg.json        # LOCKED
            ├── phase3_protocol/
            │   ├── research_protocol.docx
            │   └── irb_metadata.json
            ├── phase4_data/
            ├── phase5_analysis/
            ├── phase6_manuscript/
            │   ├── manuscript_draft.docx
            │   ├── references.bib
            │   ├── strobe_22_check.md
            │   └── ai_disclosure.md
            └── evolution_log.md
```

---

## ⚠️ PHI 데이터 처리 — 매우 중요

이 폴더는 Dropbox/iCloud 등 클라우드 동기화 폴더일 가능성이 높습니다.
**환자 식별정보(PHI)가 포함된 데이터는 이 폴더 안에 두지 마십시오.**

### 권장 운용

- **이 폴더**: 스킬 정의, 설계 문서, 분석 코드, 사전등록 파일, 결과 표/그림 (PHI 미포함)
- **별도 로컬 폴더** (예: `~/Research/clinical-data/`, 동기화 제외): 원본 환자 데이터

`workspace/{project}/input/data.csv`는 **로컬 폴더의 데이터에 대한 심볼릭 링크**로 두시는 것을 권장합니다:

```bash
ln -s ~/Research/clinical-data/PCI-MVD-2026/data.csv \
      "workspace/PCI-MVD-2026/input/data.csv"
```

`.gitignore`에 PHI 의심 파일을 사전 차단해 두었습니다.

---

## 사용 흐름 (예시)

```
[교수님] PCI 코호트로 다혈관 vs 단일혈관의 1년 MACE 비교 연구를 시작하고 싶다.

[하네스] Phase 0 — Intake
       연구 주제, 대상 환자군, 데이터 위치, IRB 승인 상태 확인 중...
       G0 게이트: 다음 3항목을 확인해 주십시오:
         1. 본 데이터 사용은 IRB 승인 범위 내입니까?
         2. PHI 외부 전송 차단 정책에 동의하십니까?
         3. 학술적 책임은 본인(연구자)에게 있음을 이해하십니까?

[교수님] 모두 예

[하네스] Phase 1 — Literature Scout
       PubMed에서 "primary PCI" AND "multivessel disease" AND "MACE"...
       총 247건, 최근 5년 systematic review 12건, RCT 6건...
       9가지 카테고리 연구 기회를 식별했습니다:
         A. 새 영역(Gap): A1-A4 (4건)
         B. 기존 연구 재검토: B1 Replication 1건, B2 Validation 2건,
                              B3 RWE 1건, B4 Subgroup 1건
         C. 업데이트: C1 (1건)
       G1 게이트: 어느 후보를 추구하시겠습니까?

[교수님] B1 — SYNTAX-II Trial을 분당서울대 PCI 코호트에서 재현

[하네스] Phase 2 — Hypothesis Refiner
       PECO 형식으로 가설 후보 3개를 제시합니다 [표 출력]
       G2 게이트: 가설 1번을 기록하시겠습니까? 기록 후 자유 변경 가능, 변경 사실은 evolution_log에 자동 기록됩니다.

[교수님] 잠가줘

[하네스] prereg.json 기록 완료 (SHA-256: a3f5c8..., 자유 변경 가능)
       Phase 3 — Protocol Writer
       잠긴 사전등록 + Phase 1 문헌을 IRB 연구계획서로 변환 중...
       research_protocol.docx 생성 완료
       G3 게이트: IRB 제출 상태를 알려주세요 (제출 예정/제출됨/승인됨/면제/중단)

[교수님] 면제 — 후향적 익명화 데이터, BRIA 면제 신청 예정

[하네스] irb_status=exempt 기록. Phase 4 — Data Inspector
       데이터 스키마 분석 중...
       (Phase 4·5 진행 후)

[하네스] Phase 6 — Manuscript Writer
       Phase 1–5 산출물 통합해 IMRaD draft 생성 중...
       manuscript_draft.docx 생성 완료
       STROBE 22항목 점검 완료 (누락 항목은 입력 요청)
       ICMJE AI disclosure 자동 생성
       G6 게이트: 검토 후 finalize 또는 수정 요청
```

📝 **v1.0 종료**: Phase 7(peer review)·Phase 8(revision)은 본 하네스 범위 밖. 사용자 직접 처리.

---

## v1.0 범위 — 명시적 비포함

다음은 본 하네스 범위 **밖**으로 명시적 결정. 사용자가 직접 또는 외부 도구로 처리:

- **Phase 7 (Peer Review)**: 학술지 동료심사 또는 사용자 자체 동료 검토
- **Phase 8 (Revision · response-to-reviewer)**: 동료심사 후 응답·재투고

이 두 단계는 *학술적 가치 판단·동료와의 협력*이 핵심이라, 자동화하기보다 사용자가 본인 학술 책임으로 처리하는 것이 합리적이라는 결정.

---

## 문제가 발생하면

- 인용 환각이 의심되면: 모든 인용에 PMID/DOI가 있는지 확인. 없으면 `lit-search` 재호출.
- 가설을 바꾸고 싶을 때 (Phase 2 이후): 자유롭게 변경 가능 (evolution_log 자동 기록). 정식 변경 사유 기록을 원하면 "가설 amendment 신청" 입력.
- 분석 결과가 사전등록과 다른 경우: 자동으로 `exploratory` 섹션으로 분리됩니다.
- PHI 노출이 의심되면: 즉시 `evolution_log.md`에 기록하고 데이터 파일을 안전한 위치로 이동.

## Evidence 등급 안내

본 하네스는 LLM이 잘하는 영역(절차적 작업, 코드 실행, 형식 준수)과 약한 영역(임상적 가치 판단, 선택편향 탐지, 인과추론)을 구분하여 설계되었습니다.
약한 영역은 모두 Human-in-the-loop 게이트로 사용자에게 위임됩니다.

자세한 근거는 `Clinical_Research_Harness_v1_Design.docx` 부록 C 참고.
