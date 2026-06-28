# IRB 연구계획서 템플릿 사양 (기관 표준 한국어 IRB 양식)

`build_protocol.py`가 결정론적으로 재현하는 .docx 구조. 이 문서는 사양의 근거이자 변경 시 참조.

## 표지
- "연구계획서" (제목, 중앙, 20pt)
- 국문 제목 (중앙, 14pt) / 영문 제목 (중앙, 11pt)
- `책임 연구자: {기관} {과} {이름} ({직위})`
- 작성일 / `Ver. {version}`
- (페이지 나눔)

## Protocol Outline (2열 요약표, Table Grid)
| 라벨 | 출처 |
|---|---|
| 연 구 제 목 | title_ko (+ title_en) |
| 연 구 목 적 | outline.purpose ‖ objectives.primary |
| 연 구 기 관 | institution |
| 연구책임자 | pi (이름·과·직위·email) |
| 공동연구자 | co_investigators ‖ "해당 없음" |
| 연 구 대 상 | outline.subjects ‖ prereg.population |
| 연 구 기 간 | study_period |
| 연 구 방 법 | outline.methods ‖ analysis_plan.primary_method |
| 기대효과 및 예상결과 | outline.expected ‖ objectives.expected |

## 본문 (번호 섹션, Heading 1)
1. **연구제목** — (국문)/(영문)
2. **연구 배경 및 목적** — background prose, in-text [n] 인용
3. **연구목표 및 기대효과** — 1차 목표 / 2차 목표(불릿) / 기대효과
4. **예상 연구기간** — study_period
5. **연구 내용 및 방법** (Heading 2 하위)
   - 1) 연구 설계 — design_narrative
   - 2) 연구 방법
     - 연구대상 (선정 기준 / 제외 기준, 불릿)
     - 노출/중재 및 비교군 — prereg.exposure / comparator
     - 결과 변수 — 1차 / 2차(불릿)
     - 데이터 수집 및 전처리 — data_collection ‖ data_provenance 자동요약
     - 인공지능 알고리즘 — ai_algorithm 있을 때만
     - 통계 분석 — primary / 공변량 / 민감도·하위군 / 결측 / 다중검정 / 소프트웨어
     - 표본 수 산출 — sample_size ‖ sample_size.py 자동
6. **연구대상자 안전보호 / 윤리** — 8개 소항목 (기본문구, ethics로 override)
   1. 연구 대상자 보호 원칙
   2. IRB 심의 분류 및 동의 면제
   3. 데이터 익명화 및 개인정보 보호
   4. 헬싱키 선언 준수
   5. 자료 보관 및 폐기
   6. AI 사용 공개 (ICMJE AI Disclosure)
   7. 이해상충 및 연구비
   8. 연구 결과 발표 계획
7. **참고문헌** — Vancouver, 각 항목에 PMID/DOI 태그

## SSOT 매핑 (prereg.json → 섹션)
| prereg 필드 | 섹션 |
|---|---|
| hypothesis.design | 5-1) 연구 설계 |
| hypothesis.population | 5-2) 연구대상 |
| hypothesis.exposure / comparator | 5-2) 노출/비교군 |
| hypothesis.outcome_primary / outcomes_secondary | 5-2) 결과 변수 |
| hypothesis.effect_size_assumption | 5-2) 표본 수 산출 (sample_size.py) |
| analysis_plan.* | 5-2) 통계 분석 |
| data_provenance | 5-2) 데이터 수집 |
| Phase1 search_log.json | 7. 참고문헌 (Citation Grounding) |

## 기관 커스터마이즈
다른 기관 양식이 필요하면 `build_protocol.py`의 `render_ethics` 기본문구와 Protocol Outline 라벨,
섹션 제목만 교체하면 된다. 구조 로직(SSOT 병합, 자동 표본수, 인용 검증)은 기관 독립적.
