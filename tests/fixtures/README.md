# 테스트 전용 Fixture

이 디렉터리의 HTML 파일은 **실제 KLPGA 사이트에서 수집한 데이터가 아닙니다.**

`klpga/parsers/*.py`의 파싱 로직이 `klpga/selectors.py`에 정의된 선택자 구조에
맞춰 올바르게 동작하는지 검증하기 위해, 사람이 직접 작성한 최소한의 합성
(synthetic) HTML 조각입니다. 선수명("Fixture Kim" 등)과 점수는 전부 테스트를
위해 임의로 지어낸 값이며, 실제 KLPGA 선수/대회와 무관합니다.

이 파일들은 `tests/` 아래에서만 사용되며, 절대로 `data/klpga_history.db`
(실제 운영 DB)에는 적재되지 않습니다. 실제 데이터 수집은 `klpga.collect`
모듈이 런타임에 klpga.co.kr / data.klpga.co.kr 에서 가져온 실제 페이지에
대해서만 수행합니다.
