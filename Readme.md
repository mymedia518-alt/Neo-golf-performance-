# Neo Golf Performance — KLPGA Historical Data Collector

KLPGA(한국여자프로골프협회) 정규투어 공식 데이터를 실제로 수집해
SQLite Historical DB를 구축하고, 향후 대회 예측 모델의 입력이 될
선수별 과거 성적 feature를 생성하는 파이프라인입니다.

> **중요 — 이 저장소가 만들어진 환경에 대해**
> 이 코드는 Claude Code 클라우드 세션에서 작성되었고, 그 환경에서는
> 프록시 정책으로 `klpga.co.kr` / `data.klpga.co.kr` 로의 아웃바운드
> 접속이 차단되어 있어 **실제 데이터를 단 한 건도 수집하지 못했습니다.**
> `data/klpga_history.db`는 커밋되어 있지 않고, 저장소 어디에도 샘플/추정
> 데이터가 들어있지 않습니다. 아래 안내에 따라 인터넷 접속이 가능한 PC에서
> 직접 실행해야 실제 데이터가 채워집니다.
>
> 또한 `klpga/config.py`의 접속 URL과 `klpga/selectors.py`의 HTML 선택자는
> 실제 사이트 구조를 확인하지 못한 상태의 **미확인 placeholder**입니다.
> 처음 실행하기 전에 반드시 [`docs/SITE_STRUCTURE_TODO.md`](docs/SITE_STRUCTURE_TODO.md)를
> 따라 실제 구조를 확인하고 두 파일을 수정하세요.

---

## 1. 무엇을 하는 프로그램인가

1. `klpga.collect` — KLPGA 정규투어 최근 대회부터 과거 방향으로 최대 N개(기본 100개)를
   수집해 `data/klpga_history.db`(SQLite)에 저장합니다. 대회, 선수, 선수×대회 성적,
   라운드별 스코어를 모두 저장하며, 공식 데이터가 없는 항목은 절대 추정하지 않고
   `NULL`로 남깁니다. 같은 대회를 다시 수집해도 UPSERT라서 중복이 생기지 않습니다.
2. `klpga.validate` — 수집된 데이터의 품질을 자동 점검하고
   `reports/data_quality_report.md`를 생성합니다.
3. `klpga.export` — DB 내용을 분석용 CSV(`data/export/*.csv`, UTF-8 BOM)로 내보냅니다.
4. `klpga.features` — 각 대회 시점 기준으로 **그 이전 데이터만** 사용해 선수별
   최근 5/10/20/50/100경기 성적 feature를 계산합니다(미래 정보 유출 없음).
5. `klpga.predict` — 향후 예측 모델을 붙이기 위한 뼈대입니다. 실제로 학습된 모델이
   없는 한 **절대 임의의 확률을 출력하지 않습니다.**

## 2. Windows에서 설치하기 (초보자용, 순서대로 따라하세요)

### 2-1. Python 설치

1. https://www.python.org/downloads/ 에서 Python 3.11 이상 설치 프로그램을 받습니다.
2. 설치 화면 첫 화면에서 **"Add python.exe to PATH"** 체크박스를 꼭 체크하고 설치합니다.
3. 설치가 끝나면 시작 메뉴에서 "명령 프롬프트"(cmd) 또는 "PowerShell"을 열고
   아래 명령으로 설치를 확인합니다.

   ```
   python --version
   ```

   `Python 3.11.x` 같은 버전이 나오면 성공입니다.

### 2-2. 저장소 내려받기 (git 사용)

git이 없다면 https://git-scm.com/download/win 에서 먼저 설치하세요.

```
git clone https://github.com/mymedia518-alt/neo-golf-performance-.git
cd neo-golf-performance-
git checkout claude/klpga-data-collection-4u90ju
```

### 2-3. 가상환경 만들고 패키지 설치

```
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

명령 프롬프트 맨 앞에 `(.venv)`가 붙으면 가상환경이 켜진 것입니다.
(이후 새 창을 열 때마다 `cd neo-golf-performance-` 후 `.venv\Scripts\activate`를 다시 실행하세요.)

### 2-4. Playwright 브라우저 설치 (JS 렌더링이 필요한 페이지 대응)

```
playwright install chromium
```

### 2-5. 실제 사이트 구조 확인 (최초 1회, 필수)

`klpga/config.py`의 `ENDPOINTS`와 `klpga/selectors.py`의 선택자는 아직 실제
KLPGA 사이트로 검증되지 않은 값입니다. 브라우저 개발자도구(F12)로 실제
대회 목록/상세/리더보드 페이지 구조를 확인한 뒤 두 파일을 실제 값으로
수정하세요. 무엇을 확인해야 하는지는
[`docs/SITE_STRUCTURE_TODO.md`](docs/SITE_STRUCTURE_TODO.md)에 체크리스트로
정리되어 있습니다.

### 2-6. 대회 1개로 먼저 테스트

```
python -m klpga.collect --events 1
```

`data/klpga_history.db`가 생기면 아래처럼 내용을 확인해 실제 KLPGA 사이트와
값이 맞는지 눈으로 대조하세요.

```
python -m klpga.export
```

`data/export/tournaments.csv` 등을 열어 확인합니다 (엑셀에서 한글이 깨지지 않습니다).

### 2-7. 최근 100개 정규투어 대회 수집

```
python -m klpga.collect --events 100
```

### 2-8. 데이터 품질 검증

```
python -m klpga.validate
```

`reports/data_quality_report.md`가 생성됩니다.

### 2-9. CSV 내보내기

```
python -m klpga.export
```

### 2-10. 예측용 feature 생성

```
python -m klpga.features
```

### 2-11. 예측 (모델이 아직 없으므로 임의 확률을 절대 출력하지 않습니다)

```
python -m klpga.predict
```

## 3. 데이터베이스 구조

`data/klpga_history.db` (SQLite)

| 테이블 | 설명 |
|---|---|
| `tournaments` | 대회 (대회ID, 이름, 시즌, 기간, 코스, 파, 야디지, 라운드수, 대회구분, 상태, 모델포함여부) |
| `players` | 선수 (선수ID, 이름) |
| `player_events` | 선수×대회 (최종순위, 최종스코어, 합계타수, 출전라운드수, 컷통과여부, 우승/TOP5/TOP10/TOP20) |
| `rounds` | 라운드별 스코어 (대회ID, 선수ID, 라운드번호, 타수) |
| `player_event_stats` | 공식 추가 통계(SG 등)가 확인되면 저장하는 확장 테이블 (기본적으로 비어있음) |
| `player_features` | 대회 시점 기준 과거 데이터로만 계산한 롤링 feature |
| `collection_runs` | 수집 실행 기록 (시작/종료 시각, 요청 개수, 성공/실패, 오류 메시지) |

모든 쓰기는 UPSERT이므로 같은 명령을 여러 번 실행해도 중복 행이 생기지 않습니다.

## 4. 테스트 실행

```
pip install -r requirements-dev.txt
pytest
```

`tests/fixtures/`의 HTML은 파서 로직 검증을 위해 사람이 직접 작성한 합성
샘플이며, 실제 KLPGA 데이터가 아니고 실제 DB에도 들어가지 않습니다.

## 5. 설계 메모

- **adapter/parser 분리**: 실제 사이트 구조가 다르더라도 `klpga/config.py`,
  `klpga/selectors.py`, `klpga/parsers/*.py`만 고치면 되고
  `klpga/collect.py`의 오케스트레이션 로직은 그대로 재사용됩니다.
- **HTTP 클라이언트** (`klpga/http_client.py`): 타임아웃, 재시도(exponential
  backoff), 요청 간 최소 간격(rate limiting), 로컬 캐시(`data/cache/`),
  User-Agent 지정, 로깅(`logs/klpga.log`)을 모두 구현했습니다.
- **Playwright fallback** (`klpga/playwright_fallback.py`): 정적 HTML에서
  기대한 행(row)을 찾지 못하면 자동으로 헤드리스 브라우저 렌더링으로
  재시도합니다. playwright가 설치되어 있지 않아도 나머지 기능은 정상 동작합니다.
- **값 추정 금지**: `klpga/rank_utils.py`가 순위 텍스트(`CUT`/`WD`/`DQ`/숫자)를
  구조화하지만, 알 수 없는 경우는 항상 `None`으로 남깁니다. SG 등 공식
  출처가 확인되지 않은 통계는 스키마만 준비되어 있고 절대 채워지지 않습니다.
