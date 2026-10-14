# Literature 검색과 수학·물리 대안

## A. 웹 검색 절차
1. 2단계에서 확정한 병목마다 검색 질의 1–2개를 만든다. 총 4–6개를 한 번에 병렬로 검색한다. 태양광 논문으로 한정하지 않는다. 방법론이 옮겨질 수 있으면 풍력·부하·가격 예측 등 다른 분야 논문도 허용한다.
2. 기간은 최근 2년(현재 날짜 기준) 논문을 우선한다. 수학적 기초가 되는 고전 방법(청천 일사 모델, PV 성능 모델, quantile·cost-sensitive 회귀, 계층 예측 reconciliation 등)은 연도 제한 없이 인용할 수 있다.
3. 후보 논문은 원문(PDF/HTML)을 열어 메커니즘, 입력, 대상, 평가 방식을 확인한다. 초록만 보고 채택하지 않는다.
4. 같은 논문 판정: 제목, 제1저자, arXiv id/DOI 중 하나라도 같으면 같은 논문이다.
   - 그 논문의 메커니즘이 이미 2025 평가창 3-seed로 평가됐거나 지금 큐에 대기 중이면 제외한다.
   - 시트에서 검토만 됐거나 smoke·실행 실패로 끝난 논문은 제외하지 않는다(evidence.md, SKILL 2단계 닫힘 규칙). 이 경우 이전 행 ID를 `[중복 검사]`에 적는다. 과거 paper-scout가 큐에 넣었던 논문(HDGCN, ECM:X 직접 클러스터, e2eTD, ARFEAT, iTransformer, G-DDPM, Dou NWP shapelet, Baguan-solar, PARA-PV, SunCastNet 등)이 여기에 해당한다.

### 병목별 질의 예시 (현재 병목에 맞게 바꿔 쓴다)
| 병목 | 질의 예시 |
|---|---|
| 흐린 날·운량 예보 오차 | day-ahead PV forecast NWP cloud cover error correction machine learning 2025; probabilistic cloud regime PV forecast |
| 피크 시간(k=3)·고 SMP 가중 오차 | cost-sensitive loss price-weighted forecast error energy imbalance; decision-focused learning renewable bidding |
| 그룹 합 정산(집계 오차) | hierarchical forecast reconciliation PV aggregation; direct vs bottom-up aggregate solar forecast |
| NWP 표현(발행분 전체 시퀀스) | NWP sequence encoder day-ahead solar power transformer 2025; multi-source NWP fusion solar |
| 사이트 간 공간 상관 | spatio-temporal graph PV forecasting distributed sites 2025; site embedding transfer PV |
| 가동 상태·결측·출력 제한 | PV curtailment detection forecasting; availability state estimation solar fleet |
| 계절·연도 간 분포 이동 | distribution shift day-ahead PV forecasting covariate shift importance weighting |
| 손으로 정한 휴리스틱의 학습형 대체 | learned sample weighting time series nonstationarity; learnable post-processing calibration forecasting; learned grouping optimization aggregation |

### 논문 채택 체크리스트 (모두 예여야 채택)
- [ ] 메커니즘이 2단계에서 측정한 W 성분 하나를 직접 겨냥한다.
- [ ] 필요한 입력이 contract.md의 허용 source로 발행 시각 이전에 얻어진다.
- [ ] 챔피언 레시피 위에 단일 변경으로 옮길 수 있다(PIVOT·ARCH 제외).
- [ ] (ARCH) 구조 전체를 재현할 수 있다: 공개 코드 또는 충분한 구조·하이퍼파라미터 기술, 비슷한 과제의 실측 성능, GPU·12시간 예산 안의 학습 비용.
- [ ] 닫힌 축이나 대기 큐와 메커니즘이 다르다.
- [ ] 우리 문제로 옮겼을 때 손으로 정한 창·임계값·bin·군집 수·가중이 필요 없다(`heuristics.md`). 논문이 그런 값을 쓰면 그 부분을 학습형으로 바꿔 옮길 수 있어야 한다.
- [ ] 워커 1개로 12시간 안에 3-seed 전체 평가창 run이 가능하다.
- [ ] 이 방법이 테스트하는 **미해결 연구가설**을 한 문장으로 쓸 수 있다.
- [ ] 성공과 실패가 서로 다른 후속 연구 결정을 만든다.
- [ ] 기존 후보와 다른 정보원·표현·물리상태·예측대상·학습단위 중 적어도 하나를 새로 검증한다.
- [ ] 발전량 문제에 옮길 때 어떤 물리·정산 경로로 그룹 W에 영향을 주는지 설명할 수 있다.

논문의 benchmark 개선률은 후보 통과 조건으로 쓰지 않는다. 우리 문제에서 예상 개선률을 계산할 수 없는 것은 기각 사유가 아니다.

검토한 논문은 모두 표로 남긴다: 제목 / 저자 / 연도 / 링크 / 메커니즘 / 채택·기각 사유(체크리스트의 어느 항목 때문인지).

## B. 수학·물리 대안 작성 규칙 (채택 논문이 부족할 때)
일반론("복잡도를 줄인다", "robust하게 만든다")은 후보가 아니다. 아래 여섯 가지를 모두 쓴다.
1. **대상 성분 정의.** 챔피언 W를 분해한다. 예: W = Σ_g Σ_t SMP_t·k_t·|e_{g,t}|, e_{g,t} = Σ_{i∈g}(ŷ_{i,t} − y_{i,t}) = (청천 기준 일사 오차) + (운량·투과 오차) + (PV 변환·가동 상태 오차) + (사이트 상쇄 후 잔여). 겨냥하는 성분을 수식으로 정의하고 그 크기를 내부 수치로 쓴다(예: 피크 11–15시 W 비중, 흐린 날 W 비중, 월별 W).
2. **물리 메커니즘.** `NWP 대기 상태 → 지표 일사(태양 기하·청천·투과) → PV 변환(셀 온도·인버터 clipping·열화·가동) → 사이트 합 → 그룹 합 → SMP·k 가중 정산` 중 어디에 개입하는지 쓴다. 운량이면 구름 투과·산란, 온도면 셀 효율 계수, 강수·적설이면 패널 덮임·세정, 가동이면 정지·출력 제한 상태와 연결한다.
3. **모델·추정량.** 새로 추정하는 양과 추정식을 쓴다. 예: 청명 지수 κ̂_t = E[GHI_t/GHI_cs,t | NWP], p(G_g,t | NWP_issue)의 분위수, 정산 손실 L = Σ SMP_t·k_t·|Σ_{i∈g} ŷ_i − G_g|를 직접 최소화하는 학습, 그룹 합 제약 아래 reconciliation.
4. **가정과 반증 조건.** 인과성(발행 시각), 정상성(연도 간 분포 이동), 식별 가능성(사이트 가동 시점이 늦은 사이트) 등 결과를 좌우하는 가정과 깨졌을 때의 영향을 쓴다. 가설이 맞다면 관측돼야 할 중간 지표와, 틀리다면 나와야 할 결과를 적는다.
5. **정보이득 / 결정 효과.** 성공 시 강화되는 가설과 다음 행동, 실패 시 약화·종료되는 축, 이 실험 없이는 구분할 수 없는 두 경쟁 설명. 예상 W 개선값은 신뢰성 있게 산출할 수 있을 때만 보조로 적는다.
6. **첫 구현 단계.** 기준 레시피의 어느 함수(`powerlab/baselines.py`의 어느 단계)나 variant 키에 무엇을 추가하는지 코드 수준으로 한 가지만 쓴다.

## C. 근거 표기
- LITERATURE 행: `[가설·근거]`에 논문 링크와 "우리 문제로 옮기는 방식"을 쓴다.
- MATH/PHYSICS 행: `[가설·근거]`에 위 1–4를, `[연구 가치와 정보이득]`에 5를, `[단일 변경]`에 6을 쓴다.
