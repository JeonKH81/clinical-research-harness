---
name: manuscript-writer
description: 계획 하네스 산출물(prereg·문헌)과 Phase 4–5 분석 결과를 통합해 IMRaD 구조의 학술지 투고용 manuscript draft .docx를 자동 생성. anthropic-skills:docx 시스템 스킬을 wrapper로 활용. STROBE 22항목 자동 충족 + ICMJE AI disclosure 자동 생성. Phase 6 전용 (다음은 Phase 7 자체 동료검토). manuscript-writer agent가 호출.
license: MIT
---

# Manuscript-Writer Skill

## 목적
계획 하네스 산출물(prereg, search_log, IRB 메타데이터)과 분석 하네스 Phase 4–5 산출물(분석 결과, STROBE 점검표)을 통합하여 학술지 투고용 manuscript draft .docx를 자동 생성한다. 이후 Phase 7(투고 전 자체 동료검토)로 이어진다.

## 트리거
- manuscript-writer agent가 호출
- 사용자가 "논문 초안", "manuscript", "IMRaD", "투고", "draft", "작성"을 직접 언급

---

## 작동 원칙 (5가지)

### 1. Wrapper, not duplicate (래퍼)
`anthropic-skills:docx` 시스템 스킬을 호출하여 .docx를 생성한다. 자체 docx 빌드 로직 없음. Phase 3의 protocol-writer와 동일한 패턴.

### 2. All sections grounded (모든 섹션 근거 기반)
LLM이 자유 생성하는 영역을 최소화:
- **Introduction**: search_log의 PMID/DOI 인용 + research_opportunities의 gap 진술 그대로
- **Methods**: prereg.json + irb_metadata + variable_mapping (필드 매핑)
- **Results**: Phase 5 위임 스킬 결과(표·HR/OR+CI) + corrected_pvalues.json (수치는 LLM이 다시 쓰지 않음)
- **References**: search_log + 사용자 명시 PMID만
- **Discussion·Limitations**: 일부 자유 서술 허용하되 사용자 검토 필수. **Discussion 초안은 Claude+Codex 이중 저자 협업으로 생성**(아래 전용 섹션) — Codex 부재 시 Claude 단독

### 3. Citation Grounding 계승 (비타협)
모든 인용은 search_log.json의 PMID/DOI 또는 사용자 명시 입력만. 자유 생성 인용 거절. Phase 1과 동일.

### 4. STROBE 22항목 자동 충족 (관찰연구)
Phase 5의 strobe_checklist.md를 manuscript에 매핑. 누락 항목 (예: Funding, Generalisability) 명시 표시 + 사용자 입력 요구.

### 5. ICMJE AI disclosure 자동 생성
- AI 사용 사실을 Methods 또는 Acknowledgements에 명시 (ICMJE 2023 권고)
- **사용한 AI 모두 명시** — Claude (Anthropic) 전 단계 + Codex (OpenAI)가 Discussion 협업에 사용된 경우 함께 disclosure (Codex 사용 시에만)
- AI는 저자가 아님 — 저자 목록은 사용자 입력만
- evolution_log 요약을 disclosure 보충 자료로 첨부 (선택)

---

## 구동 과정 (8단계)

```
[1] prereg + analysis 무결성 점검 (prereg_check.py, 드리프트 시 informed-consent)
        ↓
[2] 사용자 추가 메타데이터 수집
    - 저자 목록 + 소속 + Corresponding Author + CRediT 기여
    - 학술지 후보 + 형식 요구 (word count, 헤더 등)
    - 연구비, Keywords 5개
        ↓
[3] anthropic-skills:docx 호출로 IMRaD 골격 생성
    Introduction → Methods → Results → Discussion → References
        ↓
[4] 섹션별 자동 채움 (모두 grounded)
    Introduction: search_log 인용 + research_opportunities gap
    Methods: prereg + irb_metadata + variable_mapping
    Results: Phase 5 위임 스킬 결과 + corrected_pvalues.json (수치 그대로)
    Discussion: ★ Claude+Codex 이중 저자 협업 (아래 전용 섹션) → discussion_final.md
    References: search_log + 사용자 PMID
        ↓
[5] STROBE 22항목 점검표 첨부 + 누락 항목 사용자 입력 요구
        ↓
[6] ICMJE AI disclosure 자동 생성 (ai_disclosure.md → manuscript에 삽입)
        ↓
[7] Citation 후처리 검증 — verify_citations.py (manuscript 텍스트/references를 esummary·Crossref로 resolve + search_log 대조)
        ↓
[8] G6 게이트 — 사용자 검토 (Discussion 임상 함의·STROBE 누락·저자 기여 등)
```

---

## Discussion 이중 저자 협업 (Claude + Codex)

Discussion 섹션은 LLM의 약점 영역(임상 가치 판단)이므로, **두 독립 AI(Claude·Codex)가 각자 초안을 쓰고 서로 교차 검토**하여 약점을 상호 보완한 뒤 Claude가 최종본을 종합한다. Codex가 없으면 자동으로 Claude 단독으로 마무리한다.

### 흐름

```
[0] probe        codex 사용 가능? (discussion_collab.py probe)
                  ├─ 불가 → 단독 모드로 분기 ([A2][B1][B2] 생략)
                  └─ 가능 → 협업 모드
[패킷] Claude가 grounded 입력 패킷 작성 → discussion/discussion_packet.md
        (주요 결과 effect size+CI · 허용 인용 PMID/DOI 목록 · gap · Limitations 4항목)
        ↓
[A] 독립 초안 (동일 패킷)
    A1 Claude 작성        → discussion/discussion_claude_v1.md   (agent)
    A2 Codex 작성         → discussion/discussion_codex_v1.md    (codex-draft)
        ↓
[B] 교차 검토 (서로 바꿔서)
    B1 Claude가 codex_v1 검토 → discussion/review_claude_on_codex.md  (agent)
    B2 Codex가 claude_v1 검토 → discussion/review_codex_on_claude.md  (codex-review)
        ↓
[C] 종합 (Claude)
    4개 산출물(두 초안 + 두 검토) → discussion/discussion_final.md
    + 채택/기각 사유 기록        → discussion/discussion_merge_notes.md
        ↓
    discussion_final.md → manuscript .docx 의 Discussion 으로 삽입
```

### Codex 측 호출 (결정론적 헬퍼)

```bash
# 가용성 (exit 0=가능, 1=불가). --no-exec 는 바이너리만 빠르게 확인(인증 미확인)
python ${CLAUDE_PLUGIN_ROOT}/skills/manuscript-writer/scripts/discussion_collab.py probe

# A2: Codex 초안
python ${CLAUDE_PLUGIN_ROOT}/skills/manuscript-writer/scripts/discussion_collab.py codex-draft \
  --packet  workspace/{project}/phase6_manuscript/discussion/discussion_packet.md \
  --out     workspace/{project}/phase6_manuscript/discussion/discussion_codex_v1.md

# B2: Codex 교차 검토 (Claude 초안을 검토)
python ${CLAUDE_PLUGIN_ROOT}/skills/manuscript-writer/scripts/discussion_collab.py codex-review \
  --draft   workspace/{project}/phase6_manuscript/discussion/discussion_claude_v1.md \
  --packet  workspace/{project}/phase6_manuscript/discussion/discussion_packet.md \
  --out     workspace/{project}/phase6_manuscript/discussion/review_codex_on_claude.md
```

### 정책 (두 저자 공통)
- **Citation Grounding 비타협**: 두 저자 모두 패킷의 허용 인용 목록 밖 인용 금지. discussion_final.md도 최종적으로 verify_citations.py를 통과해야 함.
- **PHI 비전송 비타협**: 패킷에는 집계 통계만 담는다 (개별 환자 row·직접 식별자 금지). Codex 호출은 이 패킷을 OpenAI로 전송하므로, 패킷 작성 시 PHI 부재를 재확인.
- **2차 vendor 고지**: Codex 사용 시 grounded 집계 내용이 **OpenAI에 전송**됨 → ai_disclosure.md에 Claude와 함께 Codex(OpenAI) 명시 (아래 disclosure).
- **관찰연구 한계**: 두 저자 프롬프트에 인과 과대해석 금지·effect size+CI 유지 규칙이 주입됨.
- **임상 가치 판단은 여전히 사용자**: 이중 AI는 *더 나은 초안*을 만들 뿐. discussion_final.md도 G6에서 사용자 직접 검토·재작성 권장 영역으로 유지.

### Fallback (Codex 미가용)
probe가 exit 1(미설치/미인증/런타임 실패)이면 [A2][B1][B2]를 생략하고 Claude가 단독으로 discussion_final.md를 작성한다. `discussion_collab_log.json`에 `mode: "claude_solo"`와 사유를 기록하고 evolution_log에 `DISCUSSION_CODEX_UNAVAILABLE`를 남긴다. **이 경우 disclosure에는 Codex를 명시하지 않는다.**

---

## 출력 명세

| 산출물 | 위치 | 의미 |
|---|---|---|
| manuscript_draft.docx | `phase6_manuscript/manuscript_draft.docx` | IMRaD 초안 |
| references.bib | `phase6_manuscript/references.bib` | BibTeX 참고문헌 |
| strobe_22_check.md | `phase6_manuscript/strobe_22_check.md` | STROBE 22항목 점검표 |
| ai_disclosure.md | `phase6_manuscript/ai_disclosure.md` | ICMJE AI 사용 명시 (협업 시 Codex 포함) |
| citation_check.json | `phase6_manuscript/citation_check.json` | verify_citations.py 인용 검증 결과 |
| discussion/ | `phase6_manuscript/discussion/` | 이중 저자 협업 산출물 (packet·두 초안·두 검토·final·merge_notes·collab_log) |

---

## 입력 → manuscript 섹션 매핑

| 입력 자료 | manuscript 섹션 |
|---|---|
| `research_opportunities.md`의 선택된 카테고리 + 근거 PMID | Introduction (gap 진술) |
| `search_log.json`의 high-impact 논문 (인용 수 정렬) | Introduction (배경) |
| `prereg.hypothesis.design` | Methods 1. 연구 설계 |
| `prereg.hypothesis.population` | Methods 2. 대상자 |
| `variable_mapping.json` | Methods 3–4. 변수 정의 |
| `prereg.analysis_plan.primary_method` | Methods 5. 통계 방법 |
| `prereg.analysis_plan.sensitivity` | Methods 5.1. 민감도 분석 |
| `irb_metadata` (irb_status, irb_number) | Methods 6. 윤리 |
| `prereg.data_provenance` | Methods 7. 자료 출처 |
| clinical-table1 출력 (Table 1) | Results 1. Baseline |
| survival-analysis / logistic 결과 (primary) + corrected_pvalues.json | Results 2. Primary outcome |
| 위임 스킬 결과 (secondary) | Results 3. Secondary outcomes |
| 위임 스킬 민감도 결과 | Results 4. Sensitivity |
| 위임 스킬 진단 (Schoenfeld·calibration 등) | Results 5. Diagnostics |
| Phase 4 `feasibility_report.md`의 사용자 검토 4항목 | Discussion → Limitations |
| `search_log.json` 모든 인용 | References |
| evolution_log.md 요약 | ai_disclosure.md |

---

## 실패 모드 (Citation Grounding + 무결성 비타협)

| 시나리오 | 처리 |
|---|---|
| Phase 1–5 산출물 누락 | 차단, 누락 Phase로 환원 |
| LLM이 자유 생성 인용 시도 | **차단 (Citation Grounding 비타협)** |
| LLM이 prereg 외 분석 결과 자유 생성 | **차단** — Results 수치는 위임 스킬 결과·corrected_pvalues.json에서만 |
| Discussion에서 환각 의심 (인용 없는 임상 주장) | 경고 + 사용자 검토 강제 + LLM 작성 영역 명시 |
| Codex 미가용 (미설치/미인증/타임아웃) | 차단 아님 — Claude 단독 모드로 fallback + evolution_log 기록 |
| Codex 초안이 패킷 밖 인용 생성 | 종합 단계에서 제거 + discussion_final.md는 verify_citations.py 통과 필수 |
| ICMJE AI disclosure 누락 | 차단, 자동 생성 강제 |
| AI를 저자 목록에 포함 시도 | 차단 (ICMJE 정책 위반) |
| 사용자가 STROBE 누락 항목 입력 거부 | 경고 + manuscript에 ⚠️ 표시 + evolution_log 기록 |
| prereg/data 해시 드리프트 | 경고 + manuscript에 amendment 트레일 자동 노출 |

---

## 게이트 G6 — Manuscript 검토

생성된 .docx를 사용자에게 검토 요청 (다음 항목 모두):

1. Introduction의 임상 배경 적절성
2. Methods의 STROBE 22항목 충족 (누락 시 입력)
3. Results의 effect size · 95% CI 정확성
4. **Discussion 임상적 함의 — 사용자 직접 작성·재작성 권장 영역**
5. Limitations에 Phase 4 사용자 검토 4항목(선택편향·측정편향·교란·collider) 반영 여부
6. ICMJE AI disclosure 동의
7. 저자 기여 (CRediT 분류) 정확성
8. 학술지 후보별 형식 요구 (word count, 그림 형식) 반영

### 통과 시 동작
- 사용자가 검토 완료를 명시 → manuscript draft 확정
- evolution_log에 PHASE_6_COMPLETE 기록
- **Phase 7(투고 전 자체 적대적 동료검토) 진입 권장** — peer-review 스킬로 약점을 사전 점검 후 투고
- 실제 학술지 투고·심사 대응(Phase 8 revision)은 본 하네스 범위 밖

### 실패 처리
- 사용자가 수정 요청 → manuscript-writer 재호출
- STROBE 누락 항목 입력 거부 → 경고 + 그래도 finalize 가능 (informed-consent)

---

## 한계 명시 (의도된)

- **Phase 7(투고 전 자체 동료검토)은 분석 하네스에 포함**: manuscript draft 후 peer-review 스킬로 약점 사전 점검. 단 이는 *리허설*이며, 실제 학술지 심사 대응·재투고(Phase 8 revision)는 본 하네스 범위 밖 — 사용자가 직접 또는 외부 도구로 처리
- **Discussion의 임상적 함의는 자동 생성하되 사용자 직접 작성·재작성을 권장**. LLM의 임상 가치 판단은 약점 영역
- 학술지별 형식 차이는 일부만 반영. 제출 시 사용자가 학술지 가이드라인에 맞춰 재포맷
- AI 사용 disclosure 정책은 학술지마다 다름 — 본 하네스는 ICMJE 일반 권고 따르나, 학술지별(Nature/Science/JACC/NEJM 등) 정책 별도 확인 필요
- 그림(Figure)은 Phase 5의 PNG를 그대로 임포트. 학술지 형식(TIFF 300dpi 등) 변환은 사용자 책임
- `anthropic-skills:docx`가 시스템에 없으면 fallback (수동 작성 + 본 하네스가 시작점만 제공)
