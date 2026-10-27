# NEO PRE SG V1 2026 시간순 검증 (탐색 결과)

검증 대회 10개 · 시뮬레이션 5,000회/대회 · 자료 기준일 2026-10-18

## 확률 품질 비교

값이 낮을수록 좋은 Brier·Log Loss는 각 대회 예측을 먼저 계산한 뒤 대회 평균을 냈습니다. 승자 로그손실은 실제 우승자 확률만 평가합니다.

| 결과 | SG Brier | 타수 Brier | SG Log Loss | 타수 Log Loss |
|---|---:|---:|---:|---:|
| 컷 통과 | 0.22310 | 0.22334 | 0.63682 | 0.63775 |
| TOP20 | 0.14626 | 0.14792 | 0.45629 | 0.46018 |
| TOP10 | 0.08572 | 0.08666 | 0.29744 | 0.30078 |
| TOP5 | 0.04710 | 0.04747 | 0.18309 | 0.18521 |
| 우승 | 0.00859 | 0.00861 | 0.04781 | 0.04828 |

우승자 평균 로그손실: SG 4.501 · 타수 4.568
예측 우승자 TOP10 적중: SG 10.0% · 타수 10.0%
실제 TOP20 선수 포착률: SG 44.5% · 타수 43.0%

## 대회별 결과

| 대회 | 필드 | SG 기록 연결 | 실제 우승자 | SG 우승확률 | SG 예측 순위 | 타수 우승확률 |
|---|---:|---:|---|---:|---:|---:|
| 하이원리조트 여자오픈 2026 | 108 | 97 | 고지우 | 0.78% | 56위 | 0.86% |
| 2026 오로라월드 챔피언십 | 120 | 108 | 이다연 | 1.21% | 19위 | 0.96% |
| 제13회 제주삼다수 마스터스 | 128 | 107 | 장은수 | 0.75% | 47위 | 0.89% |
| 메디힐 · 한국일보 챔피언십 | 123 | 114 | 서교림 | 1.81% | 15위 | 0.80% |
| BC카드 · 한경 제48회 KLPGA 챔피언십 | 123 | 116 | 서교림 | 4.03% | 2위 | 2.95% |
| 제15회 KG 레이디스 오픈 | 119 | 111 | 신다인 | 1.13% | 28위 | 1.37% |
| KB금융 골든라이프 챔피언십 | 120 | 114 | 박보겸 | 1.53% | 21위 | 0.88% |
| 하나금융그룹 챔피언십 | 108 | 96 | 김민선7 | 0.78% | 44위 | 0.76% |
| 제26회 하이트진로 챔피언십 | 108 | 104 | 유해란 | 0.59% | 55위 | 1.09% |
| 아이스버그골프 · 서울신문 오픈 | 108 | 100 | 마서영 | 0.68% | 53위 | 0.85% |

## 해석

- The evaluation covers one 2026 season and only events with retained round-level SG.
- The sample is exploratory and cannot establish multi-season probability calibration.
- The score-only comparator uses the same simulator and shrinkage recipe; it is not the frozen M4 production baseline.
- Historical fields are reconstructed from players in the final result records; pre-event entry snapshots are not retained for every test event.
- The S-OIL joint SG simulation has not observed its future tournament result.

이 결과는 탐색용 비교이며 공개 검증 통과 판정이 아닙니다.
