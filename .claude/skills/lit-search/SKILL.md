---
name: lit-search
description: 임상연구 문헌 검색. 환경에 따라 PubMed MCP 도구(Cowork mode) 또는 PubMed E-utilities API(CLI)를 자동 선택. Citation Grounding 정책에 따라 도구가 직접 반환한 PMID/DOI만 사용하며 LLM 자유생성 인용은 차단. Phase 1 전용. literature-scout agent에 의해 호출.
license: MIT
---

# Lit-Search Skill

## 목적
임상연구 주제에 대해 도구 검증된 문헌만 검색·정리하여 research gap을 식별한다.

## 트리거
- literature-scout agent가 호출
- 사용자가 "문헌", "검색", "gap", "선행연구"를 직접 언급

---

## 작동 원칙 (5가지)

### 1. Tool-grounded only (도구 검증 인용만)
LLM이 자유 생성한 인용은 출력 단계에서 자동 거절된다. 모든 출력 인용은 다음 두 경로 중 하나여야 한다:
- (a) PubMed/Semantic Scholar API가 직접 반환한 PMID/DOI
- (b) 사용자가 명시적으로 제공한 PMID/DOI (post-hoc resolve 검증 후 사용)

근거: ChatGPT의 의학 인용 환각률은 30–50%로 보고됨 (Bhattacharyya 2023, Chelli JMIR 2024).

### 2. Reproducibility by default (재현 가능성 기본 원칙)
모든 검색은 `search_log.json`에 영구 기록된다. 6개월 후 동일 쿼리·동일 필터로 재실행 시 같은 결과 보증을 목표로 한다 (PubMed 인덱스 자체의 변동은 불가피하나, 그것까지 메타데이터로 기록).

### 3. Structure over volume (양보다 구조)
검색 결과를 단순 리스트로 제시하지 않는다. 모든 논문을 PICO 차원으로 분류해 구조화된 표를 만든다. "100건 발견"보다 "Population별 분포: 동아시아 12건, 서구 88건"이 더 가치 있다.

### 4. Opportunities as candidates, not conclusions (연구 기회는 후보일 뿐)
연구 기회(research opportunity)는 *후보로 제시*하고 *결론으로 단정하지 않는다*. 임상연구의 가치는 "비어있는 gap 메우기"에만 있지 않고, **이미 알려진 결과를 본인 코호트에서 재현·검증**하는 데도 있다. 따라서 본 스킬은 다음 9가지 카테고리를 모두 후보로 제시한다:

**A. 새로운 영역 (Gap 기반)** — A1 Population / A2 Intervention / A3 Outcome / A4 Methodological
**B. 기존 연구 재검토** — B1 Replication / B2 External validation / B3 Real-world evidence / B4 Subgroup deep-dive
**C. 업데이트 기반** — C1 Updated analysis (가이드라인·기술 변화 후 재평가)

LLM은 "X 분야에 기회가 있다"는 가치 판단을 단정하지 않고, "이런 기회 후보가 있고 임상적 중요성은 사용자 판단"으로 명시한다.

### 5. Recency × Quality balance (최근성과 질의 균형)
기본 필터는 최근 5–10년 + SR/MA/RCT 우선. 다만 landmark 논문(고인용 RCT, 가이드라인 변경 분기점)은 연도 무관하게 포함하도록 사용자 검토 게이트를 둔다.

---

## 호출 경로 — 환경 자동 감지 (MCP 우선, API fallback)

본 스킬은 두 가지 경로를 모두 지원한다. 실행 환경에 따라 자동 선택:

| 환경 | 우선 경로 | 도구 |
|---|---|---|
| Claude Desktop App (Cowork mode) | **MCP** | `mcp__pubmed__search_articles`, `get_article_metadata`, `find_related_articles`, `lookup_article_by_citation`, `convert_article_ids` |
| Claude Code (CLI) | **API 직접 호출** | `python scripts/pubmed_query.py` |

### 자동 감지 로직

LLM은 다음 순서로 시도:

1. **MCP 가능한지 확인**: 사용 가능한 도구 목록에 `mcp__d2d22bd4-...__search_articles` 또는 `mcp__pubmed__search_articles` 같은 PubMed MCP 도구가 있는가?
   - **있음** → MCP 경로 사용
   - **없음** → 다음 단계
2. **API 직접 호출 가능한지 확인**: `python3 scripts/pubmed_query.py` 실행 가능 + `NCBI_API_KEY` 환경변수 등록됨?
   - **둘 다 만족** → API 경로 사용
   - **불만족** → 사용자에게 환경 설정 안내

### 출력 형식 — 두 경로 모두 동일

두 경로 모두 **같은 search_log.json 형식**으로 저장한다 (재현성 보장). MCP 호출의 경우 LLM이 결과를 다음과 같이 정규화:

```json
{
  "tool": "mcp__pubmed (Claude desktop) 또는 pubmed_query.py (CLI)",
  "version": "1.0",
  "timestamp": "ISO 8601",
  "query_user": "사용자 자연어 표현",
  "query_full": "PubMed가 실제 받은 query",
  "filters": { "years": 10, "max": 100, "types": [...] },
  "n_results": N,
  "articles": [
    {
      "pmid": "38916491",
      "doi": "10.1093/eurjpc/zwae212",
      "title": "...",
      "authors": ["Mahmoud AK", "Farina JM", ...],
      "journal": "Eur J Prev Cardiol",
      "year": "2024",
      "publication_types": ["Journal Article", "Multicenter Study"],
      "abstract": "..."
    }
  ]
}
```

### MCP 결과 → search_log.json 매핑 (LLM 책임)

PubMed MCP의 응답 구조를 우리 형식으로 정규화:

| MCP 필드 | search_log.json 필드 | 처리 |
|---|---|---|
| `identifiers.pmid` | `pmid` | 그대로 |
| `identifiers.doi` 또는 `doi` | `doi` | 그대로 |
| `title` | `title` | 그대로 |
| `authors[].last_name + initials` | `authors` (배열) | "Smith J" 형식으로 결합 |
| `journal.iso_abbreviation` | `journal` | abbreviation 우선 |
| `publication_date.year` | `year` | 그대로 |
| `article_types` | `publication_types` | 그대로 |
| `abstract` | `abstract` | 그대로 |

### 환경별 호출 예시

**Cowork mode (MCP)**:
```
mcp__pubmed__search_articles(
  query="("Lipoprotein(a)"[MeSH] OR "Lp(a)"[Title/Abstract]) AND ...",
  date_from="2015",
  max_results=100,
  sort="relevance"
)
→ pmids 받음 → mcp__pubmed__get_article_metadata(pmids) → 메타데이터 → search_log.json 저장
```

**Claude Code (API)**:
```bash
python3 scripts/pubmed_query.py   '...query...'   --years 10 --max 100   --output workspace/{project}/phase1_lit/search_log.json
```

---

## 구동 과정 (단계별 흐름)

```
[1] 사용자 주제 발화 + Phase 0 G0 통과 확인
        ↓
[2] MeSH 용어 추출
    - 사용자 자연어 표현 → 표준 의학 용어 매핑
    - 예: "다혈관" → "Multivessel Coronary Artery Disease"[MeSH]
        ↓
[3] Boolean 쿼리 자동 구성 + 사용자에게 확인
    - AND/OR/NOT 연산자
    - 필터: 연도(default 5년), publication type(SR/MA/RCT 우선)
        ↓
[4] PubMed E-utilities 호출 (pubmed_query.py)
    - esearch → PMID 목록
    - efetch → 메타데이터 (제목·저자·초록·DOI)
    - search_log.json에 영구 기록
        ↓
[5] (선택) Semantic Scholar 인용망 보강
    - 핵심 PMID들의 인용 관계 분석
    - landmark 논문 자동 식별 (고인용 + 노드 중심성)
        ↓
[6] PICO 차원 분류
    - 모든 논문을 Population/Intervention/Comparator/Outcome 차원으로 라벨링
    - Study design (RCT/cohort/case-control/cross-sectional)
    - N (표본 크기)
        ↓
[7] 9가지 연구 기회 카테고리 자동 식별
    A. Gap 기반 (새 영역)
       - A1 Population gap (특정 환자군 부재)
       - A2 Intervention gap (head-to-head 부재)
       - A3 Outcome gap (hard endpoint 부재)
       - A4 Methodological gap (단일기관·소표본만 있음)
    B. 기존 연구 재검토
       - B1 Replication study (landmark RCT를 본인 코호트로)
       - B2 External validation (예측 모델·위험 점수 외부 검증)
       - B3 Real-world evidence (RCT 결과의 실세계 일반화)
       - B4 Subgroup deep-dive (기존 연구 내 하위군 추가 분석)
    C. 업데이트 기반
       - C1 Updated analysis (가이드라인·기술 변화 후 재평가)
        ↓
[8] research_opportunities.md 생성 (각 후보에 근거 PMID ≥1건)
        ↓
[9] Citation 후처리 검증
    - 모든 PMID를 PubMed esummary로 한 번 더 resolve
    - 모든 DOI를 Crossref로 resolve
    - 실패 시 자동 거절 + evolution_log 기록
        ↓
[10] G1 게이트 — 사용자에게 어느 gap을 추구할지 묻기
```

---

## 출력 명세

| 산출물 | 위치 | 의미 |
|---|---|---|
| search_log.json | `workspace/{project}/phase1_lit/search_log.json` | 쿼리·시점·필터·결과 영구 기록 (재현용) |
| research_opportunities.md | `workspace/{project}/phase1_lit/research_opportunities.md` | 9가지 카테고리 연구 기회 후보 + 근거 PMID |
| citation_network.json (선택) | `workspace/{project}/phase1_lit/citation_network.json` | Semantic Scholar 인용망 |
| evolution_log 추가 기록 | `workspace/{project}/evolution_log.md` | Phase 1 진입·완료, gap 선택 |

---

## search_log.json 스키마

```json
{
  "tool": "pubmed_query.py",
  "version": "1.0",
  "timestamp": "2026-05-08T05:31:35+00:00",
  "query_user": "primary PCI multivessel MACE",
  "query_full": "(\"primary PCI\"[Title/Abstract] AND \"multivessel\"[Title/Abstract]) AND ...",
  "filters": {
    "years": 5,
    "max": 200,
    "types": ["Systematic Review", "Meta-Analysis", "Randomized Controlled Trial"]
  },
  "n_results": 8,
  "articles": [
    {
      "pmid": "38001234",
      "doi": "10.1001/jama.2024.1234",
      "title": "...",
      "authors": ["Smith J", "Lee K"],
      "journal": "JAMA",
      "year": "2024",
      "publication_types": ["Randomized Controlled Trial"],
      "abstract": "..."
    }
  ]
}
```

---

## research_opportunities.md 템플릿

```markdown
# Research Opportunities — {project-name}

**검색일**: {ISO 8601}
**검색 쿼리**: {query_full}
**총 검토 논문**: {N}건 (SR/MA M건, RCT K건, 예측모델 P건)

---

## A. 새로운 영역 (Gap 기반)

### A1. [제목] — Population gap
**근거 부재 영역**: 예) 동아시아 STEMI 환자에서 staged PCI 효과 검증 부재
**참고 RCT (서구 코호트)**: Smith J, et al. JAMA 2024;331:1234. [PMID: 38001234]
**기회 신뢰도**: high / medium / low
**임상적 의의**: (사용자 검토 필요)

### A2. [제목] — Intervention gap
...

---

## B. 기존 연구 재검토

### B1. [제목] — Replication study
**검증 대상 연구**: SYNTAX-II Trial (Banning AP et al. NEJM 2018) [PMID: 29385640]
**원 결과**: 다혈관 PCI군 5년 MACE 17.4%
**본인 코호트에서 검증 가치**: 동아시아 환자, 실세계 데이터, 더 긴 follow-up
**임상적 의의**: (사용자 검토 필요)

### B2. [제목] — External validation
**검증 대상 모델/점수**: SYNTAX score (Sianos G et al. 2005) [PMID: 19105492]
**원 데이터**: 1,800명 (서구 코호트)
**본인 코호트에서 적용 가치**: 한국인 후향 데이터에서 calibration·discrimination
**임상적 의의**: (사용자 검토 필요)

### B3. [제목] — Real-world evidence
**검증 대상 RCT**: ISAR-REACT 5 (Schüpke S et al. NEJM 2019) [PMID: 31475796]
**RCT 선정 기준 좁음**: 75세 이하, ACS만 등
**본인 코호트의 차이**: 모든 연령·합병증 포함
**임상적 의의**: (사용자 검토 필요)

### B4. [제목] — Subgroup deep-dive
**원 연구**: ...
**원 연구에서 보고된 효과**: 전체군에서만 보고
**검증할 하위군**: 당뇨군 / 고령군 / 신부전군 등
**임상적 의의**: (사용자 검토 필요)

---

## C. 업데이트 기반

### C1. [제목] — Updated analysis
**기존 결과**: 1세대 DES 시기 1년 ST 1.5% 보고
**시점 변화**: 2세대·3세대 DES 도입, 더 강력한 항혈소판제 도입
**재분석 가치**: 현재 환자에서 ST·MACE 패턴
**임상적 의의**: (사용자 검토 필요)
```

---

## 실패 모드 (informed-consent 원칙)

| 시나리오 | 기대 동작 |
|---|---|
| LLM이 PMID 없는 자유 인용 자동 생성 | 후처리 검증에서 **자동 거절 (이건 우회 불가)** — Citation Grounding 핵심 정책 |
| 검색 결과 0건 | 사용자에게 알리고 쿼리 완화 제안 (MeSH 용어 변경, 필터 완화) |
| 검색 결과 너무 많음 (>500) | 더 구체적인 필터 권고 (연도 좁힘, 추가 키워드) |
| Semantic Scholar API 실패 | PubMed만으로 진행, 인용망 분석은 생략 |
| 사용자가 비영어 문헌 요청 | v1 미지원 안내 → 사용자가 직접 검색 후 PMID/DOI 형식으로 입력 가능 (post-hoc resolve로 검증) |
| 사용자가 가짜 또는 오타 PMID 직접 입력 | post-hoc resolve 시 자동 거절, 정정 요청 |
| Landmark 논문이 5년 필터에서 누락 | 사용자 요청 시 연도 필터 완화. B 카테고리(Replication/Validation) 검색은 연도 무관 별도 호출 |
| Replication 후보가 될 만한 RCT 인지 못 함 | 보조 쿼리: "[조건] AND randomized AND landmark" + 인용수 정렬 |
| External validation 후보 점수가 검색 안 됨 | 사용자가 점수명(SYNTAX, GRACE 등) 직접 입력 시 별도 검색 |
| NCBI rate limit 초과 | 자동 재시도 + 백오프, 실패 지속 시 NCBI_API_KEY 등록 권고 |
| Network/SSL 에러 | 명확한 에러 메시지 + 진단 명령 제시 (curl 등) |

**핵심 차이점**: Citation Grounding(Tool-grounded only)은 informed-consent로 풀지 않는 비타협 정책 — 자유 생성 인용 허용 시 본 하네스 전체 신뢰도가 무너지기 때문이다.

---

## 게이트 G1 — 연구 기회 선택

Phase 1 완료 시 사용자에게:
> "다음 연구 기회 후보 중 어느 것을 추구하시겠습니까?
>  A. 새로운 영역(Gap 기반): A1, A2, A3, A4
>  B. 기존 연구 재검토: B1, B2, B3, B4
>  C. 업데이트 기반: C1
>  또는 직접 작성하실 수도 있습니다."

### 검증 항목
- 사용자 응답이 명시적이어야 함 (예: "B1" 또는 자유서술 입력)
- "둘 다 좋아 보임" 같은 모호한 응답 시 재질문
- 사용자가 직접 작성하는 경우 PMID/DOI 근거 동반 권고

### 자동 거절
- PMID/DOI 근거가 전혀 없는 후보 → 거절 (Citation Grounding, 비타협)

### 카테고리별 후속 Phase 영향
| 선택 카테고리 | Phase 2(가설 정제)에서 강조 | Phase 3(IRB)에서 추가 고려 |
|---|---|---|
| A (Gap) | 새 가설 PICO 정제 | 일반 IRB 절차 |
| B1 (Replication) | 원 RCT 가설을 본인 코호트에 맞춰 재정제 | "원 연구 재현"임을 IRB에 명시 |
| B2 (External validation) | 모델 calibration·discrimination 가설로 정제 | 모델 사용 권한 확인 (가이드라인·라이선스) |
| B3 (RWE) | "선정기준 완화" 명시적 분석 계획 | RWE 연구임을 명시 |
| B4 (Subgroup) | 사전 명시된 하위군 정의 | 원 연구 인용 |
| C (Update) | "변화 시점" 정의 + 시기별 비교 | 시계열 분석 명시 |

---

## 한계 명시 (의도된)

- PubMed에 없는 **회색문헌(grey literature)**, 학회 abstract(일부 PubMed indexed 제외), preprint(medRxiv 등 일부)은 누락 가능
- 한국어·일본어 등 **비영어 문헌**은 별도 KMBASE/KISS 검색 필요 (v1 미지원, 사용자가 PMID 형식으로 직접 입력 가능)
- 진행 중 임상시험(ClinicalTrials.gov)은 별도 검색 필요 (v1 미지원)
- "이 gap이 임상적으로 중요한가"의 가치 판단은 LLM 영역 밖 — 사용자 검토 필수
- PubMed 인덱스 자체가 시점에 따라 변동 가능 (재현성 한계의 외재 요인)

## 도구 호출 명세

### pubmed_query.py
```bash
python scripts/pubmed_query.py \
  "(\"primary PCI\"[Title/Abstract] AND \"multivessel\"[Title/Abstract])" \
  --years 5 \
  --types "Systematic Review,Meta-Analysis,Randomized Controlled Trial" \
  --output workspace/{project}/phase1_lit/search_log.json
```
- PubMed E-utilities (esearch + efetch)
- Rate limiting (3 req/sec without API key, 10 req/sec with NCBI_API_KEY)
- 결과 캐싱 (재실행 시 동일 쿼리는 재사용 가능)

### Citation 후처리 검증
출력 직전 모든 PMID/DOI를 한 번 더 PubMed/Crossref로 resolve하여 존재 확인.
실패 시 해당 인용 자동 거절 + evolution_log에 어느 Agent/Skill이 환각했는지 기록.
