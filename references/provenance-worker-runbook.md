# s4 기준선 산출물 감사: 워커 실행 안내

관련: [Issue #1](https://github.com/immanuelk1m/power-harness/issues/1). 대상은 P2235(seed 0), P2236(seed 1), P2237(seed 2)이다.

이 문서는 로컬 워커에서 이미 만들어진 파일을 읽어 비교하는 절차다. 보호 평가기를 호출하거나 2025 점수를 다시 계산하지 않는다. 원본 파일을 수정하지 않고, 감사 보고서도 연구 시트나 공개 저장소에 올리지 않는다.

## 실행 전 확인

`~/power_forecast/research/runs/{P2235,P2236,P2237}/`에 `config.json`, `result.json`, `manifest.json`, `predictions.parquet`, `model.pt`가 있는지 확인한다. 실제 디렉터리가 다르면 그 경로를 사용한다.

공식 평가 격자의 `site_id, ts` 열만 담은 Parquet 파일을 별도로 준비한다. 이 파일의 SHA-256은 **독립적으로 신뢰할 수 있는 기록**에서 가져온다. 검사할 파일 자체의 해시를 방금 계산해 기대값으로 넣으면 공식 격자 동일성을 입증할 수 없다. 실제 예측 열 이름도 Parquet 스키마에서 확인한다.

## 읽기 전용 감사

아래 환경변수에는 워커의 실제 경로와 확인된 값을 넣는다. `AUDITOR`는 이 PR의 `scripts/audit_run_provenance.py`를 가리킨다.

```bash
python "$AUDITOR" "$RUNS_DIR" P2235 P2236 P2237 \
  --distinct-seeds --expected-seeds 0 1 2 --match-seed-order \
  --require-group-metrics --require-provenance-hashes \
  --compare-values --expected-rows 916872 --expected-grid 253 3624 \
  --reference-grid "$OFFICIAL_KEYS" \
  --reference-sha256 "$OFFICIAL_KEYS_SHA256" \
  --prediction-column "$PREDICTION_COLUMN" > "$AUDIT_REPORT"
status=$?
printf 'audit exit code: %s\n' "$status"
```

`--reference-grid`나 신뢰할 수 있는 기대 해시를 확보하지 못했다면 두 참조 옵션을 함께 빼고 **부분 감사**로만 실행한다. 보고서에 공식 평가 입력 동일성을 확인했다고 기록하지 않는다. `--prediction-column`은 실제 예측 열 이름을 확인한 뒤 지정한다. 열을 지정하지 않으면 모든 예측·보조 열을 비교하므로 결과 해석 범위가 달라진다.

## 결과 해석

| 종료 코드 | 뜻 | 다음 조치 |
|---|---|---|
| 0 | 요청한 파일·메타데이터·값 검사에서 미완료나 경고를 찾지 못함 | 평가 입력과 독립 학습 근거를 별도로 대조 |
| 2 | 누락·읽기 실패·격자/해시 검증 미완료 등 | `missing_*`, `unreadable_*`, `unverified_value_pairs` 확인 |
| 3 | 동일 예측과 다른 W, 중복 seed, 상충 메타데이터 등 검토 필요 | `consistency_warnings`와 해당 `pairs` 확인 |

`artifact_status=present`와 `comparison_status=complete`는 파일 검사 범위의 결과다. **0번 종료도 학습 독립성이나 공식 점수 재현을 증명하지 않는다.**

특히 P2235/P2236의 `prediction_bytes_equal`, `prediction_values.equal`, `model_bytes_equal`, `W_delta`를 함께 기록한다. 값이 같고 W가 다르면 실행별 **평가 라벨·G1/G2 그룹 배정·SMP·시간 가중 k·평가기 버전·결과 경로**를 별도로 확인한다. 이 입력들은 예측 Parquet의 키와 해시만으로 검증되지 않는다.

seed 0/1/2가 서로 다르게 선언됐는지도 확인한다. seed 번호가 다르거나 모델 해시가 다르다는 사실만으로 독립 학습을 확정하지 않는다. 각 run의 학습 로그, 실제 fit 시작/종료, 데이터·코드 버전, 체크포인트 생성 이력과 fresh inference 기록을 대조한다.

## 감사 완료 조건

실제 파일의 SHA-256과 값 비교, 공식 평가 격자와 평가 입력의 동일성, seed별 독립 학습 근거를 함께 확보한다. 누락된 항목은 미확인으로 남긴다. 확인된 사실만 Issue #1에 기록하고, P2235/P2236의 서로 다른 W 원인을 추정으로 확정하지 않는다.

발전량 큐 소실 [Issue #5](https://github.com/immanuelk1m/power-harness/issues/5)는 별도 문제다. 이 감사를 이유로 큐를 복원하거나 새 실험을 등록하지 않는다.
