# STROBE 22항목 체크리스트

> Source: STROBE Statement v4 (Vandenbroucke 2007, Elliott 2014).
> 본 체크리스트는 **관찰연구**(코호트, 환자대조, 단면) 보고에 사용됩니다.

Phase 5의 stat-analysis 스킬은 이 체크리스트를 자동 점검하며, 각 항목에 대해 다음 라벨 중 하나를 부여합니다:
- ✅ 충족 (prereg/분석 결과에서 자동 확인)
- ⚠️ 누락 (사용자 추가 입력 필요)
- N/A (해당 없음, 사유 명시)

---

## Title and Abstract

**Item 1**
- (a) 제목 또는 초록에서 일반적으로 사용되는 용어로 연구 설계 명시
- (b) 초록에서 정보적이고 균형 잡힌 요약 제공

## Introduction

**Item 2 — Background/rationale**: 연구의 과학적 배경과 근거 설명

**Item 3 — Objectives**: 사전 명시된 가설 등 구체적 목적 기술

## Methods

**Item 4 — Study design**: 연구 설계의 핵심 요소 조기 명시

**Item 5 — Setting**: 연구 setting, 위치, 관련 일자(모집/노출/추적/자료수집 시작·종료) 기술

**Item 6 — Participants**
- 코호트: 적격성 기준, 모집원, 모집 방법; 추적 방법 기술
- 환자대조: 적격성 기준, 환자/대조군 선정 근거 및 출처
- 단면: 적격성 기준, 출처, 대상 선정 방법

**Item 7 — Variables**: 모든 결과, 노출, 예측, 잠재 교란, 효과수정 변수의 명확한 정의 (적용 가능 시 진단 기준 포함)

**Item 8 — Data sources/measurement**: 각 관심 변수에 대한 자료 출처 및 측정·평가 방법 상세 기술 (둘 이상의 군이면 측정 방법의 비교가능성 기술)

**Item 9 — Bias**: 잠재적 편향 처리 노력 기술

**Item 10 — Study size**: 연구 크기가 어떻게 도출되었는지 설명

**Item 11 — Quantitative variables**: 양적 변수가 분석에서 어떻게 다뤄졌는지 설명 (적용 가능 시 grouping 선택)

**Item 12 — Statistical methods**
- (a) 교란 통제를 포함한 모든 통계 방법
- (b) subgroup, interaction 검토 방법
- (c) 결측 자료 처리 방법
- (d) 코호트: 추적 손실 처리; 환자대조: matching 처리; 단면: 표집 전략 고려 분석 방법
- (e) 민감도 분석 기술

## Results

**Item 13 — Participants**
- (a) 각 단계별 인원수 보고 (적격, 검토, 적격성 확인, 연구 포함, 추적, 분석)
- (b) 각 단계별 비참여 사유
- (c) 흐름도(flow chart) 사용 고려

**Item 14 — Descriptive data**
- (a) 참여자 특성 (인구학적, 임상적, 사회적) 및 노출/잠재 교란 변수 정보
- (b) 각 관심 변수의 결측 자료 수
- (c) 코호트: 추적 기간 요약 (mean, total)

**Item 15 — Outcome data**
- 코호트: 결과 발생 수 또는 시간 경과별 요약 측정치
- 환자대조: 노출 범주별 또는 노출의 요약 측정치
- 단면: 결과 사건 수 또는 요약 측정치

**Item 16 — Main results**
- (a) 보정 추정치 + 정확도(95% CI). 어떤 교란이 보정되었는지, 왜 포함되었는지 명시
- (b) 양적 변수가 categorize된 경우 범주 경계 보고
- (c) 적절한 경우 상대 위험을 절대 위험으로 변환 (의미 있는 기간에 대해)

**Item 17 — Other analyses**: subgroup 및 interaction 분석, 민감도 분석 수행 결과 보고

## Discussion

**Item 18 — Key results**: 연구 목적에 비추어 핵심 결과 요약

**Item 19 — Limitations**: 잠재적 편향·부정확성 출처를 포함한 연구 한계 논의 (편향의 방향과 크기 모두 논의)

**Item 20 — Interpretation**: 목적, 한계, 다중분석, 유사 연구 결과, 기타 관련 근거를 고려한 신중한 종합 해석

**Item 21 — Generalisability**: 연구 결과의 일반화 가능성(외적 타당성) 논의

## Other information

**Item 22 — Funding**: 자금 출처, 자금 제공자의 역할 (해당 시 본 연구 및 본 글의 기반이 된 원자료 연구의 경우 모두)

---

## 자동 점검 매핑 (stat-analysis 스킬)

| Item | 자동 추출 가능 | 사용자 입력 필요 |
|---|---|---|
| 1, 2, 3 | prereg.hypothesis로부터 | 초록 작성 (v2) |
| 4, 5 | prereg.hypothesis.design | setting 기술 |
| 6 | prereg.hypothesis.population | 모집 방법 |
| 7 | prereg.hypothesis 변수들 | 정의 상세 |
| 8 | data_dictionary.md | 측정 방법 비교 |
| 9 | feasibility_report.md (자동탐지 + 검토) | 잠재 편향 논의 |
| 10 | EDA의 검정력 계산 | 자유서술 |
| 11 | EDA의 변수 분포 | 분류 근거 |
| 12 | prereg.analysis_plan | 자세한 정당화 |
| 13 | 분석 코드의 N 추적 | 흐름도 (v2) |
| 14, 15 | Table 1 자동 | — |
| 16 | 분석 결과 자동 | 임상적 해석 |
| 17 | 분석 결과 자동 | — |
| 18, 19, 20, 21 | — | 사용자 작성 (v2 manuscript-writer 보조) |
| 22 | — | 사용자 입력 |

## 참고문헌

- von Elm E, et al. The Strengthening the Reporting of Observational Studies in Epidemiology (STROBE) statement. Ann Intern Med 2007;147:573–577.
- https://www.strobe-statement.org/
