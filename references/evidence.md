# 확정 사실과 닫힌 축 — historical evidence

이 파일의 P/X id와 W는 과거 실험 근거다(출처: `~/power_forecast/research/experience.jsonl`, `research/runs/*/result.json`, 시트 `발전량 연구`, 2026-10-14 기준).
현재 SOTA·현재 작업 챔피언·현재 기준값을 이 파일에서 가져오지 않는다. 매 실행 `발전량 연구` 최신 원본에서 다시 계산한다.
W 단위는 원(가격·k 가중 오차 합)이다. 아래에서 M = 10⁶원.

## 기준선
| run | 내용 | W |
|---|---|---|
| P0001 | naive(전일 17시 실적 반복, rolling 정책) | 6,698.4M |
| P0003 | 제공 LightGBM 기준선(L2) | 시트 참조 |

## historical 최고 레시피 계보 (2025 평가창 3-seed, 각 단계 채택)
| 단계 | 변경 | 평균 W 변화 | 비고 |
|---|---|---|---|
| X0003 | objective L2 → L1 | −6.87% (930.2M → 866.3M), 3/3 | seed1 1월 +3.8% |
| X0004 | NWP round 10/17 평균 → round 17만 | −1.26%, 3/3 | 2·4월 악화, 원인 미규명 |
| X0007 | 학습 창 19 → 36개월(train_from 2022-01-01) | −3.58%, 3/3 | 5월 단일 월이 견인, 1–4월은 순악화 |
| X0010 | 그룹 구성 v2(OOF min-cap 재탐색) | −0.30%, 3/3 | OOF는 v1 우위, 2025는 v2 우위(괴리) |
| X0017/18 | smpclim 표본 가중(시간대 SMP 기후값) | 조건부 채택 | |
| X0019 | 그룹×시간 48모수 bias 사후보정(postcal) | −1.73%, 3/3, 월별 15/15 | |
| X0096 / X0109 / X0123 | ExtraTrees n_estimators 400 → 300 → 250 | −0.27% / −0.24% / −0.12% | 하이퍼파라미터 미세 조정 |
| X0173 | postcal 상한 bd400 | −0.11%, 3/3 | **P0420/P0421/P0422 평균 747.22M** (737.08 / 759.01 / 745.57M) |
| X0177 | bd400 6-seed 확인 | 6-seed 평균 −0.13% | 6-seed 평균 749.65M |

- X0190 감사: runner variant 키 22종 모두 결정됨(ensemble/ensrel 폐쇄, proxy 기각, target_level=site(group 대상 X0016 +1.42% 기각), nwpvar 차단, deseason·regime/experts·feature_set 기각, fusion 보류).
- **선택 효과 경고:** 마지막 네 번의 채택은 −0.11 ~ −0.27%다. 같은 레시피의 seed 간 W 차이는 약 ±1.5%(737–759M)다. 이 크기의 "개선"은 2025 창 하나를 반복해 고른 결과로도 나온다(H1). 이 계보의 미세 조정은 재현 전에는 확정 사실로 보지 않는다.

## P0420 계열의 계약 결함 (현재 계약 replay가 필요한 이유)
1. 그룹 구성·smpclim·hourbias·jes 산출물이 2025-01-01 00:00까지 fit됐다. 첫 발행 2024-12-31 17:00 컷오프를 어긴다.
   - fi17 수리판 P0453/P0454/P0455 = 748.05 / 758.02 / 744.29M, 평균 +0.39%(seed0 +1.49%) → X0198 기각(채택 없음, reference 미인증). 산출물은 `research/cutoff_fi17/`.
2. ctx7 patch가 발행 경계를 넘었다(X0225). `powerlab/baselines.py`가 2026-10-11 03:39에 수정됐으므로, P0420 config를 지금 다시 돌리면 같은 예측이 나오지 않는다. P0453–55도 수정 전 코드다.
- 따라서 2026-10-14 현재 **현재 계약 replay는 없다.** 하네스 첫 실행은 이 replay(REPLAY 양식)부터 낸다.

## headroom·진단 사실
- REATS 오라클 라이브러리: 시간별 convex floor 571.161M vs reference 749.520M(약 −23.8%). 멤버 선택을 시간마다 사후에 고르는 한정 클래스 오라클이다(`research/oracle/report.json`).
- P0475 hindsight(target 시각 실측 기상 사용): `W_observed_support` −34.68%(X0291). 배포 불가. 기상 정보가 W의 큰 부분을 설명한다는 상한 근거다.
- 2025 창 booster 앙상블 `ensemble_xt250_bd400` 740.99M, 6-seed 742.56M(X0176/X0180): reference-only. seed 평균만으로 약 −0.8%가 나온다.
- 예측가능성 strata: `research/forecastability/{report.json,strata.csv}`.
- 사이트 가동 시점이 늦다(첫 ts 중앙값 2023-10-18, 2024 완전 관측 148/253). 학습 표본이 사이트마다 다르다.
- 월별 이질성이 크다: 여러 채택이 특정 월(특히 5월)에만 기대고 다른 월은 악화됐다(X0004, X0007).

## 2025 평가창 3-seed로 닫힌 축 (다시 낼 때는 무엇이 다른지 밝힌다)
| 축 | 결과 | 비고 |
|---|---|---|
| wxbias 3변수 NWP 입력 보정 (X0020) | +1.03%, 3/3 악화 | 2024 기상 MAE 개선이 정산 W로 전환 안 됨 |
| wxcorr NWP 보정 특징 (X0182) | −0.59%, 2/3 (seed0 +0.91%) | 6-seed −0.48%, 5/6(X0184). 새 규칙에서도 스택 후보 아님 |
| disagree WA/WB 불일치 특징 (X0181) | 기각(seed0 실패) | 6-seed −1.28%, 5/6(X0183). **근접 실패** — REPLICATE 대상 후보 |
| Chen 2025 M5 NWP 시퀀스 (X0199, P0456–58) | +6.20%, 0/3 | seed 분산 큼(s0 +15.3%) |
| 그룹 합 직접 대상 (X0016) | +1.42% | target_level=site 유지 |
| composition v3 (X0021) | 기각 | |
| fi17 artifact 수리 (X0198) | +0.39% | 계약 수리이지 성능 축이 아님 |

## smoke만으로 끝난 축 — **닫히지 않음** (SMOKE-FIRST F1/N3 seed1, `W_observed_support`, P0467 기준 431.50M)
아래는 모두 단일 fold·단일 seed 판정이었다. 같은 메커니즘을 전체 평가창 3-seed로 다시 낼 수 있다(H7·ARCH 규칙 적용).
- 근접(−0.5% 이상 개선): 태양 기하·운량 proxy 특징 X0309 −1.59%, NWP 오차 인자 X0308 −0.67%, coverage S/V/T 전이 X0355 −0.60%, TabNet 표현 X0356 −0.15%, EEMD 한 사이트 X0261 −0.04%.
- 크게 악화(대개 처음부터 새로 짠 한 행짜리 모델): Chronos-2 prior X0311 −108.6%, DHRS X0250, top-down 배분 X0256, 동적 그래프 X0255, 2×2 reconciliation X0271, TCN 그룹 X0257, Transformer X0258, iTransformer X0259·X0272, 그래프 diffusion X0260, U/V 잔차 X0267, MCNN X0270, TFT X0269, Conv1d 직접 그룹 X0312, WA/WB affine 지역화 X0310, OT 지역화 X0274.
- 그 밖: joint 그룹·시간별 bid X0262 −0.56%(악화), LSTM-AE X0249, BOCPD 가동 상태 X0363, Himawari HSD GRU X0357·X0360(−2.13 ~ −2.66% 악화), Baguan 로컬 재현 X0366, SunCastNet 로컬 X0323, CNF/Copula/GMM 기상 시나리오 X0383 등, privileged teacher X0376, 고정 leaf LP 보정 X0385, Stacking-RFR P0468(+6.54%, nested 비교), QR-STGAT X0201/X0371(고정 구현 종료).

## 과거 구조 계열 (ARCH 중복 검사용, 모두 smoke 단계에서 종료)
| 계열 | 시도 | 결과 |
|---|---|---|
| A1 그래프(사이트 그래프·GAT·diffusion) | QR-STGAT, HDGCN 동적 그래프, G-DDPM 그래프 diffusion | smoke 악화, 고정 구현 종료 |
| A2 attention 시계열(TFT·iTransformer·PatchTST·RSA-TFT) | X0258, X0259, X0269, X0272, X0273 | smoke 악화(PatchTST만 −0.53% C arm) |
| A3 RNN/CNN(LSTM-AE·AQ-RNN·MCNN·TCN·Conv1d 직접 그룹) | X0249, X0266/7, X0270, X0257, X0312 | smoke 악화 |
| A4 사전학습·위성 파운데이션(Chronos-2/PARA-PV, Baguan-solar 재현, SunCastNet) | X0311, X0366, X0323 | smoke 악화 또는 데이터 부족 |
| A5 생성형 기상 시나리오(CNF·Copula·GMM·diffusion) | X0368–X0374, X0383, X0384 | 기술 실패 또는 smoke 악화 |
- 재개 조건: 학습 예산(GPU, seed당 ≥ 30분 또는 early stop)과 전체 평가창 3-seed를 갖추고, 과거 시도와 입력 표현·학습 대상·구조 중 무엇이 다른지 적으면 그 계열의 다음 단계로 낼 수 있다. 학습 규모만 다르면 새 계보가 아니다.
