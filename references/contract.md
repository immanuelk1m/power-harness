# 평가 계약 (고정값 — 워커 규칙 `~/power_forecast/AGENTS.md` HARNESS:20261014 기준, 2026-10-14)

## 과제와 평가
- 과제: OIBC 2026 태양광 253개 발전소(PV001–253)의 시간별 발전량(kWh)을 예측하고, 사이트를 두 그룹 G1/G2로 묶은 그룹 합으로 정산한다.
- 발행 시각: target ts(KST, 우측 닫힘: `ts=01:00`은 00:00–01:00)마다 `(ts − 1h)`의 날짜 기준 **전일 17:00 KST**(`powerlab/protocol.py::issue_time`). 그 시각 이후 정보는 입력이 될 수 없다.
- **평가창(연구용 검증):** 2025-01-01 01:00 ~ 2025-06-01 00:00 KST, 3,624시간 × 253개소. 예측은 이 격자와 정확히 일치해야 한다. 독립 test가 아니라 반복 연구용 검증 점수다. 실제 대회 test(2025-06~2026-05)에는 로컬 정답이 없다.
- **지표:** W = Σ_t SMP_t · k_t · (|Ĝ1_t − G1_t| + |Ĝ2_t − G2_t|), k_t = 3 (ts.hour 11–15), 그 외 1. R = 정산 수익, S = R − 0.10·W. **W가 낮을수록 좋다.** 그룹마다 설비용량 ≥ 20,000kW, 그룹은 정확히 G1·G2 두 개.
- 판정은 보호 평가기 `powerlab/evaluate.py::evaluate`만 쓴다. `result.json`의 `metrics`는 S, R, W, penalty, mae, rmse, `group_metrics.G1/G2`, `monthly`(2025-01~05)를 준다.
- **판정 단위:** 2025 평가창 전체, seed 0/1/2 세 run. seed-mean W와 seed별 W, G1/G2 W, 월별 W를 보고한다.
- smoke(F1/N3 seed1, `W_observed_support`, P0467 대비)와 내부 fold 판정은 없다(HARNESS:20261014가 SMOKE-FIRST:20261011을 대체). OOF·nested fold 점검은 디버깅 참고용이다.

## 동적 기준 선택
- 이 문서에는 특정 P id나 W를 현재 기준으로 고정하지 않는다.
- 매 실행 시작 시 `발전량 연구` 최신 전체를 읽어 현재 SOTA와 현재 계약의 작업 챔피언을 확정한다.
- 과거 P0420 계열 등의 값은 historical evidence로만 쓰고 현재 기준값으로 자동 사용하지 않는다.
- 후보 생성에 고정 최소 예상 개선률을 두지 않는다.
- noise scale이 필요하면 최신 반복·재현 실험의 seed 짝 차이에서 동적으로 추정한다.

## 현재 계약 (2026-10-14) — 작업 챔피언 자격
1. **첫 발행 컷오프:** 모든 fit, 전처리 파라미터, 그룹 구성 선택, OOF 기반 보정·가중 테이블이 2024-12-31 17:00 KST(첫 발행) 이전 라벨만 쓴다. 학습 라벨 상한 `TRAIN_END`=2025-01-01 00:00이지만 실제 fit은 마지막 7시간을 뺀다.
2. **발행 경계 patch:** ctx 류 주변 시간 patch 특징은 같은 발행분 예보 안에서만 만든다. 2026-10-11 03:39 `powerlab/baselines.py` 수정 이전 코드로 만든 patch run은 계약 이전이다(X0225).
3. **입력 정책:** `forecast_only`(실적 입력 없음)가 기본이다. `rolling_actuals_to_issue`(발행 시점까지 실적을 입력으로만 사용, 재학습 금지)는 실제 대회에 실적 입력이 없으므로 별도 comparator로만 기록하고 같은 순위에 섞지 않는다.
4. 2025 라벨로 재학습·보정·하이퍼파라미터 선택을 하지 않는다. 그룹 구성은 컷오프 이전 chronological OOF로만 최적화한다.
- 계약 이전 run은 SOTA 표에 남기되 작업 챔피언이 될 수 없다. 계약 replay(같은 레시피를 위 규칙으로 다시 만든 run)가 작업 챔피언의 출발점이다.

## SOTA 갱신
- run 완료 시 그 시점의 현재 SOTA·작업 챔피언과 같은 계약인지 먼저 확인한다.
- 같은 계약이면 seed-mean W, seed별 방향, G1/G2·월별 W로 비교한다. 채택은 평균 W 개선 + 모든 seed 악화 없음(기존 power 규칙) 이상이고, 작업 챔피언 이동은 −1.5% + 모든 seed 개선, 확정은 REPLICATE(seed 3·4·5) 6-seed 짝비교다.
- 계약이 다르면 `SOTA 갱신`이라 부르지 않고 comparator 결과로 기록한다.

## 인과 규칙 (위반은 무효)
- 입력은 발행 시각(전일 17:00 KST) 이전에 얻을 수 있어야 한다. NWP는 round 10(D-1 10:00 발행)과 round 17(D-1 17:00 발행) 모두 합법이다.
- 실측 기상(observed_wa/wb)의 target 시각 값, 실현 SMP, 2025 발전 실적은 입력·보정·선택에 쓰지 않는다. 실측 기상은 컷오프 이전 NWP 보정 학습 쌍이나 hindsight 진단(큐 행 금지)으로만 쓴다.
- 사이트 좌표로 실제 발전소를 재식별하면 실격 사유다. 외부 발전소 데이터 조회 금지.
- poison check(2025 라벨·미래 실적을 바꿔도 예측이 변하지 않음)를 통과해야 한다.

## 허용 데이터 source (2026-10-15)
- **데이터는 Power DB 시트(미러 `references/datasets.md`)에 있는 데이터셋(PW-xxx)만 쓴다(사용자 2026-10-15).** 워커는 외부 데이터를 내려받지 않는다. 아래 사용자 예외도 이미 로컬에 있고 시트에 올라 있는 것만 쓸 수 있다. 새 원천 수집·기존 데이터셋 기간 연장·가중치나 재분석 다운로드가 필요한 행은 내지 않는다. 시트에 없는 데이터가 꼭 필요하다고 판단되면 행을 내지 말고 결과 요약에 '데이터 추가 제안'으로 따로 적는다.
- **데이터셋 목록과 상태는 최신 live manifest를 따른다.** `references/datasets.md`는 과거 미러다. 미러에만 남은 항목·과거 사용자 예외는 현재 사용 가능의 증거가 아니다. live manifest에 없는 항목은 후보 입력으로 쓰지 않는다. 원본은 Google Sheet [Power DB](https://docs.google.com/spreadsheets/d/1QStrEgZsC5-5KO4excwCHBJui02m3y8SFBYH780cnE4/edit) 탭 `데이터셋 manifest`다. 행에서 데이터를 지정할 때 그 ID(PW-xxx)와 로컬 경로를 쓴다.
- 기본: 대회 원자료(sites, generation, forecast_wa/wb, observed_wa/wb, smp, baseline.py)만. 그 밖의 외부 데이터·외부 사전학습 모델은 금지다.
- 사용자 예외(AGENTS.md): Himawari-8/9 위성(NOAA Open Data), Baguan 계열 가중치·코드와 그 로컬 재현 학습, Chronos-2 가중치(frozen prior, fine-tune 금지), PARA-PV 코드, ERA5/CLDAS/JAXA 재분석(승인됐으나 미수집 — 2026-10-15부터 수집 금지라 사용 불가), SunCastNet용 IFS/GFS 아카이브·가중치. 출처 URL·revision·checksum·다운로드 날짜를 기록하고, 대회 데이터를 외부로 보내지 않는다. 새 외부 source는 사용자 결정이 필요하므로 행으로 내지 않는다.
- 외부 source는 평가창(2025-01~05)의 발행 시각마다 그때 얻을 수 있었어야 한다. 바이트 단위 과거 이력 입증이 없으면 문서화된 보수적 지연 상수를 행에 적는다.

## 자원 (워커 1개 기준)
- 디스패처는 power 워커를 **동시에 1개만** 띄운다(solar와 6슬롯 공유). CPU 3–4스레드에 고정된다. 트리·부스팅은 CPU, 딥러닝·파운데이션 모델은 GPU 필수(2장 공용, `resources.gpu_lease`로 대기).
- 워커 1개의 제한 시간은 12시간, 실패하면 디스패처가 최대 4회까지 이어서 재시도한다.
- 참고: provided_baseline 계열 run은 seed당 약 1분(P0420 44.6초)이다. 3-seed 전체 평가는 매우 싸므로, 비용 게이트는 주로 DL·대형 모델에 걸린다.

## 코드 위치 (워커 로컬 경로, 모두 `~/power_forecast`)
- 실행: `.venv/bin/python -m powerlab.cli run --id P#### --model provided_baseline --seed <s> --variant '<json>' --parent <id> --hypothesis '<…>'` → `research/runs/P####/{config,result,manifest}.json, predictions.parquet`. 새 모델은 새 파일(`powerlab/<약칭>_*.py`)로 만들고, 2025 평가창 격자 전체의 사이트 예측을 보호 평가기 `evaluate`로 채점해 같은 run 디렉터리 형식으로 남긴다.
- historical 최고 레시피(계약 이전): `research/runs/P0420/config.json` — provided_baseline, objective regression_l1, rounds [17], train_from 2022-01-01 01:00, composition_v2.csv, patch ctx7, sample_weight smpclim, postcal hourbias_bd400.json, jesaffine jes_full.json, extra_trees, n_estimators 250.
- 모델: `powerlab/baselines.py::run_baseline`(제공 `baseline.py`의 `features`/`FEATS`/`solar`, `_apply_patch`, `_sample_weights`, `_apply_postcal`, `_apply_jesaffine`).
- 산출물 생성기: `research/oof/make_oof.py`, `research/oof/swap_search.py`, `research/costs/build_smp_weights.py`, `research/correction/fit_correction.py`, `research/affine/fit_jes.py`. 첫 발행 컷오프판은 `powerlab/cutoff_regenerate_fi17.py`(`research/cutoff_fi17/`), 중첩 기준은 `powerlab/nested_reference.py`(P0467).
- 보호 파일(수정 금지): `powerlab/protocol.py`, `powerlab/evaluate.py`, `tests/test_evaluate.py`, `research/protocol_hashes.json`, 원본 데이터.
