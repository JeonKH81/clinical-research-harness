# Clinical Research Harness — Project Routing

이 프로젝트는 **Clinical Research Harness v1**을 사용하는 임상연구 프로젝트입니다.
모든 자연어 요청은 먼저 `clinical-research-orchestrator` 스킬을 거쳐 적절한 Phase로 라우팅됩니다.

---

## 자연어 라우팅 규칙

사용자가 다음과 같이 말하면 해당 Phase로 라우팅합니다:

| 사용자 발화 패턴 | 라우팅 |
|---|---|
| "문헌 좀 찾아줘", "선행연구", "research gap", "이 RCT를 내 데이터로 재현하자", "external validation" | **Phase 1** (`lit-search`) |
| "가설을 PICO로 정리해줘", "내 연구가설 좀 봐줘" | **Phase 2** (`hypothesis-refiner` + `prereg-lock`) |
| "연구계획서 만들어줘", "IRB 제출 자료", "프로토콜 작성" | **Phase 3** (`protocol-writer`) |
| "데이터 받았다", "이 데이터로 검증 가능한가", "표본 크기" | **Phase 4** (`data-inspect`) |
| "분석 돌려줘", "Cox 회귀", "생존분석", "Kaplan-Meier" | **Phase 5** (`stat-analysis`) |
| "논문 초안", "manuscript", "IMRaD", "투고", "draft" | **Phase 6** (`manuscript-writer`) |
| "처음부터 도와줘", "이 주제로 연구를 시작하고 싶다" | **Phase 0부터 순차 진행** |
| "가설 바꾸자" (Phase 2 잠금 이후) | **차단 → amendment 절차 안내** |

분류가 모호하면 Orchestrator가 명확화 질문을 합니다.

---

## 강제 정책 (자동 적용 — 우회 불가)

### 1. Citation Grounding (인용 환각 방지)

모든 인용은 검색 도구가 실제 반환한 **PMID 또는 DOI**를 동반해야 합니다.
LLM이 자유 생성한 인용은 출력 단계에서 자동 거절됩니다.

근거: ChatGPT의 의학 인용 환각률은 30–50% 범위로 보고됨 (Bhattacharyya 2023, Chelli JMIR 2024).

**호출 경로**: Cowork mode에서는 PubMed MCP (`mcp__pubmed__search_articles`), CLI에서는 API 직접 호출 (`pubmed_query.py`). 두 경로 모두 같은 `search_log.json` 형식 사용. 자세한 매핑은 `.claude/skills/lit-search/SKILL.md` 참조.

### 2. Pre-registration Recording (HARKing 자동 트레일)

Phase 2의 사전등록(`prereg.json`)은 **SHA-256 해시와 함께 기록**됩니다 (Soft 기록 모델, v1).
- 파일 자유 변경 가능 — 시스템 차원 잠금 안 함
- 변경 시 evolution_log에 자동 기록 (PREREG_HASH_DRIFT)
- 정식 변경 사유 기록 원하면 amendment 명령 사용 (선택)
- 사전등록과 어긋나는 분석은 자동으로 `exploratory` 라벨

근거: HARKing은 Kerr 1998 이래 비윤리적으로 분류되나(Rubin 2017), *기술적 강제*보다 *연구자 본인의 학술 약속·외부 timestamping(OSF 등)*이 더 본질적인 방어선. 본 하네스는 자동 감사 트레일을 제공할 뿐.

### 3. PHI Local-only (환자 정보 보호)

환자 식별정보(PHI)는 어떤 경우에도 외부 LLM API로 전송되지 않습니다 (비타협).
- 데이터 파일은 로컬에서만 처리
- LLM 컨텍스트로는 컬럼명, 요약통계, 결측 패턴만 전달
- **개별 행(row) 데이터 절대 LLM 비전송** — informed-consent로도 풀지 않음

**자동 마스킹 (v1.0)**: 직접 식별자에 한정 — 실명·생년월일·주민등록번호 (`name`, `dob`, `birth_date`, `ssn`, `rrn`, `jumin`, `national_id` 등).

**인지 확인 (informed-consent)**: 차트번호·주소·전화·이메일 등은 자동 마스킹 대신 사용자에게 경고. 분석 포함 여부는 사용자 결정 (후향 코호트에서 차트번호는 추적용으로 의도적으로 사용되는 경우 많음).

**사용자 책임**: 출력물 외부 공유 시 차트번호·주소 등이 포함되지 않도록 본인 점검.

### 4. Exploratory Tagging (p-hacking 방지)

사전등록에 없는 분석은 모두 `exploratory` 라벨로 분리 출력됩니다.
- Confirmatory: Bonferroni 보정
- Exploratory: Benjamini–Hochberg FDR 보정
- p-value 외 effect size + 95% CI 항상 함께 보고

### 5. IRB Gate (분석 권고 정책 — informed-consent)

Phase 3에서 생성된 `irb_metadata.json`의 `irb_status`에 따라 Phase 5 분석 진입 시 처리가 다릅니다:
- `approved`, `exempt`, `expedited` → 정상 진행
- `pending_submission`, `submitted`(심사 중) → 경고 + 사용자 명시적 override 가능. override 시 evolution_log에 영구 기록 (학술 무결성 트레일)

Phase 4 (데이터 검정 가능성) 진입은 `irb_status`와 무관하게 가능 — *데이터 분석*이 아닌 *적합성 검토*에 해당.

철학: 후향적 익명화 자료의 IRB 면제 가능성, 외부 협력 전 사전 분석 등 합법적 시나리오 존재로 일률 차단은 부적절. 사용자(연구자)의 학술적 책임으로 위임하되 모든 override는 학술 트레일에 영구 기록.

---

## Phase별 게이트 (Human-in-the-loop 체크포인트)

| Gate | 위치 | 사용자가 확인할 것 |
|---|---|---|
| **G0** | Phase 0 종료 | IRB 승인 범위, PHI 처리 정책, 학술적 책임 소재 |
| **G1** | Phase 1 종료 | Gap 후보 중 선택 |
| **G2** | Phase 2 종료 | **사전등록 기록** (자유 변경 + 자동 로깅) |
| **G3** | Phase 3 종료 | **연구계획서 검토, IRB 제출/승인/면제 상태 입력** |
| **G4** | Phase 4 종료 | Feasibility verdict, 진행/중단/대안 |
| **G5** | Phase 5 종료 (1차 분석 후) | 임상적 해석, PH 가정 검토, 민감도 분석 |
| **G6** | Phase 6 종료 (Manuscript draft 후) | IMRaD·STROBE 충족·Discussion 임상 함의·ICMJE AI disclosure |

각 게이트에서 사용자 명시적 승인 없이는 다음 Phase로 진행되지 않습니다.

**v1.0 범위**: Phase 0–6까지. Phase 7(peer review) · Phase 8(revision)은 본 하네스 범위 밖 — 사용자가 직접 또는 외부 도구로 처리.

---

## 워크스페이스 디렉토리 규칙

- 모든 프로젝트별 산출물은 `workspace/{project-name}/` 아래에 생성
- 데이터 파일은 `workspace/{project-name}/input/`에 두되 **PHI 포함 시 이 폴더는 Dropbox/iCloud 등 클라우드 동기화에서 제외**
- 사전등록 잠금 파일: `workspace/{project-name}/phase2_hypothesis/prereg.json`
- 연구계획서: `workspace/{project-name}/phase3_protocol/research_protocol.docx`
- IRB 메타데이터: `workspace/{project-name}/phase3_protocol/irb_metadata.json`
- Manuscript 초안: `workspace/{project-name}/phase6_manuscript/manuscript_draft.docx`
- AI 사용 disclosure: `workspace/{project-name}/phase6_manuscript/ai_disclosure.md`
- Evolution 로그: `workspace/{project-name}/evolution_log.md`

---

## 참고

- 설계 문서: `Clinical_Research_Harness_v1_Design.docx`
- 원본 하네스 개념: [jikime/harness-lab](https://github.com/jikime/harness-lab) (카카오 황민호 님 원본 [revfactory/harness](https://github.com/revfactory/harness) 기반)
- 보고 가이드: STROBE (관찰연구), 향후 v3에서 TRIPOD-AI (예측모델 연구)
