# Clinical Research Harness — Repo Guide

이 저장소는 **Clinical Research Harness v2**입니다. 임상연구 보조 골격을 **두 개의 플러그인(하네스)**으로 제공하는 Claude Code 마켓플레이스입니다.

- **계획 하네스** (`planning/`, 플러그인명 `clinical-research-planning`): Phase 0–3 — Intake · 문헌 · 가설/사전등록 · IRB 연구계획서. 진입점 스킬 `planning-orchestrator`.
- **분석 하네스** (`analysis/`, 플러그인명 `clinical-research-analysis`): Phase 4–7 — 데이터 검정 · 통계분석 · 논문초안 · 투고 전 자체 동료검토. 진입점 스킬 `analysis-orchestrator`.

경계는 **IRB 승인 시점**이며, 두 하네스는 공유 `workspace/{project}/`와 `prereg.json`·`search_log.json`으로 연결됩니다. 자연어 라우팅·게이트 정책의 단일 출처는 각 orchestrator의 `SKILL.md`와 `references/phase_gates.md`입니다.

---

## 트리거 규칙 (요약)

- **계획 관련** 발화(연구 시작·문헌·가설·사전등록·연구계획서·IRB)는 `planning-orchestrator`가 처리 — Phase 0–3.
- **분석 관련** 발화(데이터·검정·Cox·생존분석·Table 1·논문초안·동료검토)는 `analysis-orchestrator`가 처리 — Phase 4–7.
- "가설 바꾸자"(기록 후)는 amendment 절차로 안내. 분류가 모호하면 명확화 질문, 범위 밖이면 다른 플러그인 사용을 안내합니다.

> **전체 키워드·Phase별 라우팅의 단일 출처는 각 orchestrator의 `SKILL.md`입니다.** 라우팅을 바꾸려면 이 요약이 아니라 해당 `SKILL.md`를 고치세요.

---

## 3대 비타협 정책 (우회 불가)

1. **Citation Grounding** — 모든 인용은 도구 반환 PMID/DOI 또는 사용자 명시 입력만. 자유 생성 인용 거절.
2. **PHI 행 비전송** — 개별 환자 row는 절대 LLM 컨텍스트 비전송. 직접 식별자(실명·생년월일·주민번호) 자동 마스킹. 차트번호·주소 등은 인지 확인(informed-consent).
3. **effect size + 95% CI 강제** — p-value 단독 보고 거절. Confirmatory=Bonferroni, Exploratory=BH-FDR.

그 외는 informed-consent + 자동 로깅 모델:
- **사전등록(HARKing)**: SHA-256 해시 기록 + 변경 자동 로깅(차단 아님, Soft 모델). 사전등록과 어긋나는 분석은 자동 `exploratory` 라벨.
- **IRB**: 계획 하네스는 상태를 *기록*만 함. **분석 하네스는 IRB 무관 독립 실행**이며 IRB 책임은 전적으로 사용자에게 있음.

---

## 게이트 (Human-in-the-loop)

계획·분석 각 Phase 종료 시 사용자 명시 승인 게이트(G0–G7)가 있으며, 승인 없이는 다음 Phase로 진행하지 않습니다.

> **각 게이트의 검증 항목·통과/실패 처리의 단일 출처는 각 플러그인의 `references/phase_gates.md`입니다**(계획 = G0–G3, 분석 = G4–G7). 게이트 정책을 바꾸려면 그 파일을 고치세요.

**범위 밖**: Phase 8(실제 심사 대응·재투고)은 본 하네스 밖 — 사용자 직접 처리.

---

## 워크스페이스 규칙

- 모든 산출물은 `workspace/{project-name}/` 아래 (두 하네스 공유)
- 데이터는 `workspace/{project}/input/`에 두되 **PHI 포함 시 클라우드 동기화 제외** (심볼릭 링크 권장)
- 사전등록: `phase2_hypothesis/prereg.json` (핸드오프 핵심)
- 연구계획서: `phase3_protocol/research_protocol.docx` + `irb_metadata.json`
- 분석 결과: `phase5_analysis/`
- 논문 초안: `phase6_manuscript/manuscript_draft.docx`
- 자체 동료검토: `phase7_review/review_report.md`
- 공통 로그: `workspace/{project}/evolution_log.md`

---

## 개발 메모

- 플러그인 레이아웃: 각 플러그인은 `<plugin>/.claude-plugin/plugin.json` + `<plugin>/skills/<skill>/SKILL.md` + `<plugin>/agents/*.md`. 스킬 내부 cross-skill 참조는 `${CLAUDE_PLUGIN_ROOT}/skills/...` 경로 사용.
- 분석 하네스는 계획 하네스에 의존하지 않음 — 사전등록 무결성 검증은 자체 `analysis/skills/stat-analysis/scripts/prereg_check.py` 사용.
- 설계 문서: `Clinical_Research_Harness_v1_0_Final.docx`

---

## 변경 이력

하네스 자체(에이전트·스킬·정책)의 변경을 기록합니다. (프로젝트별 분석 로그는 각 `workspace/{project}/evolution_log.md`에 별도 기록)

| 날짜 | 변경 내용 | 대상 | 사유 |
|---|---|---|---|
| 2026-06-14 | 오케스트레이터에 테스트 시나리오(정상+에러) 섹션 추가 | planning/analysis orchestrator SKILL.md | 회귀 점검 기준 부재 |
| 2026-06-14 | description에 후속·재작업 키워드 추가 | planning/analysis orchestrator | "다시 해줘" 재실행 요청 미트리거 방지 |
| 2026-06-14 | 전체 에이전트(7개) 모델 sonnet→opus 통일 | planning/analysis agents | 하네스 품질은 추론력에 직결 (harness 원칙) |
| 2026-06-14 | citation_policy 두 사본에 동기화 주의 표시 | 양 플러그인 references | 정책 드리프트 방지 |
| 2026-06-14 | CLAUDE.md 라우팅·게이트표를 포인터로 축약 | CLAUDE.md | 단일 출처 중복 제거 |
