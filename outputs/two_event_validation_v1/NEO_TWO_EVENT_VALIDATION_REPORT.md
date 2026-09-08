# NEO Two-Event Validation Report

- Generated: `2026-09-06T21:29:39Z`
- Global status: **WAIT**
- Postmortem freeze: **BLOCKED**
- Model tuning: **BLOCKED**
- Next event mode: **SHADOW_ONLY**

## Event status

| Event | Status | Forecast | Result | Tuning |
|---|---|---|---|---|
| 제15회 KG 레이디스 오픈 (2026080001) | WAIT | WAIT | PASS | False |
| ↳ score | EVALUATED | winner hit=False | Brier=0.00829809 / LogLoss=3.96541603 | Top5 coverage=0.285714 |
| OK저축은행 읏맨 오픈 (2026120001) | PASS | PASS | PASS | True |
| ↳ score | EVALUATED | winner hit=True | Brier=8.7e-07 / LogLoss=0.00662188 | Top5 coverage=0.6 |

## Blockers

- `2026080001`: **WAIT**

## Operating rule

Do not tune, overwrite, or recalibrate a model until every required official result is frozen and this report is PASS.
