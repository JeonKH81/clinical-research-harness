# Clinical Research Harness v2

> 임상연구자의 인지부담을 분산시키는 AI 보조 골격
> **두 개의 하네스(플러그인)**로 구성 — 연구의 흐름(계획 → 분석)에 맞춰 분리

**버전**: v2.0
**대상**: 후향적 관찰 코호트 (1차: PCI · 심혈관)
**실행 환경**: Claude Code / Claude Desktop App (Cowork mode)

---

## 두 하네스 구조

연구의 시점은 **IRB 승인**을 기준으로 자연스럽게 둘로 나뉩니다. 본 하네스도 이를 따라 두 플러그인으로 분리되어 있습니다.

| | **하네스 1 — 계획** (`clinical-research-planning`) | **하네스 2 — 분석·집필** (`clinical-research-analysis`) |
|---|---|---|
| 범위 | Phase 0–3 | Phase 4–7 |
| 단계 | Intake → 문헌검색 → 가설/사전등록 → IRB 연구계획서 | 데이터 검정 → 통계분석 → 논문초안 → 투고 전 자체 동료검토 |
| 게이트 | G0–G3 | G4–G7 |
| 시점 | 데이터를 보기 **전** | IRB 승인/면제 **후** |
| IRB | 상태를 *기록* | **무관 독립 실행** (책임은 사용자) |
| 산출물 | `prereg.json`, `research_protocol.docx`, `irb_metadata.json` | `feasibility_report`, `results`, `manuscript_draft.docx`, `review_report.md` |

두 하네스는 **같은 `workspace/{project}/` 폴더**를 공유하며, `prereg.json`·`search_log.json`을 핸드오프 산출물로 연결됩니다.

```
계획 하네스 (Phase 0–3)                 분석 하네스 (Phase 4–7)
─────────────────────────              ─────────────────────────
Phase 0  Intake          G0            Phase 4  Data Inspector      G4
Phase 1  Literature      G1            Phase 5  Statistician        G5
Phase 2  Hypothesis/     G2            Phase 6  Manuscript Writer   G6
         Pre-registration              Phase 7  Peer Reviewer       G7
Phase 3  Protocol Writer G3                     (투고 전 자체 적대적 검토)
   │                                       ▲
   └── prereg.json + search_log + irb_metadata ──┘
       (공유 workspace/{project}/)
```

---

## 설치 (Claude Code 마켓플레이스)

이 저장소는 두 플러그인을 담은 **마켓플레이스**입니다.

```bash
# 마켓플레이스 등록 (repo 루트)
/plugin marketplace add JeonKH81/clinical-research-harness

# 필요한 하네스 설치
/plugin install clinical-research-planning@clinical-research-harness
/plugin install clinical-research-analysis@clinical-research-harness
```

설치 후 스킬은 네임스페이스로 호출됩니다:
- `clinical-research-planning:planning-orchestrator`
- `clinical-research-analysis:analysis-orchestrator`

대개는 자연어로 시작하면 orchestrator가 자동 호출됩니다:

```
이 PCI 코호트로 다혈관 vs 단일혈관의 1년 MACE 비교 연구를 시작하고 싶다   → 계획 하네스
데이터 받았다. 사전등록한 가설로 분석 돌려줘                              → 분석 하네스
```

---

## 저장소 구조

```
clinical-research-harness/
├── .claude-plugin/marketplace.json     # 두 플러그인 등록
│
├── planning/                           # 하네스 1 (플러그인)
│   ├── .claude-plugin/plugin.json
│   ├── skills/
│   │   ├── planning-orchestrator/      # 진입점, Phase 0–3 라우팅, G0–G3
│   │   │   └── references/{phase_gates.md, citation_policy.md}
│   │   ├── lit-search/                 # Phase 1 (+ pubmed_query.py)
│   │   ├── prereg-lock/                # Phase 2 사전등록 (+ lock.py)
│   │   └── protocol-writer/            # Phase 3 IRB 연구계획서
│   └── agents/
│       ├── literature-scout.md
│       ├── hypothesis-refiner.md
│       └── protocol-writer.md
│
├── analysis/                           # 하네스 2 (플러그인)
│   ├── .claude-plugin/plugin.json
│   ├── skills/
│   │   ├── analysis-orchestrator/      # 진입점, Phase 4–7 라우팅, G4–G7
│   │   │   └── references/{phase_gates.md, STROBE_checklist.md, citation_policy.md}
│   │   ├── data-inspect/               # Phase 4 (+ eda.py)
│   │   ├── stat-analysis/              # Phase 5 (+ run_analysis.py, prereg_check.py)
│   │   ├── manuscript-writer/          # Phase 6 IMRaD 초안 (Discussion: Claude+Codex 협업 + discussion_collab.py)
│   │   └── peer-review/                # Phase 7 자체 동료검토 (신규)
│   └── agents/
│       ├── data-inspector.md
│       ├── statistician.md
│       ├── manuscript-writer.md
│       └── peer-reviewer.md            # 신규
│
└── workspace/                          # 프로젝트별 산출물 (두 하네스 공유)
    └── {project}/
        ├── input/                      # 데이터 (PHI 포함 시 동기화 제외)
        ├── phase1_lit/ … phase3_protocol/    # 계획 하네스
        ├── phase4_data/ … phase7_review/     # 분석 하네스
        └── evolution_log.md            # 두 하네스 공통 로그
```

---

## 3대 비타협 정책 (우회 불가)

1. **Citation Grounding** — 모든 인용은 도구가 반환한 PMID/DOI 또는 사용자 명시 입력만. 자유 생성 인용 거절. (계획: lit-search / 분석: manuscript·peer-review)
2. **PHI 행 비전송** — 개별 환자 row는 어떤 경우에도 LLM 컨텍스트로 전달되지 않음. 직접 식별자(실명·생년월일·주민번호) 자동 마스킹. (분석: data-inspect) 이는 Phase 6 Discussion의 Claude+Codex 협업에도 동일 적용 — Codex로는 집계 통계만 전송.
3. **effect size + 95% CI 강제** — p-value 단독 보고 거절. (분석: stat-analysis)

그 외 IRB·HARKing은 informed-consent + 자동 로깅 모델 (차단 아님). 특히 **분석 하네스는 IRB 무관 독립 실행**이며 IRB 책임은 전적으로 사용자에게 있습니다.

---

## ⚠️ PHI 데이터 처리 — 매우 중요

이 폴더는 Dropbox/iCloud 등 클라우드 동기화 폴더일 수 있습니다.
**환자 식별정보(PHI)가 포함된 데이터는 이 폴더 안에 두지 마십시오.**

권장 운용:
- **이 폴더**: 스킬 정의, 분석 코드, 사전등록 파일, 결과 표/그림 (PHI 미포함)
- **별도 로컬 폴더** (동기화 제외): 원본 환자 데이터

`workspace/{project}/input/data.csv`는 로컬 데이터에 대한 **심볼릭 링크**를 권장합니다:

```bash
ln -s ~/Research/clinical-data/PCI-MVD-2026/data.csv \
      "workspace/PCI-MVD-2026/input/data.csv"
```

`.gitignore`에 PHI 의심 파일을 사전 차단해 두었습니다.

---

## 범위 — 명시적 비포함

- **Phase 8 (Revision · 실제 심사 대응)**: 학술지 reviewer comment에 대한 rebuttal·재투고. Phase 7의 *자체* 동료검토(투고 전 리허설)와 달리, 실제 심사 대응은 본 하네스 범위 밖 — 사용자 직접 처리.
- "임상적 가치 판단"은 항상 사용자에게 위임 (LLM 약점 영역).

---

## 참고
- 설계 문서: `Clinical_Research_Harness_v1_0_Final.docx`
- 원본 하네스 개념: [jikime/harness-lab](https://github.com/jikime/harness-lab) (카카오 황민호 님 원본 [revfactory/harness](https://github.com/revfactory/harness) 기반)
- 보고 가이드: STROBE (관찰연구)
