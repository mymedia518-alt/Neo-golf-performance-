# NEO 두 대회 검증 파이프라인 V1

## 목적

제15회 KG 레이디스 오픈과 2026 OK저축은행 읏맨 오픈을 다음 대회의 개선 모델에 바로 섞지 않고, 먼저 고정된 사후검증 데이터셋으로 보존한다.

이 파이프라인은 모델을 튜닝하는 도구가 아니다. 다음 네 가지를 차단하는 감사 도구다.

1. 미래 라운드 데이터가 예측 입력에 들어가는 것
2. 실제 결과가 없는 상태에서 결과를 만들어내는 것
3. 확률 합계·선수 식별·단계명이 깨진 상태로 공개하는 것
4. 고정 검증 결과를 본 뒤 같은 대회에 맞춰 모델을 수정하는 것

## 두 대회의 역할

| 대회 | 예측 기준 | 실제 결과 | 현재 처리 |
|---|---|---|---|
| KG 레이디스 오픈 `2026080001` | PRE | 공식 결과 파일 | 기존 예측은 legacy review flag와 함께 보존 |
| OK저축은행 읏맨 오픈 `2026120001` | R2 종료 후 최종 라운드 예측 | KLPGA 월요일 공식 업데이트 후 확정 | 공식 FINAL 파일이 생길 때까지 WAIT |

OK 오픈의 `R3_LIVE_SNAPSHOT`은 진행 중 데이터다. 최종 결과 파일로 승격하지 않는다.

## 상태 규칙

- `PASS`: 예측 파일·공식 결과·출처·확률·식별 검증 통과
- `WAIT`: 공식 결과 또는 출처 증거가 아직 없음. 채점·튜닝 금지
- `HARD_STOP`: 미래 데이터, 단계 오류, 중복 선수, 확률 오류, 형식 오류

전체 결과가 `PASS`일 때만 사후검증 번들을 동결할 수 있다.

## 실행

저장소 루트에서 다음을 실행한다.

```powershell
python .\klpga_pipeline\scripts\run_two_event_validation_pipeline.py `
  --repo-root . `
  --manifest .\klpga_pipeline\config\NEO_TWO_EVENT_VALIDATION_MANIFEST_V1.json
```

또는:

```powershell
\.\NEO_TWO_EVENT_VALIDATION_PIPELINE.bat
```

공식 결과가 확인된 뒤에만 동결을 실행한다.

```powershell
\.\NEO_TWO_EVENT_VALIDATION_PIPELINE.bat --freeze
```

## 출력

```text
outputs/two_event_validation_v1/
├─ NEO_TWO_EVENT_VALIDATION_REPORT.json
├─ NEO_TWO_EVENT_VALIDATION_REPORT.md
└─ frozen/NEO_TWO_EVENT_POSTMORTEM_<UTC>/
   ├─ manifest.json
   ├─ validation_report.json
   ├─ FROZEN_EVIDENCE_INDEX.json
   └─ evidence/<game_code>/<forecast|result>/...
```

동결 번들에는 원본 파일의 SHA-256이 기록된다. 이후 모델 개선은 이 번들을 학습 데이터로 사용하지 않고, 오직 최종 홀드아웃 검증 자료로 사용한다.

## 다음 대회 준비 게이트

다음 대회의 PRE 실행 전까지 다음 조건을 확인한다.

- 두 대회의 예측·실제 결과가 모두 동결됐는가
- KG legacy 예측의 미래 데이터 제외 근거가 별도 기록됐는가
- OK 최종 결과가 KLPGA 공식 파일로 확정됐는가
- `starting_tee`, `last_played_hole`, `holes_completed`가 분리됐는가
- 54홀 예측 단계가 `POST_R2_PRE_FINAL` 또는 `FINAL_FORECAST`인가
- 공개용 `/r3/` 경로가 내부적으로 실제 R3 입력을 의미하지 않는가
- 기존 모델과 개선 모델을 동일한 고정 데이터셋에서 비교했는가
- Brier, Log Loss, Calibration, Top5/Top10, 추격자 포착률을 모두 계산했는가

하나라도 충족하지 않으면 다음 대회는 `SHADOW_ONLY`로 운영한다. 즉, 내부 계산은 하되 개선 모델을 공식 공개 모델로 승격하지 않는다.

## 이번 파이프라인이 금지하는 것

- OK 공식 FINAL 파일이 없는데 뉴스·스크린샷·라이브 스냅샷으로 결과 확정
- 99.340% 예측을 맞혔다는 이유로 확률 보정 없이 모델 승격
- 현재 두 대회의 결과를 바로 학습 데이터에 포함
- `R3`와 `FINAL`을 같은 의미로 임의 사용
- 시작홀을 반영하지 않은 완료홀 계산
- 검증 실패 행을 삭제하고 성공 행만으로 점수 계산
