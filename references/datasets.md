# 데이터셋 manifest (발전량)

원본은 Google Sheet [Power DB](https://docs.google.com/spreadsheets/d/1QStrEgZsC5-5KO4excwCHBJui02m3y8SFBYH780cnE4/edit) 탭 `데이터셋 manifest`다. 이 파일은 그 시트의 미러다(2026-10-14 기준, 열 일부). 시트를 열 수 있으면 시트를 우선한다.

쓰는 법:
- 후보 행이 쓰는 데이터는 아래 ID(PW-xxx)와 로컬 경로로 지정한다. 표에 없는 새 source는 `references/contract.md`의 허용·인과 규칙을 따른다.
- 인과 규칙 칸을 그대로 지킨다. 공통 규칙: 학습 라벨 ≤ 첫 발행 2024-12-31 17:00 KST, 발행 = 전일 17:00 KST, 2025 라벨로 재학습·보정 금지, 실현 SMP 입력 금지.
- "평가 후 미채택" 데이터로 다시 행을 낼 때는 그 결과를 근거로 적고 무엇이 달라지는지 밝힌다. smoke만으로 기각된 것은 축이 닫힌 것이 아니다.
- 외부 데이터는 AGENTS.md 사용자 예외 범위 안에서만 쓴다.

## 대회 원자료 (OIBC 2026)

| ID | 데이터셋 | 시작 | 끝 | 로컬 경로 | 인과(가용 시각) 규칙 | 사용처 | 상태 | 비고 |
|---|---|---|---|---|---|---|---|---|
| PW-001 | sites.csv 발전소 메타 | 정적 | 정적 | `~/power_forecast/handover 2/01_participant_dataset/sites.csv` | 정적. 좌표로 사이트를 재식별하면 실격 사유 | 모든 모델·그룹당 ≥20,000kW 규칙·평가기 | 사용 중 | sha256 93d166ff… |
| PW-002 | train/generation.parquet 발전 실적 (라벨) | 2021-01-19 13:00 | 2025-06-01 00:00 | `~/power_forecast/handover 2/01_participant_dataset/train/generation.parquet` | 학습 라벨 ≤ 첫 발행 2024-12-31 17:00 KST; 2025 라벨로 재학습·보정 금지. 2025 구간은 평가 정답 전용. rolling_actuals_to_issue 정책은 발행 시점까지 실적을 입력으로만 허용(재학습 금지) | 모든 fit, 평가기 정답 | 사용 중 | 사이트 가동 시점이 늦음(첫 ts 중앙값 2023-10-18, 2024 완전관측 148개). 2025 평가창 916,872 = 253×3,624 완전. sha256 a2c334a5… |
| PW-003 | train/forecast_wa.parquet NWP 제공처 A | 2021-01-01 01:00 | 2025-06-01 00:00 | `~/power_forecast/handover 2/01_participant_dataset/train/forecast_wa.parquet` | round 10 = D-1 10:00 발행, round 17 = D-1 17:00 발행 → 둘 다 합법. 발행 = (ts−1h) 날짜의 전일 17:00 KST | 챔피언 계열: 6변수(cloud, temp, humidity, rain, wind_speed, ground_press) + ctx7 patch(wa_cloud/wa_temp), round 17만(X0004) | 사용 중 (챔피언 입력) | 2025 연구 평가도 이 train 파일의 예보를 읽음. sha256 a2bda685… |
| PW-004 | train/forecast_wb.parquet NWP 제공처 B | 2021-01-01 01:00 | 2025-06-01 00:00 | `~/power_forecast/handover 2/01_participant_dataset/train/forecast_wb.parquet` | forecast_wa와 같음 | 챔피언 계열: 9변수(cloud, temp, rel_hum, uv_idx, precip_prob, total_liq, vis, wind_speed, dew_point) + patch(wb_cloud/wb_temp) | 사용 중 (챔피언 입력) | 강수 관련 8열에 NaN 각 1,298. sha256 e8e5de90… |
| PW-005 | train/observed_wa.parquet 실측 기상 A | 2021-01-01 01:00 | 2025-06-01 00:00 | `~/power_forecast/handover 2/01_participant_dataset/train/observed_wa.parquet` | target 시각 값은 D-1 17:00에 없음. 허용: 컷오프 이전 NWP 보정 학습 쌍, 발행 시점까지 이력(rolling 정책), hindsight 오라클(진단 전용) | wxbias X0020(+1.03% 기각), wxcorr X0182(6-seed −0.48%, 5/6, X0184 기각), Chen M5 P0456–58(+6.20%, X0199), P0475 hindsight(−34.68% W_obs, 배포 불가), smoke S0067·S0092·S0123 기각 | 근거 전용 / 평가 후 미채택 | test 기간에는 없음 |
| PW-006 | train/observed_wb.parquet 실측 기상 B | 2021-01-01 01:00 | 2025-06-01 00:00 | `~/power_forecast/handover 2/01_participant_dataset/train/observed_wb.parquet` | observed_wa와 같음 | observed_wa와 같음 | 근거 전용 / 평가 후 미채택 | 이상치 개수는 README에 문서화 |
| PW-007 | train/smp.csv 계통한계가격 | 2021-01-01 01:00 | 2025-06-01 00:00 | `~/power_forecast/handover 2/01_participant_dataset/train/smp.csv` | 실현 SMP는 입력 금지(코드에서 누출로 취급). 학습 가중에는 컷오프 이전 시간대 SMP 기후값만 사용 | 2025 평가기 가격; smp_clim_weights.json 원천 | 사용 중 | sha256 6ae610fc… |
| PW-008 | test smp.csv (제출 격자) | 2025-06-01 01:00 | 2026-06-01 00:00 | `~/power_forecast/handover 2/01_participant_dataset/smp.csv` | 제출 격자 전용 | powerlab에서 사용 없음 | 미사용 | 로컬 정답 없음, 제출 금지 |
| PW-009 | test/forecast_wa.parquet | 2025-06-01 01:00 | 2026-06-01 00:00 | `~/power_forecast/handover 2/01_participant_dataset/test/forecast_wa.parquet` | train과 같음 | 메인 레인에서 미사용 | 미사용 | 실제 제출 때만 필요 |
| PW-010 | test/forecast_wb.parquet | 2025-06-01 01:00 | 2026-06-01 00:00 | `~/power_forecast/handover 2/01_participant_dataset/test/forecast_wb.parquet` | train과 같음 | - | 미사용 |  |
| PW-011 | baseline.py 제공 기준선 코드 | - | - | `~/power_forecast/handover 2/01_participant_dataset/baseline.py` | - | baselines.run_baseline, nested_reference, chen_m5가 import | 사용 중 | sha256 ab2a5752… |
| PW-012 | README.md 데이터 설명 | - | - | `~/power_forecast/handover 2/01_participant_dataset/README.md` | - | 참고 | 참고 |  |

## 외부 데이터·가중치 (AGENTS.md 사용자 예외 범위 안에서만)

| ID | 데이터셋 | 시작 | 끝 | 로컬 경로 | 인과(가용 시각) 규칙 | 사용처 | 상태 | 비고 |
|---|---|---|---|---|---|---|---|---|
| PW-013 | Himawari-8/9 AHI L1b HSD smoke 세트 | 2022-12-12 | 2023-07-01 | `~/power_forecast/research/external_data/Baguan_solar_smoke/` | 08:00 UTC(=17:00 KST 발행) 이전 이력만 | S0135–S0139, S0117: S0136 −2.66%(악화, poison check 무효 지적), S0139 −2.13%(악화) → smoke-reject(X0360) | 평가 후 미채택 | Himawari/Baguan 사용자 예외(2026-10-10). smoke 판정만 있음 → 축 닫힘 아님 |
| PW-014 | Himawari repro_v1 | 2022-12-12 | 2023-07-01 | `~/power_forecast/research/external_data/Baguan_solar_repro_v1/` | 이력 = 발행 −6~−1h; 타깃 = 발행 +8~+31h | S0146 −0.37%(하루 대체) smoke-reject(X0366) | 평가 후 미채택 | smoke 판정만 있음 |
| PW-015 | Himawari F1-history v1 | 2023-06-30 | 2023-12-18 | `~/power_forecast/research/external_data/Baguan_solar_F1_history_v1/` | 예정 스캔 10분 전 fallback, 발행 이전 | 학습에 쓰인 적 없음 | 중단 | 2026-10-13 03:25 중단(download_stop_checkpoint.json, X0382) |
| PW-016 | NOAA ISatSS Himawari-9 tile 샘플 | 2023-06-30 00:00 UTC | 2023-06-30 00:00 UTC | `~/power_forecast/research/external_data/noaa_himawari_samples/` | - | 스키마 확인만 | 근거 전용 |  |
| PW-017 | ERA5 (CDS) / CLDAS-V2.0 (CMA) | - | - | `없음` | 재분석은 발행 시점 가용성 증빙 필요(보수적 지연 상수) | - | 미수집 (승인됐으나 막힘) | UNBLOCK:20261011/12에서 승인 |
| PW-018 | Baguan-solar 코드 | - | - | `~/power_forecast/research/external/Baguan-solar/` | - | 로컬 재현(REPRO-TRAIN:20261012)의 기반 | 중단 |  |
| PW-019 | PARA-PV 코드 | - | - | `~/power_forecast/research/external/PARA-PV/` | - | S0070 | 평가 후 미채택 |  |
| PW-020 | Chronos-2 가중치 | - | - | `~/power_forecast/research/external/chronos-2/29ec3766d36d6f73f0696f85560a422f50e8498c/` | context는 발행 시점 데이터로 제한; 사전학습 컷오프 미공개 → 오염 가능성을 한계로 기록 | S0068·S0069 기술 실패; S0070 prior-only W_obs 431.50M → 900.19M(−108.6%) smoke-reject(X0311). retrieval/adapter/PA-DSC 전체는 미시험 | 평가 후 미채택 | Chronos-2 사용자 예외(2026-10-10): frozen prior만, 가중치 fine-tune 금지 |
| PW-021 | SunCastNet 외부 입력 (IFS/GFS/재분석/가중치) | - | - | `없음` | 과거 아카이브 NWP는 발행 시각 < origin 증빙 필요 | S0093(−89.4%)·S0094(−152.7%)는 로컬 WA/WB만 사용(X0322/X0323) | 미수집 | UNBLOCK:20261012 승인 |
| PW-022 | TabPFN-3.5 가중치 (Prior Labs) | - | - | `미확인(~/.cache에 없음)` | - | research_tabpfn 레인: P1003 1월 1주 W 38.85M(전체 구간과 비교 불가), P1007 실패(CPU torch), P1008 대기 | 중단 | 2026-10-08 이후 레인 활동 없음 |

## 파생 데이터 산출물 (재사용 가능)

| ID | 데이터셋 | 시작 | 끝 | 로컬 경로 | 인과(가용 시각) 규칙 | 사용처 | 상태 | 비고 |
|---|---|---|---|---|---|---|---|---|
| PW-023 | Expanding-window OOF 예측 | 2023-07 | 2024-12-31 | `~/power_forecast/research/oof/` | 비중첩, fi17 이전 컷오프, patch 수정(2026-10-11 03:39) 이전 생성 → 현재 계약에서는 재생성 필요 | 그룹 구성·보정의 원천 | 사용 중 (계약 이전 산출물) |  |
| PW-024 | 그룹 구성 composition v1 / v2 / v3 | - | - | `~/power_forecast/research/oof/composition_v{1,2,3}.csv` | 컷오프 이전 chronological OOF로만 최적화 | v2 = 챔피언 구성 | 사용 중 (v2) / v3 기각 |  |
| PW-025 | First-issuance(fi17) 수정 산출물 | - | 2024-12-31 17:00 | `~/power_forecast/research/cutoff_fi17/` | 첫 발행 컷오프 준수 | P0453–55 +0.39% 악화 → 미채택(X0198) | 평가 후 미채택 | 현재 계약(fi17)을 지키는 유일한 챔피언 계열 산출물. 계약 replay의 출발점 |
| PW-026 | Nested reference P0467 | 2022-04 | 2024-12-31 17:00 | `~/power_forecast/research/nested_reference/builds/171089ac2d97…/` | 중첩 + 첫 발행 컷오프 + patch 수정 후 | smoke 기준(F1/N3 seed1 W_observed_support 431,499,790.86) | 사용 중 (기준 인프라) | SMOKE-FIRST 기준이었음. 하네스(LB 판정)에서는 내부 진단용 |
| PW-027 | Nested reference P0465 (폐기) | 2022-04 | 2024-12-31 | `~/power_forecast/research/nested_reference/builds/9e2a5abd09c7…/` | ctx7 patch가 발행 경계를 넘음(X0225) | - | 중단 |  |
| PW-028 | Nested reference 부분 빌드 | - | - | `~/power_forecast/research/nested_reference/builds/{5cb20ea0…,5eebd02a…,e9f159a3…}` | - | - | 중단 |  |
| PW-029 | 챔피언 보정 테이블 (smpclim·hourbias·jes·clusters) | - | 2025-01-01 00:00 | `~/power_forecast/research/costs/smp_clim_weights.json, ~/power_forecast/research/correction/hourbias_bd400.json, ~/power_forecast/research/affine/jes_full.json, ~/power_forecast/research/affine/clusters.json` | 2025-01-01 00:00까지 fit(첫 발행 17:00 위반) → fi17 판은 PW-025 | P0420 레시피 | 사용 중 (챔피언 입력, 계약 이전) | bd400·nb·sh 값은 sweep으로 고른 휴리스틱(heuristics.md) |
| PW-030 | 평가 후 미채택 보정·결합 테이블 | - | - | `~/power_forecast/research/{weather,ensemble,fusion,experts,costs,spatial}/` | - | fusion(X0025) 조건부 채택이었으나 P0420 레시피에는 없음 | 평가 후 미채택 |  |
| PW-031 | 2025 창 booster 앙상블 예측 | 2025-01-01 01:00 | 2025-06-01 00:00 | `~/power_forecast/research/dens/` | - | 참고값 | 근거 전용 |  |
| PW-032 | P0475 hindsight 실측 기상 예측 | - | - | `~/power_forecast/research/runs/P0475/` | 실측 기상 사용 → 배포 불가(오라클) | −34.68% W_observed_support (X0291) | 근거 전용 | 오라클 headroom 근거 |
| PW-033 | P0468 Stacking-RFR 예측 | - | - | `~/power_forecast/research/stacking/` | - | +6.54% 악화 | 평가 후 미채택 |  |
| PW-034 | 오라클·예측가능성 보고서 | - | - | `~/power_forecast/research/oracle/report.json, ~/power_forecast/research/forecastability/{report.json,strata.csv}` | hindsight → 진단 전용 | 병목·headroom 근거 | 근거 전용 |  |
| PW-035 | 게시 집계 (리더보드) | - | - | `~/power_forecast/leaderboard_space/results.json` | - | 결과 조회 | 사용 중 |  |
