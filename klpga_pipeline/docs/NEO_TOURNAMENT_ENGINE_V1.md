# NEO Tournament Engine v1

## 목표

이 엔진은 특정 대회를 위한 코드가 아니다.

KG 레이디스 오픈, OK저축은행 읏맨 오픈,
다음 대회, 1년 뒤 대회가 동일한 운영 코드를 사용한다.

## 절대 규칙

1. 정상 운영 코드에 대회명 하드코딩 금지.
2. 정상 운영 코드에 특정 gameCode 하드코딩 금지.
3. 날짜만으로 stage 변경 금지.
4. 공식 데이터 검증 결과만 stage를 변경한다.
5. 미검증 값은 추측해서 공개하지 않는다.
6. WD/DQ/CUT를 명시적으로 처리한다.
7. CUT 확정 전 CUT/다음 라운드 확률 공개 금지.
8. 모델 실패가 factual LIVE를 파괴해서는 안 된다.
9. publish 검증 실패 시 이전 정상 LIVE를 보존한다.
10. 모든 예측은 model version과 input snapshot을 기록한다.
11. 모든 대회 종료 후 예측과 실제 결과를 평가해 history에 보존한다.
12. 대회별 emergency script는 정상 운영 dependency가 될 수 없다.

## State machine

DISCOVERED
→ ENTRY_READY
→ PRE_READY
→ R1_LIVE
→ R1_COMPLETE
→ R2_LIVE
→ R2_COMPLETE
→ CUT_CONFIRMED
→ R3_LIVE / FINAL_LIVE
→ FINAL_COMPLETE
→ POST_EVALUATED

실제 라운드 수는 tournament configuration으로 처리한다.

## Architecture

Official Source
→ Collector
→ Raw Archive
→ Parser
→ Reconciliation
→ Validation Gate
→ Tournament State Engine
→ Model Adapter
→ Model Validation
→ Renderer
→ Publish Gate
→ Deploy
→ LIVE Verification
→ History

## Model independence

Tournament Engine과 NEO 모델은 분리한다.

Tournament Engine
→ stable Model Adapter
→ NPI / Monte Carlo / 후속 모델 버전

모델 업그레이드는 허용한다.
대회가 바뀐다는 이유로 Tournament Engine을 수정하는 것은 허용하지 않는다.

## Acceptance

### Historical regression
KG 레이디스 오픈을 동일 엔진으로 재생한다.

### Current tournament
OK저축은행 읏맨 오픈을 동일 엔진으로 처리한다.

### Future tournament
새 gameCode를 입력하거나 자동 탐지했을 때
Tournament Engine 코드 변경 0줄이어야 한다.

### Automation
30분 scheduled cycle에서 사용자 입력 없이:

discover
→ collect
→ validate
→ determine stage
→ model if eligible
→ build
→ publish gate
→ deploy
→ LIVE verify
→ history

까지 완료되어야 한다.

실패하면 기존 정상 LIVE를 유지하고 실패 기록만 남긴다.
