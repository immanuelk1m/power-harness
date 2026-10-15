power-harness 스킬의 절차를 처음부터 끝까지 그대로 실행하세요.

**먼저 최신 스킬 원본을 GitHub에서 직접 열어 읽으세요.** 업로드되거나 기억된 사본은 오래됐을 수 있으니 쓰지 마세요.
- https://raw.githubusercontent.com/immanuelk1m/power-harness/main/SKILL.md
- https://raw.githubusercontent.com/immanuelk1m/power-harness/main/references/contract.md
- https://raw.githubusercontent.com/immanuelk1m/power-harness/main/references/evidence.md
- https://raw.githubusercontent.com/immanuelk1m/power-harness/main/references/row-template.md
- https://raw.githubusercontent.com/immanuelk1m/power-harness/main/references/literature.md
- https://raw.githubusercontent.com/immanuelk1m/power-harness/main/references/pivot.md
- https://raw.githubusercontent.com/immanuelk1m/power-harness/main/references/diagnostics.md
- https://raw.githubusercontent.com/immanuelk1m/power-harness/main/references/heuristics.md
- https://raw.githubusercontent.com/immanuelk1m/power-harness/main/references/datasets.md
결과 첫 줄에 SKILL.md에 적힌 버전(`power-harness v1.1`)을 출력하세요. v1.1이 아니면 실행하지 말고 그 사실만 알려 주세요.

- 시트: https://docs.google.com/spreadsheets/d/1eqmgRn3qJH_44Bkv14piwzhADU2fWZL8-p-d6EzF-nw/edit?gid=253#gid=253 (`발전량 연구`, `발전량 큐` 최신 원본 전체)
- 데이터셋 manifest: https://docs.google.com/spreadsheets/d/1QStrEgZsC5-5KO4excwCHBJui02m3y8SFBYH780cnE4 (Power DB; 사용 중·평가된·중단된 데이터셋과 인과 규칙. 미러 `references/datasets.md`)
- 모델 코드는 로컬 전용입니다. 코드 경로·레시피는 `references/contract.md`, `references/evidence.md`를 보세요.
- 특정 P id, SOTA W, 목표 W, 목표 개선률을 프롬프트에 하드코딩하지 마세요.
- 매 실행마다 `발전량 연구` 최신 원본 전체를 읽어 현재 SOTA와 **현재 계약**(첫 발행 2024-12-31 17:00 컷오프, 발행 경계 수정 후 patch, forecast_only)의 작업 챔피언을 스스로 확정하세요. 계약 이전 run은 작업 챔피언이 될 수 없고, 현재 계약 replay가 없으면 첫 행을 REPLAY로 내세요.
- 후보 생성과 우선순위는 사전 추정 W 개선률이 아니라 **정보이득, 미해결 가설의 판별력, 현재 병목과의 직접성, 기존 실험과의 독립성, 물리적 타당성**을 중심으로 판단하세요. 예상 개선률의 최소 임계값을 쓰지 마세요.
- 축은 2025 평가창 전체 3-seed 결과나 충분한 표본의 정보 검정으로만 닫힙니다. SMOKE-FIRST smoke(F1/N3 seed1, W_observed_support)·단일 fold·실행 실패 결과는 중복 근거가 아닙니다.
- **1.5단계 연구 건강 진단(H1–H8)을 반드시 코드로 계산해 표로 보이고, 발동한 신호의 큐 조치를 다른 규칙보다 먼저 따르세요.** 재현이 안 된 개선 위에 쌓지 말고(REPLICATE), 같은 유형이 포화됐으면 다른 층(예측 대상·정산 손실·구조)으로 전환하세요. H8이 발동하면 아키텍처 전체 피봇(ARCH) 계보를 여세요. ARCH는 단독 판정만 하고 블렌딩하지 않습니다.
- **손으로 정한 휴리스틱은 제안하지 마세요**(`references/heuristics.md`): 학습 시작일·patch 폭·변수 부분집합·임계값·시간대 bin 보정 표·고정 가중·축소 상수·군집 수를 새로 넣거나 그 값을 바꾸는 행은 금지입니다. 챔피언의 휴리스틱을 학습형 구성요소로 바꾸는 행은 권장합니다. 문헌에 정의된 표준 물리량(태양 기하·청천 일사·청명 지수·셀 온도 모델)은 출처를 인용하면 허용합니다.
- 근거: 웹 검색으로 literature를 먼저 찾고 원문을 확인하세요. 채택할 논문이 부족하면 **수학적 모델 + 태양광 발전 물리·정산 메커니즘**을 함께 제시하세요(NWP → 일사 → PV 변환 → 사이트 합 → 그룹 합 → SMP·k 가중 정산 중 어디인지).
- 스킬의 후보 게이트를 통과한 행만 `발전량 큐`에 최대 4건(4번째는 ARCH-STEP 전용) 끝에 append로 추가하세요(`references/row-template.md` 양식, `순서` 칸은 비움). 0건으로 끝내지 말고, 통과 후보가 없으면 근거를 보강해 다시 시도한 뒤 그래도 없으면 가장 큰 연구 불확실성을 줄일 1건을 LOW-CONFIDENCE로 추가하세요. 마지막에 상태 표·진단 표·추가 행 요약·기각 후보·검토 논문 표를 보여 주세요.
